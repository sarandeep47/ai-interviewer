# AI Interviewer: Mock Screening Suite

An advanced, interactive mock screening application that simulates high-fidelity technical interviews using LLMs. Features a React frontend and FastAPI backend, with PDF/Image resume uploads, client-side/backend OCR fallbacks, real-time evaluation, database session management, and synchronized voice interaction (TTS and STT).

---

## Architecture Overview

Monorepo structure:

1. **Frontend (`/frontend`)**: React 19 + TypeScript + Vite, custom CSS glassmorphic design, Lucide React icons.
2. **Backend (`/backend`)**: FastAPI + Uvicorn, SQLAlchemy ORM, SQLite (dev) / PostgreSQL (prod), dual-LLM -- **Groq** (primary, low-latency) and **Google Gemini** (fallback).
3. **Orchestration**: PowerShell `start.ps1` runs both servers in separate windows.

---

## System Rules and Logic

### 1. Resume Parsing and OCR Fallbacks

- **Digital PDFs**: Extracted via `pypdf`.
- **File Size Limit**: Uploads over **10 MB** are rejected with a `413` error.
- **Backend OCR**: If extracted text < 150 chars, `PyMuPDF` renders pages as images and runs OCR via **Tesseract** (fallback: **PaddleOCR**).
- **Client-Side OCR Fallback**: If backend OCR fails or returns `client_ocr_required`, React activates **Tesseract.js** in-browser.

### 2. LLM Provider Strategy

Dual-LLM waterfall:

- **Groq** (`openai/gpt-oss-120b` default): primary for conversation (low latency).
- **Gemini** (`gemini-2.5-flash` default): primary for resume extraction; fallback for conversation.
- Override via `GROQ_MODEL` / `GEMINI_MODEL` env vars.
- If neither key is set: **Demo Mode** with mock responses.

Resume extraction fields: `candidate_name`, `candidate_email`, `skills`, `experience_level`, `summary_evaluation`.

Local Parsing Fallbacks (Demo Mode or LLM failure):

- Email: regex match.
- Name: first 6 lines, 1-4 capitalized words, skips headers/locations.
- Skills: curated keyword scan (up to 6 matches).
- Experience: senior/lead -> Senior; junior/intern -> Entry-level; else Mid-level.

### 3. Interview Flow -- 8-Question State Machine (indices 0-7)

| Index | Stage | Description |
|---|---|---|
| 0 | Introduction | Welcome candidate, ask for self-introduction. |
| 1 | Projects | Walk through a project, architecture, contributions. |
| 2 | Challenges | Biggest technical challenge and resolution. |
| 3 | AI Fundamentals | ML concepts -- overfitting, bias-variance, evaluation. |
| 4 | Generative AI | LLMs, prompt engineering, RAG, hallucinations, vector DBs. |
| 5 | Automation | AI ops, monitoring, model downtime, API failure handling. |
| 6 | System Design | Scalable AI platform, concurrency, cost reduction. |
| 7 | Closing | Mindset/learning assessment and candidate questions. |

Question Diversity Rules:

- Similarity checked via SequenceMatcher ratio (>0.75) and Jaccard similarity (>0.45).
- Rejected questions fed back to LLM on each retry (up to 3 attempts).

### 4. Conversation Continuity and Answer Validation

- Personalized Address: AI uses candidate's extracted name throughout.
- Answer Status: ANSWERED, IRRELEVANT, SKIPPED, or I_DONT_KNOW.
- Clarification Logic: First IRRELEVANT triggers polite follow-up (no index advance). Second auto-advances.
- "I don't know" Bypass: Acknowledged and index advances.
- Background LLM Analysis: Fast local parsing responds immediately; BackgroundTasks updates DB with LLM metadata without blocking the user.

### 5. Voice Interaction and Timer Rules

- TTS: Browser SpeechSynthesis API. Markdown stripped before speaking.
- Strict TTS/STT Sequencing: Mic disabled while AI speaks; recording starts only after onend callback fires.
- Idle Timer (10s): After AI finishes -- Q0 nudges candidate once; Q1-7 auto-skip with "Candidate did not respond".
- Recording Timer (15s): Countdown while recording. Submits transcription (or empty fallback) on expiry.
- Mic Stream Cleanup: streamRef tracks MediaStream. All cleanup paths call getTracks().forEach(t => t.stop()) to prevent leaks.

