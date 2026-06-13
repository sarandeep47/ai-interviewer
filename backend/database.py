import os
from datetime import datetime
import json
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Read database URL, fallback to default SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///interview_db.db")

# Conditionally configure connection arguments (only SQLite requires check_same_thread)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(String, primary_key=True, index=True)
    candidate_name = Column(String, nullable=True)
    candidate_email = Column(String, nullable=True)
    target_role = Column(String, nullable=False, default="Software Engineer")
    resume_text = Column(Text, nullable=True)
    current_question_index = Column(Integer, default=0)
    total_questions = Column(Integer, default=5)
    status = Column(String, default="started")  # started, ongoing, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    final_feedback = Column(JSON, nullable=True)  # Will store the final evaluation JSON

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String, nullable=False)  # 'ai' or 'candidate'
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    evaluation = Column(Text, nullable=True)  # Stores brief AI assessment of the candidate's answer

    session = relationship("InterviewSession", back_populates="messages")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
