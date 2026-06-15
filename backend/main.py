import os
import uuid
import logging
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Database
from database import init_db, get_db, InterviewSession, ChatMessage, SessionLocal
init_db()

# Import Services
from services.parser_service import parse_resume
from services.ai_service import AIService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Interviewer API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, we allow all. Can restrict to http://localhost:5173 in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class StartInterviewRequest(BaseModel):
    candidate_name: str
    candidate_email: str
    target_role: str
    resume_text: str
    total_questions: int = 5

class AnswerRequest(BaseModel):
    answer: str

# Background Task for LLM Analysis
def run_llm_analysis_background(session_id: str, resume_text: str, target_role: str):
    db = SessionLocal()
    try:
        logger.info(f"[Background Analysis] Session {session_id}: Launching LLM details analysis.")
        details = AIService.extract_resume_details(resume_text, target_role)
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if session:
            # Update candidate details with high-quality LLM-extracted metadata
            if details.get("candidate_name") and details.get("candidate_name") != "Candidate":
                session.candidate_name = details["candidate_name"]
            if details.get("candidate_email"):
                session.candidate_email = details["candidate_email"]
            db.commit()
            logger.info(f"[Background Analysis] Session {session_id}: Resume analysis completed. Updated name = '{session.candidate_name}'")
    except Exception as e:
        logger.error(f"[Background Analysis] Error in session {session_id}: {str(e)}")
    finally:
        db.close()

# Endpoints

@app.get("/")
def read_root():
    return {"message": "AI Interviewer Backend is running!", "demo_mode": os.getenv("GEMINI_API_KEY") is None}

