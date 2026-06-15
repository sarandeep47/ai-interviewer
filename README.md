# AI Interviewer: Mock Screening Suite

An advanced, interactive mock screening application designed to simulate high-fidelity technical interviews using LLMs. It features a React frontend and a FastAPI backend, supporting PDF/Image resume uploads, client-side/backend OCR fallbacks, real-time evaluation, database session management, and synchronized voice interaction (Text-to-Speech & Speech-to-Text).

---

## 🏗️ Architecture Overview

The project is structured as a monorepo consisting of:
1. **Frontend (`/frontend`)**: React + TypeScript + Vite, using custom CSS for a glassmorphic design and Lucide React icons.
2. **Backend (`/backend`)**: FastAPI server using Uvicorn, SQLAlchemy ORM, SQLite (local development) / PostgreSQL database, and Google Generative AI (Gemini SDK).
3. **Orchestration**: A PowerShell startup script (`start.ps1`) to run both servers concurrently in separate windows.

---

## 🛠️ Complete System Rules & Logic

The system operates under strict rules defined across its service layers and user interface:

### 1. Resume Parsing & OCR Fallbacks
* **Digital PDFs**: Extracted directly using the `pypdf` library on the backend.
* **Backend OCR**: If the extracted text has a length of less than 150 characters (typical of scanned files), the backend uses `PyMuPDF` (`fitz`) to render pages as high-resolution images and runs OCR using **Tesseract** (falling back to **PaddleOCR**).
* **Client-Side OCR Fallback**: If backend OCR fails or requests client-side OCR (notifying the client with `client_ocr_required`), the React frontend activates **Tesseract.js** to scan the document directly in the user's browser. This removes the need for candidates to install system-level Tesseract binaries locally.

### 2. Resume Profile Extraction Rules
* **Gemini SDK Extraction**: When `GEMINI_API_KEY` is configured, it sends the parsed resume text to the model `gemini-flash-latest` with a strict JSON schema output instruction to extract:
  * `candidate_name`
  * `candidate_email`
  * `skills` (relevant to the target role)
  * `experience_level` (Entry-level, Mid-level, Senior, or Lead)
  * `summary_evaluation` (2-3 sentences overview)
* **Local Parsing Fallbacks (Demo Mode)**: If running in Demo Mode or if the API call fails, the system applies local rules:
  * **Email**: Extracted via Regex match (`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`).
  * **Candidate Name**: Iterates through the first 6 lines of text, skipping common section headers/location keywords. Checks for lines of 1-4 capitalized words to determine the name.
  * **Skills**: Performs a lowercase search for common keywords (e.g., react, typescript, python) and picks up to 6 matches.
  * **Experience Level**: Scans for seniority keywords (e.g., senior, lead, architect -> `Senior`; junior, intern, student -> `Entry-level`), defaulting to `Mid-level`.

### 3. Interview Flow & Question Progression Rules
The interview operates on a strict **5-Question Flow** matching specific sequential indices (0 to 4):
* **Index 0 (Introduction)**: The AI greets the candidate by their extracted name and invites them to introduce themselves.
* **Index 1 (Project Probing)**: Evaluates the candidate's introduction. If a project was mentioned, it probes details about it. If not, it extracts a project from the parsed resume text and asks the candidate to describe their contribution.
* **Index 2 (Core Role Concepts)**: Asks role-specific conceptual questions (e.g., FastAPI vs standard REST API design patterns).
* **Index 3 (General Engineering Practices)**: Probes technical topics outside projects (e.g., testing, databases, security, performance, or system design).
* **Index 4 (Closing/Goodbye)**: Concludes the interview, asks the candidate if they have any final questions, and thanks them for their time.

### 4. Conversation Continuity & Answer Validation Rules
* **Personalized Address**: The AI refers to the candidate by their extracted/provided name throughout the interview instead of generic greeting terms.
* **Answer Relevance & Validation**:
  * For each response, the AI checks if the user's reply is relevant and sufficient.
  * If the response is extremely brief, empty, or avoids the question, the AI sets `is_answer_acceptable` to `false` and generates a polite follow-up nudge without advancing the question index.
