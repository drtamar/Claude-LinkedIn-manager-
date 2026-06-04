import json
from sqlalchemy.orm import Session
from app.models.content import Post, PostMetrics, ContentIdea
from app.models.profile import UserProfile
from app.services.profile_service import user_profile_to_dict
from app.ai.modules.content_ai import generate_hashtags, score_post


def get_posts(db: Session, user_id: int, skip: int = 0, limit: int = 20) -> list[Post]:
    return db.query(Post).filter(Post.user_id == user_id).order_by(
        Post.created_at.desc()
    ).offset(skip).limit(limit).all()


def get_post(db: Session, post_id: int, user_id: int) -> Post | None:
    return db.query(Post).filter(Post.id == post_id, Post.user_id == user_id).first()


def create_post(db: Session, user_id: int, data: dict) -> Post:
    content = data.get("content", "")
    word_count = len(content.split())
    post = Post(
        user_id=user_id,
        title=data.get("title"),
        content=content,
        post_type=data.get("post_type", "text"),
        hook=data.get("hook"),
        hashtags=json.dumps(data.get("hashtags", [])),
        call_to_action=data.get("call_to_action"),
        word_count=word_count,
        estimated_read_time=max(1, word_count // 200),
        status="draft",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def update_post(db: Session, post: Post, data: dict) -> Post:
    for key, value in data.items():
        if hasattr(post, key):
            if key == "hashtags" and isinstance(value, list):
                setattr(post, key, json.dumps(value))
            else:
                setattr(post, key, value)
    db.commit()
    db.refresh(post)
    return post


def delete_post(db: Session, post: Post) -> None:
    db.delete(post)
    db.commit()


async def score_and_save(db: Session, post: Post, user_profile: UserProfile) -> Post:
    profile_dict = user_profile_to_dict(user_profile)
    score_data = await score_post(post.content, post.post_type, profile_dict)
    post.ai_score = score_data.get("total_score", 0)
    post.score_breakdown = json.dumps(score_data)
    db.commit()
    db.refresh(post)
    return post


def get_top_performing_posts(db: Session, user_id: int, limit: int = 5) -> list[Post]:
    from sqlalchemy import desc
    return (
        db.query(Post)
        .join(PostMetrics)
        .filter(Post.user_id == user_id, Post.status == "published")
        .order_by(desc(PostMetrics.engagement_rate))
        .limit(limit)
        .all()
    )
