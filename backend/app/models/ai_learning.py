from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module = Column(String, nullable=False, index=True)  # e.g. "content.post_writer"
    version = Column(Integer, default=1)
    prompt_template = Column(Text, nullable=False)
    system_message = Column(Text)
    model = Column(String, default="claude-opus-4-8")
    temperature = Column(Float, default=0.7)
    performance_score = Column(Float, default=0.0)
    sample_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    parent_version_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=True)
    change_reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    retired_at = Column(DateTime)


class LearningCycle(Base):
    __tablename__ = "learning_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cycle_date = Column(DateTime, server_default=func.now())
    modules_analyzed = Column(Text)  # JSON array
    insights = Column(Text)  # JSON
    improvements_made = Column(Integer, default=0)
    avg_before_score = Column(Float, default=0.0)
    avg_after_score = Column(Float, default=0.0)
    full_report = Column(Text)
    status = Column(String, default="running")  # running|completed|failed

    user = relationship("User", back_populates="learning_cycles")


class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_type = Column(String, nullable=False)  # post_publish|connection_send|analytics_scrape|profile_scrape
    status = Column(String, default="queued")  # queued|running|completed|failed|cancelled
    payload = Column(Text)  # JSON
    result = Column(Text)  # JSON
    error_message = Column(Text)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    queued_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    next_retry_at = Column(DateTime)

    user = relationship("User", back_populates="automation_jobs")


class AlgorithmInsight(Base):
    __tablename__ = "algorithm_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    insight_type = Column(String)  # timing|hook|format|length|hashtag|engagement
    insight_data = Column(Text)  # JSON
    confidence_score = Column(Float, default=0.0)
    based_on_posts = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    generated_at = Column(DateTime, server_default=func.now())
