from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String)
    content = Column(Text, nullable=False)
    post_type = Column(String, default="text")  # text|carousel|poll|article|document|image
    hook = Column(Text)
    hashtags = Column(Text)  # JSON array
    call_to_action = Column(Text)
    status = Column(String, default="draft")  # draft|scheduled|published|failed
    ai_score = Column(Integer, default=0)
    score_breakdown = Column(Text)  # JSON
    generation_prompt_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=True)
    word_count = Column(Integer, default=0)
    estimated_read_time = Column(Integer, default=0)
    scheduled_at = Column(DateTime)
    published_at = Column(DateTime)
    linkedin_post_id = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="posts")
    metrics = relationship("PostMetrics", back_populates="post")
    generation_prompt = relationship("PromptVersion", foreign_keys=[generation_prompt_id])


class PostMetrics(Base):
    __tablename__ = "post_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    scraped_at = Column(DateTime, server_default=func.now())
    impressions = Column(Integer, default=0)
    reactions = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    profile_views = Column(Integer, default=0)
    follows_gained = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    top_reaction_type = Column(String)

    post = relationship("Post", back_populates="metrics")


class ContentIdea(Base):
    __tablename__ = "content_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic = Column(Text)
    angle = Column(Text)
    post_type = Column(String, default="text")
    hook_options = Column(Text)  # JSON array of 5 hooks
    content_pillars = Column(Text)  # JSON array
    status = Column(String, default="idea")  # idea|in_progress|rejected|used
    source = Column(String, default="ai_generated")  # ai_generated|scraped_trend|manual
    created_at = Column(DateTime, server_default=func.now())