### 6. Audio Transcription

Server-side via Groq Whisper Large V3 at POST /api/transcribe. Audio saved to temp file, transcribed, then deleted. Falls back to mock if GROQ_API_KEY not set.

### 7. Session Termination (no_show)

Frontend calls POST /api/sessions/{id}/terminate when candidate is idle before the intro. Marked no_show only if no user messages exist AND current_question_index == 0. Report endpoint returns a "Session Terminated" state instead of crashing on null feedback.

### 8. Evaluation and Reporting

After all 8 questions, the backend generates:

- overall_score (0-100)
- verdict (Strong Hire / Hire / Borderline / No Hire)
- summary, strengths, improvements (arrays)
- technical_skills_rating and communication_skills_rating (out of 10) with comments
- qa_breakdown (per-question feedback)

Session is marked "completed" ONLY AFTER generate_final_feedback() returns -- a failed LLM call will not leave the session stuck with null feedback.

---

## Database Schema

Managed via SQLAlchemy in `database.py`. Dynamic migrations run at startup; ALTER TABLE wrapped in try/except that ignores "already exists" errors (safe for SQLite and PostgreSQL).

```
InterviewSession
  id                     String PK
  candidate_name         String Nullable
  candidate_email        String Nullable
  target_role            String
  resume_text            Text Nullable
  current_question_index Integer default=0
  total_questions        Integer default=8
  status                 String: started / completed / no_show
  created_at             DateTime UTC
  final_feedback         JSON Nullable
  experience_level       String Nullable    [context optimization]
  skills                 Text Nullable      [context optimization]
  resume_summary         Text Nullable      [context optimization]
    |
    | 1-to-many CASCADE DELETE
    v
ChatMessage
  id                     Integer PK Autoincrement
  session_id             String FK -> InterviewSession
  sender                 String: ai / user
  message                Text
  timestamp              DateTime UTC
  evaluation             Text Nullable
  topic                  String Nullable    [state machine]
  intent                 String Nullable    [state machine]
  status                 String Nullable    [ANSWERED/IRRELEVANT/SKIPPED/I_DONT_KNOW]
  clarification_count    Integer Nullable
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | / | Health check; shows demo mode status. |
| GET | /api/health/ai | Tests both Groq and Gemini connections. |
| POST | /api/upload-resume | Upload PDF/image resume. Returns session_id or client_ocr_required. |
| POST | /api/start-interview | Start session with pre-parsed text (used after browser OCR). |
| POST | /api/transcribe | Transcribe audio via Groq Whisper Large V3. |
| POST | /api/sessions/{id}/next-question | Submit answer and receive next question or final feedback. |
| POST | /api/sessions/{id}/terminate | Force-terminate session as no_show. |
| GET | /api/sessions | List all completed sessions. |
| GET | /api/sessions/{id}/report | Get full feedback report and chat transcript. |
| DELETE | /api/sessions/{id} | Delete session and all associated messages. |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Tesseract OCR (optional -- only for backend OCR on scanned PDFs)

### Setup Environment

1. In `/backend`, create a `.env` file (use `.env.example` as a template):

```env
GEMINI_API_KEY=your-gemini-api-key-here
GROQ_API_KEY=your-groq-api-key-here
DATABASE_URL=sqlite:///interview_db.db
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
GROQ_MODEL=openai/gpt-oss-120b
GEMINI_MODEL=gemini-2.5-flash
```

- Omit both API keys to run in **Demo Mode**.
- `ALLOWED_ORIGINS` restricts CORS. Defaults to localhost:5173 and localhost:3000 if not set.
- `DATABASE_URL` accepts `sqlite:///` or `postgresql://` formats.

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

From the root `ai-interviewer/` directory:

```powershell
.\start.ps1
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs

### Security Notes

- Never commit your `.env` file -- it is listed in `backend/.gitignore`.
- Use `backend/.env.example` as a safe template for collaborators.
- If secrets were previously committed to git history, rotate them at the Gemini Console, Groq Console, and your database provider.