* **"I don't know" / Skill Bypass**: If the candidate states they do not know the answer (e.g., "no idea", "i don't know") for index > 0, the AI sets `is_answer_acceptable` to `true`, acknowledges it politely ("Okay, let's leave that question. Let's move on."), and transitions to the next index flow.

### 5. Voice Interaction, Synchronization & Timer Rules
To provide a seamless, non-overlapping voice experience:
* **TTS (Text-to-Speech)**: Uses the browser's Web Speech API (`SpeechSynthesis`) to vocalize AI questions. It strips markdown symbols (like `*`, `#`, `_`, `` ` ``) before speaking.
* **Strict TTS/STT Sequencing**: To prevent the browser microphone from recording its own speaker outputs, speech recognition and timers are strictly disabled while the AI is speaking. Recording starts only after the TTS `onend` callback is triggered.
* **Idle Timer (10 seconds)**:
  * Starts counting down once the AI finishes speaking and the candidate remains silent.
  * **Question 0 (Intro)**: Nudges the user ("Are you there, [Name]?") and plays a TTS nudge.
  * **Question > 0**: Plays a skip phrase ("Okay, let's leave that question. Let's move on.") and automatically calls `/api/sessions/{id}/next-question` with the answer set to `"Candidate did not respond"`.
* **Speech Recording Timer (15 seconds)**:
  * While the candidate is speaking/recording, a 15-second countdown is displayed.
  * If the countdown reaches zero, the recorder turns off and automatically submits whatever has been captured. If nothing was transcribed, it submits `"Candidate did not respond"`.

### 6. Evaluation & Reporting Rules
Upon completing the final question, the backend generates a detailed assessment JSON structured as follows:
* `overall_score` (0-100)
* `verdict` (`Strong Hire`, `Hire`, `Borderline`, `No Hire`)
* `summary` (3-4 sentences summarizing candidate performance)
* `strengths` & `improvements` (detailed list arrays)
* `technical_skills_rating` & `communication_skills_rating` (out of 10) with comments
* `qa_breakdown` (mapping each question, answer, and specific evaluation feedback)

---

## 📁 Database Schema

Configured via SQLAlchemy in `database.py`:

```
┌────────────────────────────────────────┐
│           InterviewSession             │
├────────────────────────────────────────┤
│ - id (String, PK)                      │
│ - candidate_name (String)              │
│ - candidate_email (String)             │
│ - target_role (String)                 │
│ - resume_text (Text)                   │
│ - current_question_index (Integer)     │
│ - total_questions (Integer)            │
│ - status (String: started/completed)   │
│ - created_at (DateTime)                │
│ - final_feedback (JSON)                │
└───────────────────┬────────────────────┘
                    │ 1
                    │
                    │ 1..* (Cascade Delete)
┌───────────────────▼────────────────────┐
│             ChatMessage                │
├────────────────────────────────────────┤
│ - id (Integer, PK, Autoincrement)      │
│ - session_id (String, FK -> Session)   │
│ - sender (String: 'ai' / 'candidate')  │
│ - message (Text)                       │
│ - timestamp (DateTime)                 │
│ - evaluation (Text)                    │
└────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites
* **Python 3.10+**
* **Node.js 18+**
* Tesseract OCR installed on the system (Optional, only for scanned document backend OCR fallback; browser OCR uses Tesseract.js).

### Setup Environment
1. In the `/backend` directory, create a `.env` file containing:
   ```env
   GEMINI_API_KEY="your-api-key-here"
   DATABASE_URL="sqlite:///interview_db.db"
   ```
   *If `GEMINI_API_KEY` is omitted, the app will run in **Demo Mode** with mock responses.*

2. Install backend dependencies:
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

### Running the Project
From the root directory, launch both applications using the startup script:
```powershell
.\start.ps1
```
* **Frontend**: `http://localhost:5173`
* **Backend API**: `http://localhost:8000`
