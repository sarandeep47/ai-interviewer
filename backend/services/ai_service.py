import os
import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from groq import Groq

logger = logging.getLogger(__name__)

# Initialize API keys and clients
# If neither API key is set, we will run in Demo Mode with mock responses.
gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

IS_DEMO_MODE = not (gemini_key or groq_key)
groq_client = None

if gemini_key:
    cleaned_gemini = gemini_key.strip().strip('"').strip("'")
    if cleaned_gemini:
        genai.configure(api_key=cleaned_gemini)
        logger.info("Gemini AI service successfully initialized.")
    else:
        gemini_key = None

if groq_key:
    cleaned_groq = groq_key.strip().strip('"').strip("'")
    if cleaned_groq:
        try:
            groq_client = Groq(api_key=cleaned_groq)
            logger.info("Groq AI service successfully initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {str(e)}")
            groq_key = None
    else:
        groq_key = None

if IS_DEMO_MODE:
    logger.warning("No GEMINI_API_KEY or GROQ_API_KEY found in environment. Running in Demo Mode.")

# Model configurations (can be overridden via environment variables)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


class AIService:
    @classmethod
    def _call_llm_json(cls, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        """
        Attempts to get a JSON response from Groq first (primary).
        Falls back to Gemini (backup) if Groq fails or is not configured.
        Falls back to local mock/error handling if both fail.
        """
        if IS_DEMO_MODE:
            raise Exception("AI Service is running in Demo Mode (no API keys configured).")

        errors = []
        
        # 1. Attempt Groq (Primary)
        if groq_client:
            try:
                logger.info(f"Attempting Groq model '{GROQ_MODEL}' for JSON response...")
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                response = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                res_text = response.choices[0].message.content
                # Parse to ensure it is valid JSON
                return json.loads(res_text)
            except Exception as e:
                err_msg = f"Groq execution failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)

        # 2. Attempt Gemini (Fallback)
        if gemini_key:
            try:
                logger.info(f"Attempting Gemini model '{GEMINI_MODEL}' (Fallback) for JSON response...")
                model = genai.GenerativeModel(
                    GEMINI_MODEL,
                    system_instruction=system_instruction
                )
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.3}
                )
                return json.loads(response.text)
            except Exception as e:
                err_msg = f"Gemini fallback execution failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)

        raise Exception(f"All LLM providers failed for JSON request. Errors: {'; '.join(errors)}")

    @classmethod
    def _call_llm_text(cls, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Attempts to get a text response from Groq first (primary).
        Falls back to Gemini (backup) if Groq fails or is not configured.
        """
        if IS_DEMO_MODE:
            raise Exception("AI Service is running in Demo Mode (no API keys configured).")

        errors = []

        # 1. Attempt Groq (Primary)
        if groq_client:
            try:
                logger.info(f"Attempting Groq model '{GROQ_MODEL}' for text response...")
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})

                response = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                err_msg = f"Groq execution failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)

        # 2. Attempt Gemini (Fallback)
        if gemini_key:
            try:
                logger.info(f"Attempting Gemini model '{GEMINI_MODEL}' (Fallback) for text response...")
                model = genai.GenerativeModel(
                    GEMINI_MODEL,
                    system_instruction=system_instruction
                )
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.7}
                )
                return response.text.strip()
            except Exception as e:
                err_msg = f"Gemini fallback execution failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)

        raise Exception(f"All LLM providers failed for text request. Errors: {'; '.join(errors)}")

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
        
        # Skip common resume section headers and location words
        skip_keywords = {
            "resume", "cv", "curriculum", "vitae", "profile", "contact", 
            "experience", "education", "skills", "summary", "page",
            "gmail", "email", "github", "linkedin", "phone", "mobile", 
            "address", "india", "tamil", "nadu", "madurai", "villapuram", 
            "chennai", "bangalore", "hyderabad", "pune", "mumbai", "delhi", 
            "street", "road", "city", "state", "pin", "code", "zip", "tel", "mail"
        }
        
        for line in lines[:6]:
            # Keep letters and spaces
            cleaned = "".join(c for c in line if c.isalpha() or c.isspace()).strip()
            words = cleaned.split()
            
            # Candidate name can be 1 to 4 words
            if 1 <= len(words) <= 4:
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
        Extract key details from the resume text using Gemini (primary) or Groq (fallback).
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

        # For resume parsing: Gemini is primary, Groq is fallback
        try:
            if gemini_key:
                logger.info(f"Attempting Gemini model '{GEMINI_MODEL}' (Primary) for resume details extraction...")
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                data = json.loads(response.text)
                if not data.get("candidate_name") or data.get("candidate_name").lower() == "candidate":
                    local_res = cls._extract_metadata_locally(resume_text, target_role)
                    data["candidate_name"] = local_res["candidate_name"]
                return data
        except Exception as e:
            logger.error(f"Gemini resume extraction failed: {str(e)}")

        # Fallback to Groq for resume details extraction
        try:
            if groq_client:
                logger.info(f"Attempting Groq model '{GROQ_MODEL}' (Fallback) for resume details extraction...")
                response = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                data = json.loads(response.choices[0].message.content)
                if not data.get("candidate_name") or data.get("candidate_name").lower() == "candidate":
                    local_res = cls._extract_metadata_locally(resume_text, target_role)
                    data["candidate_name"] = local_res["candidate_name"]
                return data
        except Exception as e:
            logger.error(f"Groq resume extraction failed: {str(e)}")

        # Fallback to local extraction
        logger.warning("All LLM providers failed for resume extraction. Falling back to local/regex parsing.")
        return cls._extract_metadata_locally(resume_text, target_role)

    @classmethod
    def _is_too_similar(cls, new_q: str, previous_questions: List[str]) -> bool:
        import difflib
        import re
        
        def clean_words(s: str):
            return set(re.findall(r'\w+', s.lower()))
            
        new_words = clean_words(new_q)
        ignore_words = {"hello", "welcome", "please", "could", "you", "tell", "me", "thank", "you", "let", "s", "move", "on", "okay"}
        new_meaningful_words = new_words - ignore_words
        
        for old_q in previous_questions:
            # 1. SequenceMatcher ratio
            ratio = difflib.SequenceMatcher(None, new_q.lower(), old_q.lower()).ratio()
            if ratio > 0.75:
                return True
                
            # 2. Jaccard similarity on meaningful words
            old_words = clean_words(old_q)
            old_meaningful_words = old_words - ignore_words
            
            if new_meaningful_words and old_meaningful_words:
                intersection = new_meaningful_words.intersection(old_meaningful_words)
                union = new_meaningful_words.union(old_meaningful_words)
                jaccard = len(intersection) / len(union)
                if jaccard > 0.45:
                    return True
        return False

    @classmethod
    def evaluate_candidate_answer(
        cls,
        question_text: str,
        candidate_answer: str,
        target_role: str
    ) -> Dict[str, Any]:
        """
        Evaluates the relevance and status of the candidate's response to the last question.
        Returns:
            answer_status: "ANSWERED", "IRRELEVANT", "SKIPPED", or "I_DONT_KNOW"
            evaluation: A short critique of the response.
        """
        if IS_DEMO_MODE:
            ans_lower = candidate_answer.lower().strip()
            if not ans_lower or len(ans_lower) < 3:
                return {"answer_status": "SKIPPED", "evaluation": "No response or too short."}
            if any(phrase in ans_lower for phrase in ["skip", "move on", "pass", "don't ask this"]):
                return {"answer_status": "SKIPPED", "evaluation": "Candidate requested to skip this question."}
            if any(phrase in ans_lower for phrase in ["don't know", "dont know", "no idea", "not sure"]):
                return {"answer_status": "I_DONT_KNOW", "evaluation": "Candidate stated they don't know the answer."}
            return {"answer_status": "ANSWERED", "evaluation": "Candidate provided a relevant answer."}

        prompt = f"""
        You are a technical interviewer evaluating a candidate's answer to a specific interview question.
        Target Role: {target_role}
        
        Question Asked:
        "{question_text}"
        
        Candidate's Answer:
        "{candidate_answer}"
        
        Analyze the candidate's answer and categorize its status into one of these exact values:
        1. "SKIPPED": The candidate explicitly asked to skip, didn't answer, gave a completely empty response, or said something completely unrelated to any discussion (e.g., "skip", "next", "please pass", "leave it", "let's move on").
        2. "I_DONT_KNOW": The candidate explicitly stated they do not know the answer (e.g., "I don't know", "no idea", "not sure about this", "no clues").
        3. "IRRELEVANT": The candidate avoided the question, changed the topic, or gave an off-topic/evasive response that does not address the question asked (e.g., asked about FastAPI vs REST API, and they responded talking about their favorite food or generic greeting without answering the differences).
        4. "ANSWERED": The candidate provided a relevant response that attempts to answer the question, even if it is partially incorrect or incomplete.
        
        Provide the output in the following JSON format:
        {{
            "answer_status": "ANSWERED" | "IRRELEVANT" | "SKIPPED" | "I_DONT_KNOW",
            "evaluation": "A 1-2 sentence constructive critique of the response."
        }}
        """
        try:
            return cls._call_llm_json(prompt)
        except Exception as e:
            logger.error(f"Error in evaluate_candidate_answer: {str(e)}")
            # Default heuristics fallback
            ans_lower = candidate_answer.lower().strip()
            if not ans_lower or len(ans_lower) < 3:
                status = "SKIPPED"
            elif any(phrase in ans_lower for phrase in ["skip", "move on", "pass", "leave it"]):
                status = "SKIPPED"
            elif any(phrase in ans_lower for phrase in ["don't know", "dont know", "no idea"]):
                status = "I_DONT_KNOW"
            else:
                status = "ANSWERED"
            return {
                "answer_status": status,
                "evaluation": "Evaluation fallback run."
            }

    @classmethod
    def generate_interview_question(
        cls, 
        resume_text: str, 
        target_role: str, 
        chat_history: List[Dict[str, str]], 
        question_index: int,
        candidate_name: str = "Candidate",
        skills: Optional[str] = None,
        experience_level: Optional[str] = None,
        resume_summary: Optional[str] = None,
        previous_questions: Optional[List[Dict[str, Any]]] = None,
        is_clarification: bool = False,
        rejected_questions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates the next interview question.
        Uses Groq primarily for real-time latency optimization, falling back to Gemini.
        Uses optimized, concise resume, question memory, and chat history contexts.
        """
        # Optimize context: use resume summary, skills, and experience level if available to save tokens
        if resume_summary:
            resume_context = f"""
            Candidate Name: {candidate_name}
            Target Role: {target_role}
            Experience Level: {experience_level or 'Not specified'}
            Key Skills: {skills or 'Not specified'}
            Resume Summary: {resume_summary}
            """
        else:
            # Fallback/truncate raw resume text to save tokens
            resume_context = resume_text[:2000] + "..." if len(resume_text) > 2000 else resume_text

        # Optimize chat history: only send the last 2-3 QA pairs (max 6 messages)
        optimized_history = chat_history[-6:] if len(chat_history) > 6 else chat_history

        history_str = ""
        for msg in optimized_history:
            role_name = "Interviewer" if msg["role"] == "ai" else "Candidate"
            history_str += f"{role_name}: {msg['content']}\n"

        prev_q_str = ""
        if previous_questions:
            for i, pq in enumerate(previous_questions):
                prev_q_str += f"- Question: \"{pq.get('question')}\" | Topic: {pq.get('topic')} | Intent: {pq.get('intent')} | Status: {pq.get('status')}\n"
        else:
            prev_q_str = "None"
            
        rejected_str = ", ".join([f'"{rq}"' for rq in rejected_questions]) if rejected_questions else "None"

        prompt = f"""
        You are a professional technical AI Interviewer conducting a screening for: {target_role}.
        Candidate Name: {candidate_name}
        
        Candidate Profile:
        {resume_context}
        
        Current Question Index: {question_index} (0-indexed)
        Is Clarification Question: {is_clarification}
        
        Previously Asked Questions:
        {prev_q_str}
        
        Rejected Questions (due to being too similar to previous questions):
        {rejected_str}
        
        Recent Conversation History:
        {history_str}
        
        Task:
        Generate the next interview question for index {question_index}.
        
        Topic Flow by Index:
        - Index 0: INTRODUCTION. Welcome the candidate by name, introduce yourself, ask them to introduce themselves. (Topic: INTRODUCTION, Intent: INTRO_DISCUSSION)
        - Index 1: PROJECTS. Walk through one of their projects, frontend/backend architecture, and their specific contributions. (Topic: PROJECTS, Intent: PROJECT_DISCUSSION)
        - Index 2: CHALLENGES. The biggest technical challenge faced in that project and how they overcame it. (Topic: CHALLENGES, Intent: CHALLENGE_DISCUSSION)
        - Index 3: AI_FUNDAMENTALS. AI/Machine Learning concepts. E.g., supervised vs unsupervised learning, overfitting, bias-variance trade-off, model evaluation. (Topic: AI_FUNDAMENTALS, Intent: AI_CONCEPT_DISCUSSION)
        - Index 4: GENERATIVE_AI. LLM/Generative AI. E.g., building applications using LLMs, prompt engineering, RAG, reducing hallucinations, vector databases. (Topic: GENERATIVE_AI, Intent: GEN_AI_DISCUSSION)
        - Index 5: AUTOMATION. Automation workflows, AI operations, monitoring, model downtime, api failures. (Topic: AUTOMATION, Intent: AUTOMATION_DISCUSSION)
        - Index 6: SYSTEM_DESIGN. System design & scalability. E.g., scalable AI interview platform, handling concurrent users, optimizing performance, cost reduction. (Topic: SYSTEM_DESIGN, Intent: DESIGN_DISCUSSION)
        - Index 7: CLOSING. Assess mindset/learning, and ask: "Do you have any questions for us?" (Topic: CLOSING, Intent: CLOSING_DISCUSSION)
        
        Target Role Specificity Rules:
        If the target role ({target_role}) is related to AI, Machine Learning, Generative AI, AI Ops, or LLMs:
        - Prioritize AI/ML concepts, LLMs, prompt engineering, vector databases, RAG, automation, and AI deployment.
        - Avoid asking traditional, generic full-stack/web development questions repeatedly (such as FastAPI vs Flask, simple REST APIs, or basic databases) unless they are directly relevant to the AI infrastructure/system design.
        
        Question Diversity Rules:
        1. If 'Is Clarification Question' is true: Ask one polite clarification question about the current topic, referencing the candidate's last answer. Do not change topics.
        2. If 'Is Clarification Question' is false: Generate a new question for index {question_index}.
        3. Do NOT ask about any topic or intent that is already present in 'Previously Asked Questions' as ANSWERED or SKIPPED.
        4. Do NOT generate any question similar to the 'Rejected Questions' or 'Previously Asked Questions'.
        5. Assign a clear 'topic' and 'intent' to the question matching the Topic Flow by Index.
        6. Always speak in a professional, warm, and conversational tone.
        
        Provide the output in the following JSON format:
        {{
            "question": "The question text",
            "topic": "The topic name (e.g. INTRODUCTION, PROJECTS, CHALLENGES, AI_FUNDAMENTALS, GENERATIVE_AI, AUTOMATION, SYSTEM_DESIGN, CLOSING)",
            "intent": "The specific intent (e.g. INTRO_DISCUSSION, PROJECT_DISCUSSION, CHALLENGE_DISCUSSION, AI_CONCEPT_DISCUSSION, GEN_AI_DISCUSSION, AUTOMATION_DISCUSSION, DESIGN_DISCUSSION, CLOSING_DISCUSSION)"
        }}
        """

        # Loop to ensure similarity check passes
        rejected = []
        previous_q_texts = [pq.get("question") for pq in previous_questions] if previous_questions else []
        
        for attempt in range(3):
            try:
                if IS_DEMO_MODE:
                    mock_questions = [
                        f"Welcome {candidate_name}! Let's start the mock interview for the {target_role} position. To kick things off, could you please introduce yourself and tell me a bit about your professional background?",
                        f"Thank you for the introduction, {candidate_name}. Let's talk about projects. Looking at your background, could you detail a specific project you worked on that is relevant to this role, explaining your contribution?",
                        "What was the biggest technical challenge you faced in that project and how did you overcome it?",
                        "Let's discuss some core AI and Machine Learning concepts. How would you explain overfitting and what strategies would you use to prevent it in production?",
                        "Moving on to Generative AI. How would you design a Retrieval-Augmented Generation (RAG) system to minimize hallucinations and retrieve accurate context?",
                        "Let's talk about automation and operations. Describe a production workflow you've built, or how you would monitor an LLM application to handle API latency and model failures.",
                        "For system design: how would you design a scalable, low-latency AI interview platform capable of handling thousands of concurrent sessions?",
                        f"Thank you, {candidate_name}. We have finished the technical part of the interview. Do you have any questions for us, and what are you currently learning?"
                    ]
                    q_idx = min(question_index, len(mock_questions) - 1)
                    q_text = mock_questions[q_idx]
                    
                    if is_clarification:
                        q_text = f"Could you please expand or clarify on that response, {candidate_name}?"
                        
                    topics = ["INTRODUCTION", "PROJECTS", "CHALLENGES", "AI_FUNDAMENTALS", "GENERATIVE_AI", "AUTOMATION", "SYSTEM_DESIGN", "CLOSING"]
                    intents = ["INTRO_DISCUSSION", "PROJECT_DISCUSSION", "CHALLENGE_DISCUSSION", "AI_CONCEPT_DISCUSSION", "GEN_AI_DISCUSSION", "AUTOMATION_DISCUSSION", "DESIGN_DISCUSSION", "CLOSING_DISCUSSION"]
                    
                    return {
                        "question": q_text,
                        "topic": topics[q_idx],
                        "intent": intents[q_idx]
                    }

                response_data = cls._call_llm_json(prompt)
                new_q = response_data.get("question", "")
                
                # Check similarity unless it's a clarification or intro/closing
                is_intro_or_closing = question_index == 0 or question_index == 7
                if not is_clarification and not is_intro_or_closing and cls._is_too_similar(new_q, previous_q_texts):
                    logger.warning(f"Generated question was too similar to previous questions: '{new_q}'. Rejecting and retrying.")
                    rejected.append(new_q)
                    # Reconstruct prompt with rejected questions
                    rejected_str = ", ".join([f'"{rq}"' for rq in rejected])
                    prompt = prompt.replace(f"Rejected Questions (due to being too similar to previous questions):\n{rejected_str if len(rejected) > 1 else 'None'}", f"Rejected Questions (due to being too similar to previous questions):\n{rejected_str}")
                    continue
                
                return response_data
            except Exception as e:
                logger.error(f"Error in generate_interview_question attempt {attempt}: {str(e)}")
                
        # If all attempts fail or are similar, return a default fallback
        fallback_questions = [
            f"Welcome {candidate_name} to the AI Interview for the {target_role} position. Please introduce yourself.",
            "Tell me about a project on your resume that relates to this role and your exact contributions.",
            "What was the biggest technical challenge you faced in that project and how did you overcome it?",
            "What is overfitting and how can it be prevented?",
            "How would you build an AI-powered application using LLMs and reduce hallucinations?",
            "Describe an automation workflow you have built or how you monitor AI in production.",
            "How would you design a scalable AI interview platform?",
            f"We have finished the interview. Do you have any questions for us, {candidate_name}?"
        ]
        q_idx = min(question_index, len(fallback_questions) - 1)
        topics = ["INTRODUCTION", "PROJECTS", "CHALLENGES", "AI_FUNDAMENTALS", "GENERATIVE_AI", "AUTOMATION", "SYSTEM_DESIGN", "CLOSING"]
        intents = ["INTRO_DISCUSSION", "PROJECT_DISCUSSION", "CHALLENGE_DISCUSSION", "AI_CONCEPT_DISCUSSION", "GEN_AI_DISCUSSION", "AUTOMATION_DISCUSSION", "DESIGN_DISCUSSION", "CLOSING_DISCUSSION"]
        return {
            "question": fallback_questions[q_idx],
            "topic": topics[q_idx],
            "intent": intents[q_idx]
        }


    @classmethod
    def generate_concluding_response(
        cls,
        target_role: str,
        candidate_answer: str,
        candidate_name: str = "Candidate"
    ) -> str:
        """
        Generates a final response answering the candidate's final question and concluding.
        """
        if IS_DEMO_MODE:
            answer_lower = candidate_answer.lower()
            if "next step" in answer_lower or "process" in answer_lower or "what after" in answer_lower:
                return f"That's a great question, {candidate_name}. Our HR team will review the evaluation report and get back to you within 3 business days regarding the next steps. Thank you so much for your time today, and have a wonderful day!"
            elif "no" in answer_lower or "none" in answer_lower or "thank" in answer_lower:
                return f"You're very welcome, {candidate_name}. Thank you for your time today, it was a pleasure speaking with you. We will review your answers and get back to you soon. Have a great day!"
            else:
                return f"Thank you for that question, {candidate_name}. We will review the session and get back to you soon regarding the next steps! Thank you for your time today!"

        prompt = f"""
        You are an AI Interviewer concluding a screening interview for a {target_role} position.
        Candidate Name: {candidate_name}
        
        At the end of the interview, you asked the candidate if they had any questions, and they replied with:
        "{candidate_answer}"
        
        Write a professional, warm response in English that:
        1. Answers their question directly or acknowledges their comment.
        2. Concludes the interview and thanks them for their time.
        3. States that the team will get back to them soon.
        4. Keeps the response concise (2-4 sentences max).
        """

        try:
            return cls._call_llm_text(prompt)
        except Exception as e:
            logger.error(f"Error in generate_concluding_response: {str(e)}")
            return f"Thank you for your response, {candidate_name}. We will review the session and get back to you soon. Thank you for your time!"

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
        
        Candidate's Resume/Profile Context:
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
            return cls._call_llm_json(prompt)
        except Exception as e:
            logger.error(f"Error in generate_final_feedback: {str(e)}")
            # Return high-quality mock feedback with a key notification instead of a blank report
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
                "summary": f"The candidate performed well in the interview for the {target_role} position. Note: The live AI evaluation encountered an error, displaying mock analysis.",
                "strengths": [
                    "Strong project ownership and clear articulation of development challenges.",
                    "Good understanding of application scalability, security, and clean code principles.",
                    "Constructive approach to handling team conflicts and peer collaboration."
                ],
                "improvements": [
                    "Please verify your GROQ_API_KEY or GEMINI_API_KEY environment variable if you want real-time AI-powered evaluations.",
                    "Could use the STAR method (Situation, Task, Action, Result) more rigorously to quantify achievements.",
                    "Could dive deeper into specific performance optimization techniques when discussing scaling."
                ],
                "technical_skills_rating": 8,
                "technical_skills_comments": "Strong technical foundation. Candidate was able to explain architectural designs, security measures, and testing strategies clearly.",
                "communication_skills_rating": 9,
                "communication_skills_comments": "Excellent communication skills. Answers were well-structured, polite, and directly addressed the questions asked.",
                "qa_breakdown": qa_breakdown
            }

    @classmethod
    def transcribe_audio(cls, file_path: str) -> str:
        """
        Transcribes audio using Groq Whisper Large V3.
        Falls back to a demo text warning if Groq is not configured.
        """
        if not groq_client:
            logger.warning("Groq client not initialized for transcribe_audio. Returning mock transcription.")
            return "This is a mock transcription because Groq API key is not configured."
            
        try:
            logger.info(f"Uploading and transcribing audio file '{file_path}' via Groq Whisper...")
            with open(file_path, "rb") as audio_file:
                response = groq_client.audio.transcriptions.create(
                    file=(os.path.basename(file_path), audio_file.read()),
                    model="whisper-large-v3",
                    response_format="json"
                )
                transcript = response.text if hasattr(response, "text") else response.get("text", "")
                logger.info(f"Successfully transcribed audio. Length: {len(transcript)} chars.")
                return transcript
        except Exception as e:
            logger.error(f"Error calling Groq Whisper API: {str(e)}")
            raise e