@app.post("/api/upload-resume")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_role: str = Form("Software Engineer"),
    total_questions: int = Form(5),
    db: Session = Depends(get_db)
):
    """
    Endpoint to upload and parse a resume.
    If it's digital PDF, it extracts text directly.
    If it fails or is scanned, it returns a code indicating client-side OCR is needed.
    """
    logger.info(f"Received file upload: {file.filename}, target_role={target_role}")
    
    try:
        file_bytes = await file.read()
        
        # Parse the resume text
        parse_result = parse_resume(file_bytes, file.filename, file.content_type)
        
        if not parse_result["success"]:
            # Check if we specifically need client-side OCR
            if parse_result.get("method") == "client_ocr_required":
                return {
                    "success": False,
                    "status": "client_ocr_required",
                    "error": parse_result["error"]
                }
            raise HTTPException(status_code=400, detail=parse_result.get("error", "Failed to parse file."))
            
        resume_text = parse_result["text"]
        
        # Use fast local extraction first to respond instantly
        details = AIService._extract_metadata_locally(resume_text, target_role)
        
        # Create a new session
        session_id = str(uuid.uuid4())
        db_session = InterviewSession(
            id=session_id,
            candidate_name=details.get("candidate_name", "Candidate"),
            candidate_email=details.get("candidate_email"),
            target_role=target_role,
            resume_text=resume_text,
            current_question_index=0,
            total_questions=total_questions,
            status="started"
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        # Offload heavy LLM analysis to background
        background_tasks.add_task(run_llm_analysis_background, session_id, resume_text, target_role)
        
        return {
            "success": True,
            "session_id": session_id,
            "details": details,
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Error in upload_resume endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/api/start-interview")
def start_interview(
    background_tasks: BackgroundTasks,
    request: StartInterviewRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint to start an interview session when resume text is sent directly
    (e.g., after client-side OCR).
    """
    try:
        session_id = str(uuid.uuid4())
        
        # Use fast local extraction first to respond instantly
        details = AIService._extract_metadata_locally(request.resume_text, request.target_role)
        
        db_session = InterviewSession(
            id=session_id,
            candidate_name=request.candidate_name or details.get("candidate_name", "Candidate"),
            candidate_email=request.candidate_email or details.get("candidate_email"),
            target_role=request.target_role,
            resume_text=request.resume_text,
            current_question_index=0,
            total_questions=request.total_questions,
            status="started"
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        # Offload heavy LLM analysis to background
        background_tasks.add_task(run_llm_analysis_background, session_id, request.resume_text, request.target_role)
        
        return {
            "success": True,
            "session_id": session_id,
            "details": details,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error in start_interview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sessions/{session_id}/next-question")
def next_question(session_id: str, payload: AnswerRequest = None, db: Session = Depends(get_db)):
    """
    Handles the interview conversational flow.
    If the candidate is answering a question, saves their response and generates the next question.
    If they are finishing, triggers evaluation.
    """
    # Retrieve session
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
        
    if session.status == "completed":
        return {
            "status": "completed",
            "feedback": session.final_feedback
        }

    try:
        # Retrieve message history
        messages_db = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()
        
        # Map history for LLM
        chat_history = []
        for m in messages_db:
            chat_history.append({
                "role": m.sender,
                "content": m.message
            })
            
        candidate_answer = payload.answer if payload else ""
        last_evaluation = None
        
        # If candidate answered a previous question
        if candidate_answer:
            # 1. Save candidate's response
            candidate_msg = ChatMessage(
                session_id=session_id,
                sender="user",
                message=candidate_answer
            )
            db.add(candidate_msg)
            chat_history.append({"role": "user", "content": candidate_answer})
            db.commit()

            # Check if this was the last question
            if session.current_question_index >= session.total_questions - 1:
                logger.info(f"[Interview Flow Log] Session {session_id}: Candidate answered the final question. Completing session.")
                
                # Generate concluding message
                concluding_msg = AIService.generate_concluding_response(
                    session.target_role,
                    candidate_answer,
                    session.candidate_name
                )

                # Save AI concluding message to database so it's in the transcript
                ai_concluding_chat = ChatMessage(
                    session_id=session_id,
                    sender="ai",
                    message=concluding_msg
                )
                db.add(ai_concluding_chat)
                chat_history.append({"role": "ai", "content": concluding_msg})
                db.commit()

                # Update status to completed
                session.current_question_index += 1
                session.status = "completed"
                db.commit()
                
                # Generate final feedback
                final_feedback = AIService.generate_final_feedback(
                    session.resume_text,
                    session.target_role,
                    chat_history
                )
                
                session.final_feedback = final_feedback
                db.commit()
                
                return {
                    "status": "completed",
                    "concluding_message": concluding_msg,
                    "feedback": final_feedback
                }

        # Determine target question index to generate
        target_idx = session.current_question_index + 1 if candidate_answer else session.current_question_index

        logger.info(f"[Interview Flow Log] Session {session_id}: Current Index = {session.current_question_index}, Target Index = {target_idx}, Candidate Answer = '{candidate_answer}'")

        # Generate the next question
        ai_response = AIService.generate_interview_question(
            session.resume_text,
            session.target_role,
            chat_history,
            target_idx,
            session.candidate_name
        )
        
        next_q = ai_response.get("question")
        last_evaluation = ai_response.get("evaluation")
        is_acceptable = ai_response.get("is_answer_acceptable", True)

        logger.info(f"[Interview Flow Log] Session {session_id}: Evaluation = '{last_evaluation}', Is Acceptable = {is_acceptable}")

        # If candidate answered a previous question
        if candidate_answer:
            # If the answer is acceptable, advance to the next step
            if is_acceptable:
                session.current_question_index += 1
                db.commit()
                logger.info(f"[Interview Flow Log] Session {session_id}: Answer ACCEPTED. Index advanced to {session.current_question_index}")
            else:
                logger.info(f"[Interview Flow Log] Session {session_id}: Answer REJECTED. Index remains at {session.current_question_index}")
        
        # Update evaluation of previous message if available
        if last_evaluation and messages_db:
            # The last candidate message would be the one we just added or the last in list
            last_candidate_msg = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id, ChatMessage.sender == "user"
            ).order_by(ChatMessage.timestamp.desc()).first()
            if last_candidate_msg:
                last_candidate_msg.evaluation = last_evaluation
                db.commit()

        # Save the AI's question in the database
        ai_msg = ChatMessage(
            session_id=session_id,
            sender="ai",
            message=next_q
        )
        db.add(ai_msg)
        db.commit()
        
        return {
            "status": "ongoing",
            "question": next_q,
            "evaluation": last_evaluation,
            "question_index": session.current_question_index
        }
        
    except Exception as e:
        logger.error(f"Error in next_question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
def get_all_sessions(db: Session = Depends(get_db)):
    """
    Returns a list of all completed interview sessions with their final report.
    """
    try:
        sessions = db.query(InterviewSession).filter(InterviewSession.status == "completed").order_by(InterviewSession.created_at.desc()).all()
        result = []
        for s in sessions:
            result.append({
                "session_id": s.id,
                "candidate_name": s.candidate_name,
                "candidate_email": s.candidate_email,
                "target_role": s.target_role,
                "created_at": s.created_at.isoformat(),
                "final_feedback": s.final_feedback
            })
        return result
    except Exception as e:
        logger.error(f"Error in get_all_sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/report")
def get_report(session_id: str, db: Session = Depends(get_db)):
    """
    Returns the final feedback report and conversation transcript.
    """
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
        
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()
    
    transcript = [
        {
            "sender": m.sender,
            "message": m.message,
            "evaluation": m.evaluation,
            "timestamp": m.timestamp.isoformat()
        } for m in messages
    ]
    
    return {
        "candidate_name": session.candidate_name,
        "candidate_email": session.candidate_email,
        "target_role": session.target_role,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "final_feedback": session.final_feedback,
        "transcript": transcript
    }
