import os
import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Initialize Gemini API
# If GEMINI_API_KEY is not set, we will run in Demo Mode with mock responses.
api_key = os.getenv("GEMINI_API_KEY")
IS_DEMO_MODE = True

if api_key:
    genai.configure(api_key=api_key)
    IS_DEMO_MODE = False
    logger.info("Gemini AI service successfully initialized.")
else:
    logger.warning("No GEMINI_API_KEY found in environment. Running in Demo Mode.")


class AIService:
    @staticmethod
    def _get_model():
        if IS_DEMO_MODE:
            return None
        return genai.GenerativeModel("gemini-1.5-flash")

    @classmethod
    def extract_resume_details(cls, resume_text: str, target_role: str) -> Dict[str, Any]:
        """
        Extract key details from the resume text using Gemini.
        Returns a dict containing name, key skills, experience level, and summary.
        """
        prompt = f"""
        Analyze the following resume text and extract the details in JSON format.
        Target Role: {target_role}

        Resume Text:
        {resume_text}

        Provide the output in the following JSON structure (strict):
        {{
            "candidate_name": "Full name of candidate, or 'Candidate' if not found",
            "candidate_email": "Email address, or null if not found",
            "skills": ["List of key technical or relevant skills matching the target role"],
            "experience_level": "Entry-level, Mid-level, Senior, or Lead",
            "summary_evaluation": "A 2-3 sentence overview of the candidate's profile in relation to the target role"
        }}
        """
        
        if IS_DEMO_MODE:
            # Generate mock details based on simple keyword search
            text_lower = resume_text.lower()
            name = "John Doe"
            email = "johndoe@example.com"
            # Simple keyword heuristic
            skills = []
            for word in ["javascript", "react", "python", "fastapi", "django", "node", "java", "sql", "aws", "docker", "c++", "css", "html", "git"]:
                if word in text_lower:
                    skills.append(word.capitalize() if word != "aws" and word != "sql" and word != "html" and word != "css" else word.upper())
            
            if not skills:
                skills = ["Software Development", "Problem Solving", "Communication"]
                
            exp = "Mid-level"
            if "senior" in text_lower or "lead" in text_lower or "manager" in text_lower:
                exp = "Senior"
            elif "junior" in text_lower or "intern" in text_lower or "student" in text_lower:
                exp = "Entry-level"
                
            return {
                "candidate_name": name,
                "candidate_email": email,
                "skills": skills[:6],
                "experience_level": exp,
                "summary_evaluation": f"Candidate possesses skills in {', '.join(skills[:4])}. Profile appears to match requirements for a {target_role} role."
            }

        try:
            model = cls._get_model()
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Error in extract_resume_details: {str(e)}")
            # Fallback to simple structure
            return {
                "candidate_name": "Candidate",
                "candidate_email": None,
                "skills": ["Technical Skills"],
                "experience_level": "Mid-level",
                "summary_evaluation": "Resume successfully uploaded. AI service encountered an API error, running on local parser."
            }

    @classmethod
    def generate_interview_question(
        cls, 
        resume_text: str, 
        target_role: str, 
        chat_history: List[Dict[str, str]], 
        question_index: int
    ) -> Dict[str, Any]:
        """
        Generates the next interview question and assesses the previous answer (if any).
        Returns a dict:
        {
            "evaluation": "Brief feedback on previous answer (or null if first question)",
            "question": "The next interview question"
        }
        """
        # Format chat history for prompt
        history_str = ""
        for msg in chat_history:
            role_name = "Interviewer" if msg["role"] == "ai" else "Candidate"
            history_str += f"{role_name}: {msg['content']}\n"

        prompt = f"""
        You are a professional, technical, and friendly AI Interviewer conducting a screen for the position of: {target_role}.
        The candidate's resume is provided below.
        
        Candidate's Resume:
        {resume_text}
        
        Current Question Number: {question_index + 1}
        
        Here is the conversation history so far:
        {history_str}
        
        Your task:
        1. If the candidate just answered a question (the last message is from Candidate), evaluate their answer briefly (strengths/flaws).
        2. Generate the next question.
           - If question_index is 0: introduce yourself, acknowledge their background briefly, and ask the first relevant technical/behavioral question.
           - If question_index > 0: ask a relevant follow-up or a new question testing their skills. Do not repeat previous questions.
           - Keep the tone professional, encouraging, yet probing.
           
        Provide your output in the following JSON format:
        {{
            "evaluation": "A 1-2 sentence critique of the candidate's last response (constructive, detailing what was good or what was missing). Null if this is the first question.",
            "question": "The next interview question to ask the candidate."
        }}
        """

        if IS_DEMO_MODE:
            # Mock interview script
            mock_questions = [
                f"Welcome! Let's start the interview for the {target_role} position. To kick things off, could you walk me through one of the most challenging projects listed on your resume and explain your role in it?",
                "Interesting. How did you handle technical trade-offs or constraints during that project, and what would you do differently if you built it today?",
                "Perfect. Working in teams often involves handling disagreements about architecture or implementation details. Can you share an experience where you had a difference of opinion with a peer and how you resolved it?",
                f"Let's dive into some tech. Given your interest in {target_role}, how do you ensure the applications you write are scalable, secure, and maintainable?",
                "Great answer. To wrap up the interview, do you have any questions for me about the team, or is there a specific skill you wanted to highlight that we haven't covered yet?"
            ]
            
            evals = [
                None,
                "Strong explanation of the project context and technologies used, showing clear ownership.",
                "Good technical reasoning. Demonstrated an understanding of trade-offs, particularly regarding efficiency versus developer speed.",
                "Excellent behavioral response. Emphasized constructive dialogue, active listening, and arriving at a consensus based on project needs.",
                "Solid overview of best practices, including security auditing, unit testing, and leveraging cloud infrastructure."
            ]

            q_idx = min(question_index, len(mock_questions) - 1)
            eval_text = evals[q_idx] if q_idx > 0 else None
            
            return {
                "evaluation": eval_text,
                "question": mock_questions[q_idx]
            }

        try:
            model = cls._get_model()
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Error in generate_interview_question: {str(e)}")
            # Fallback
            return {
                "evaluation": "Good response. (AI Fallback)",
                "question": f"Could you tell me more about how you would apply your skills to succeed as a {target_role}?"
            }

    @classmethod
    def generate_final_feedback(
        cls, 
        resume_text: str, 
        target_role: str, 
        chat_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Generates a comprehensive feedback report at the end of the interview.
        """
        history_str = ""
        for msg in chat_history:
            role_name = "Interviewer" if msg["role"] == "ai" else "Candidate"
            history_str += f"{role_name}: {msg['content']}\n"

        prompt = f"""
        You are a Senior Technical Recruiter evaluating a candidate's performance in a mock interview.
        Target Role: {target_role}
        
        Candidate's Resume:
        {resume_text}
        
        Here is the full interview transcript:
        {history_str}
        
        Analyze the interview and output a detailed evaluation in JSON. Be honest, constructive, and thorough.
        
        The output MUST adhere to this strict JSON structure:
        {{
            "overall_score": 75, // Integer score between 0 and 100
            "verdict": "Strong Hire / Hire / Borderline / No Hire",
            "summary": "A high-level summary of the candidate's performance and fit for the role (3-4 sentences).",
            "strengths": [
                "Strength 1",
                "Strength 2",
                "Strength 3"
            ],
            "improvements": [
                "Area of improvement 1",
                "Area of improvement 2",
                "Area of improvement 3"
            ],
            "technical_skills_rating": 8, // Integer out of 10
            "technical_skills_comments": "Evaluation of their technical skills based on their answers.",
            "communication_skills_rating": 8, // Integer out of 10
            "communication_skills_comments": "Evaluation of their clarity, structure, and professional tone.",
            "qa_breakdown": [
                {{
                    "question": "The question asked by AI",
                    "answer": "The answer given by the candidate",
                    "feedback": "Specific feedback on this response, what went well, and what could be better."
                }}
            ]
        }}
        """

        if IS_DEMO_MODE:
            # Mock feedback generator
            qa_breakdown = []
            temp_q = ""
            for msg in chat_history:
                if msg["role"] == "ai":
                    temp_q = msg["content"]
                elif msg["role"] == "user" and temp_q:
                    qa_breakdown.append({
                        "question": temp_q,
                        "answer": msg["content"],
                        "feedback": "The candidate provided a structured answer demonstrating relevant experience, though adding more metrics/KPIs would strengthen their response."
                    })
                    temp_q = ""
                    
            if not qa_breakdown:
                qa_breakdown = [{
                    "question": "Walk me through one of your projects.",
                    "answer": "I built a web application using React and FastAPI that processes PDF documents.",
                    "feedback": "Good description of tech stack, could elaborate more on personal contributions."
                }]

            return {
                "overall_score": 82,
                "verdict": "Hire",
                "summary": f"The candidate performed well in the interview for the {target_role} position. They showed clear hands-on experience with core concepts and spoke articulately about architectural decisions and team collaboration.",
                "strengths": [
                    "Strong project ownership and clear articulation of development challenges.",
                    "Good understanding of application scalability, security, and clean code principles.",
                    "Constructive approach to handling team conflicts and peer collaboration."
                ],
                "improvements": [
                    "Could use the STAR method (Situation, Task, Action, Result) more rigorously to quantify achievements.",
                    "Could dive deeper into specific performance optimization techniques when discussing scaling.",
                    "Should prepare questions for the interviewer that demonstrate deeper interest in company operations."
                ],
                "technical_skills_rating": 8,
                "technical_skills_comments": "Strong technical foundation. Candidate was able to explain architectural designs, security measures, and testing strategies clearly.",
                "communication_skills_rating": 9,
                "communication_skills_comments": "Excellent communication skills. Answers were well-structured, polite, and directly addressed the questions asked.",
                "qa_breakdown": qa_breakdown
            }

        try:
            model = cls._get_model()
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Error in generate_final_feedback: {str(e)}")
            # Fallback
            return {
                "overall_score": 70,
                "verdict": "Borderline",
                "summary": "AI generation failed due to API limitations. Here is a basic assessment based on interview completion.",
                "strengths": ["Completed the interview structure successfully."],
                "improvements": ["Please verify Gemini API key configuration to get detailed analysis."],
                "technical_skills_rating": 7,
                "technical_skills_comments": "Satisfactory.",
                "communication_skills_rating": 7,
                "communication_skills_comments": "Clear answers provided.",
                "qa_breakdown": []
            }
