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

# SQLAlchemy requires postgresql:// dialect prefix instead of postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
    total_questions = Column(Integer, default=8)
    status = Column(String, default="started")  # started, ongoing, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    final_feedback = Column(JSON, nullable=True)  # Will store the final evaluation JSON
    
    # Context optimization columns
    experience_level = Column(String, nullable=True)
    skills = Column(Text, nullable=True)
    resume_summary = Column(Text, nullable=True)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String, nullable=False)  # 'ai' or 'candidate'
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    evaluation = Column(Text, nullable=True)  # Stores brief AI assessment of the candidate's answer
    
    # Question memory and state machine tracking columns
    topic = Column(String, nullable=True)
    intent = Column(String, nullable=True)
    status = Column(String, nullable=True)  # ANSWERED, IRRELEVANT, SKIPPED, I_DONT_KNOW
    clarification_count = Column(Integer, default=0, nullable=True)

    session = relationship("InterviewSession", back_populates="messages")

import logging
logger = logging.getLogger(__name__)

def init_db():
    global engine, SessionLocal
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        logger.warning("Falling back to local SQLite database 'interview_db.db' for development...")
        fallback_url = "sqlite:///interview_db.db"
        engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Local SQLite database initialized as fallback.")

    # Dynamic migrations: alter tables to add columns if they don't exist
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        
        # 1. Update interview_sessions
        session_columns = [col['name'] for col in inspector.get_columns('interview_sessions')]
        new_session_cols = {
            "experience_level": "VARCHAR",
            "skills": "TEXT",
            "resume_summary": "TEXT"
        }
        
        # 2. Update chat_messages
        chat_columns = [col['name'] for col in inspector.get_columns('chat_messages')]
        new_chat_cols = {
            "topic": "VARCHAR",
            "intent": "VARCHAR",
            "status": "VARCHAR",
            "clarification_count": "INTEGER"
        }
        
        with engine.connect() as conn:
            # Alter interview_sessions
            for col_name, col_type in new_session_cols.items():
                if col_name not in session_columns:
                    logger.info(f"Adding column '{col_name}' to table 'interview_sessions'...")
                    conn.execute(text(f"ALTER TABLE interview_sessions ADD COLUMN {col_name} {col_type}"))
            
            # Alter chat_messages
            for col_name, col_type in new_chat_cols.items():
                if col_name not in chat_columns:
                    logger.info(f"Adding column '{col_name}' to table 'chat_messages'...")
                    conn.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {col_name} {col_type}"))
                    
            conn.commit()
            logger.info("Database schema check/migration completed successfully.")
    except Exception as e:
        logger.error(f"Error during dynamic schema check/migration: {str(e)}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

