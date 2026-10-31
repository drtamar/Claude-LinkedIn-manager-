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
    # Which channel this rendition is for (plan B3.2). One idea produces one
    # Post per assigned channel; see idea_id below.
    channel = Column(String, default="linkedin", index=True)
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
    # The channel's own id for this post, whatever that channel calls it: a
    # LinkedIn URN, a YouTube video id, a website slug.
    external_id = Column(String)
    # Kept so existing rows and any code still reading it keep working. New
    # code writes external_id; the LinkedIn adapter writes both.
    linkedin_post_id = Column(String)
    # The approved idea this rendition came from (plan B3.2). This link is
    # what makes Stage F's "Inherited" review tier possible: approve the
    # parent idea once, and its children need only the platform-fit check.
    idea_id = Column(Integer, ForeignKey("content_ideas.id"), nullable=True, index=True)
    # Set when a human approved it, so "who approved this" is answerable
    # later. Null means nothing has been approved yet.
    approved_at = Column(DateTime)
    # full | inherited | light — which review tier cleared it (plan F2).
    review_tier = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="posts")
    metrics = relationship("PostMetrics", back_populates="post")
    generation_prompt = relationship("PromptVersion", foreign_keys=[generation_prompt_id])
    idea = relationship("ContentIdea", back_populates="posts")


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
    """An idea, which is the unit she approves (plan F1).

    This table already carried the right lifecycle before Stage B; what it
    lacked was a subject and a way to point back at the research it came
    from. Approval happens here, once, and every Post pointing at this row
    inherits it.
    """

    __tablename__ = "content_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # One of app.subjects.definitions.SUBJECTS (plan B3.1). Drives audience,
    # register, reading level and which channels this idea goes to.
    subject = Column(String, index=True)
    topic = Column(Text)
    angle = Column(Text)
    post_type = Column(String, default="text")
    hook_options = Column(Text)  # JSON array of 5 hooks
    content_pillars = Column(Text)  # JSON array
    status = Column(String, default="idea")  # idea|in_progress|rejected|used
    source = Column(String, default="ai_generated")  # ai_generated|scraped_trend|manual
    # Where this came from: a DOI, or the canonical URL of the article or
    # thread. Stage C dedupes on it; the critic cites it.
    research_ref = Column(String, index=True)
    # Stage D's credibility score and its written rationale, carried on the
    # idea so every rendition of it can cite the same assessment.
    bias_score = Column(Float)
    bias_rationale = Column(Text)
    # Set when she approves the idea. One approval, many renditions (F1.1).
    approved_at = Column(DateTime)
    # Unreviewed ideas expire and return to the pool rather than forming a
    # backlog that can never be cleared (plan F4.2).
    expires_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    posts = relationship("Post", back_populates="idea")
