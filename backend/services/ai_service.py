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
    def _extract_metadata_locally(cls, text: str, target_role: str) -> Dict[str, Any]:
        """
        Extract key candidate details from resume text locally using regex and keywords.
        Used as fallback and in Demo Mode.
        """
        if not text:
            return {
                "candidate_name": "Candidate",
                "candidate_email": None,
                "skills": ["Technical Skills"],
                "experience_level": "Mid-level",
                "summary_evaluation": f"Resume successfully uploaded for the {target_role} position."
            }

        # 1. Extract Email
        import re
        email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        emails = email_pattern.findall(text)
        email = emails[0] if emails else None

        # 2. Extract Name
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        name = "Candidate"
        
        # Skip common resume section headers
        skip_keywords = {"resume", "cv", "curriculum", "vitae", "profile", "contact", "experience", "education", "skills", "summary", "page"}
        
        for line in lines[:5]:
            # Keep letters and spaces
            cleaned = "".join(c for c in line if c.isalpha() or c.isspace()).strip()
            words = cleaned.split()
            
            # Candidate name is usually 2 or 3 capitalized words
            if 2 <= len(words) <= 4:
                if all(w[0].isupper() for w in words):
                    if not any(w.lower() in skip_keywords for w in words):
                        name = cleaned
                        break

        # 3. Extract Skills
        text_lower = text.lower()
        skills = []
        common_skills = [
            "javascript", "typescript", "react", "python", "fastapi", "django", 
            "node", "java", "sql", "aws", "docker", "c++", "css", "html", "git",
            "kubernetes", "pytorch", "tensorflow", "machine learning", "nlp", "llm"
        ]
        for skill in common_skills:
            if skill in text_lower:
                skills.append(skill.capitalize() if skill not in ["aws", "sql", "html", "css", "llm", "nlp"] else skill.upper())
                
        if not skills:
            skills = ["Software Development", "Problem Solving", "Communication"]

        # 4. Experience Level
        exp = "Mid-level"
        if "senior" in text_lower or "lead" in text_lower or "manager" in text_lower or "architect" in text_lower:
            exp = "Senior"
        elif "junior" in text_lower or "intern" in text_lower or "student" in text_lower or "graduate" in text_lower:
            exp = "Entry-level"

        return {
            "candidate_name": name,
            "candidate_email": email,
            "skills": skills[:6],
            "experience_level": exp,
            "summary_evaluation": f"Candidate profile analyzed locally. Demonstrates capabilities in {', '.join(skills[:4])}. Profile matches target role {target_role}."
        }

    @classmethod
    def extract_resume_details(cls, resume_text: str, target_role: str) -> Dict[str, Any]:
        """
        Extract key details from the resume text using Gemini.
        Returns a dict containing name, key skills, experience level, and summary.
        """
        if IS_DEMO_MODE:
            return cls._extract_metadata_locally(resume_text, target_role)

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

        try:
            model = cls._get_model()
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = json.loads(response.text)
            # If the LLM failed to find name (returned 'Candidate'), try local extraction
            if not data.get("candidate_name") or data.get("candidate_name").lower() == "candidate":
                local_res = cls._extract_metadata_locally(resume_text, target_role)
                data["candidate_name"] = local_res["candidate_name"]
            return data
        except Exception as e:
            logger.error(f"Error in extract_resume_details: {str(e)}")
            # Fallback to local extraction
            return cls._extract_metadata_locally(resume_text, target_role)

    @classmethod
    def generate_interview_question(
        cls, 
        resume_text: str, 
        target_role: str, 
        chat_history: List[Dict[str, str]], 
        question_index: int,
        candidate_name: str = "Candidate"
    ) -> Dict[str, Any]:
        """
        Generates the next interview question and assesses the previous answer (if any).
        Ensures a structured flow: Intro -> Project -> Concept -> Tech Q -> Closing.
        """
        # Format chat history for prompt
        history_str = ""
        for msg in chat_history:
            role_name = "Interviewer" if msg["role"] == "ai" else "Candidate"
            history_str += f"{role_name}: {msg['content']}\n"

        prompt = f"""
        You are a professional, technical, and friendly AI Interviewer conducting a screening for the position of: {target_role}.
        Candidate's Name: {candidate_name}
        The candidate's resume is provided below.
        
        Candidate's Resume:
        {resume_text}
        
        Current Question Index: {question_index} (0-indexed)
        Total Questions: 5
        
        Here is the conversation history so far:
        {history_str}
        
        Your task is to generate the question for index {question_index} following this strict interview flow:
        - Index 0: Introduce yourself as the AI Interviewer, welcome {candidate_name} to the screening for the {target_role} role, and ask them to introduce themselves.
        - Index 1: Read their introduction. If they mentioned a project in their introduction, ask probing questions about that specific project. If they did not mention a project, identify a relevant project in their resume and ask them to describe it and their contributions.
        - Index 2: Ask a question about core technical terms or concepts related to the target role (for example, if the role is related to APIs/web services, ask "What is the difference between FastAPI and REST API?", or other relevant role-specific concepts).
        - Index 3: Ask a technical question related to the job outside of their projects (e.g., testing, databases, security, performance, or system design).
        - Index 4 (Last Question): Thank {candidate_name} for their responses, ask if they have any final questions, and conclude with "Thank you for your time, we will get back to you."
        
        Answer Checking & Continuity Rule:
        If question_index > 0:
            - You MUST check the candidate's last answer against the previous question asked.
            - Verify if their answer actually addressed the previous question. Evaluate if it was relevant, accurate, and complete.
            - In the generated question (or evaluation), you must explicitly reference their previous answer (e.g., "Regarding your point about...", "That is a great explanation of...") to maintain high conversational continuity.
            - If they avoided the question, gave an irrelevant answer, or provided insufficient detail, politely point it out and ask them to clarify or re-answer it before moving on.
        
        Provide your output in the following JSON format:
        {{
            "evaluation": "A 1-2 sentence critique of the candidate's last response (constructive, detailing what was good or what was missing). Null if this is the first question (index 0).",
            "question": "The next interview question to ask the candidate matching the specific flow rule for index {question_index}."
        }}
        """

        if IS_DEMO_MODE:
            # Mock interview script matching user flow exactly
            mock_questions = [
                f"Welcome {candidate_name}! Let's start the mock interview for the {target_role} position. To kick things off, could you please introduce yourself and tell me a bit about your professional background?",
                f"Thank you for the introduction, {candidate_name}. Let's talk about projects. Looking at your background, could you detail a specific project you worked on that is relevant to this role, explaining your contribution?",
                f"Great. Let's discuss some core technical concepts. For a {target_role} position, how would you explain the difference between FastAPI and standard REST API design patterns?",
                "Nice. Beyond project-specific details, how do you handle security, performance tuning, and unit testing when building and deploying web services?",
                f"Thank you for sharing that, {candidate_name}. We've reached the end of the interview. Do you have any questions for us? Thank you for your time, we will get back to you soon!"
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
            # Fallback matching the current step
            fallback_questions = [
                f"Welcome {candidate_name} to the AI Interview for the {target_role} position. Please introduce yourself.",
                "Tell me about a project on your resume that relates to this role and your exact contributions.",
                "Could you explain some core concepts for this role, such as the difference between FastAPI and a standard REST API?",
                "Beyond your projects, what are the best practices you follow for testing, security, and deploying software?",
                f"We have finished the interview. Do you have any questions? Thank you for your time, we will get back to you, {candidate_name}."
            ]
            q_idx = min(question_index, len(fallback_questions) - 1)
            return {
                "evaluation": "Good response. (AI Fallback)",
                "question": fallback_questions[q_idx]
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
