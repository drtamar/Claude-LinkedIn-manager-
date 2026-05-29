from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class QuestionnaireSession(Base):
    __tablename__ = "questionnaire_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="in_progress")  # in_progress|completed|abandoned
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=35)
    answers = Column(Text, default="{}")  # JSON step_id: answer pairs
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="questionnaire_sessions")
    answers_log = relationship("QuestionnaireAnswer", back_populates="session")


class QuestionnaireAnswer(Base):
    __tablename__ = "questionnaire_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("questionnaire_sessions.id"), nullable=False)
    step_id = Column(String, nullable=False)
    question_text = Column(Text)
    answer_value = Column(Text)
    answer_type = Column(String, default="text")  # text|select|multi_select|scale|boolean
    answered_at = Column(DateTime, server_default=func.now())

    session = relationship("QuestionnaireSession", back_populates="answers_log")
