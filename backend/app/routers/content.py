import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import content_service as svc
from app.services.profile_service import get_user_profile, user_profile_to_dict
from app.ai.modules.content_ai import (
    generate_hooks, stream_post, stream_content_ideas,
    generate_hashtags, score_post
)

router = APIRouter(prefix="/api/content", tags=["content"])


class CreatePostRequest(BaseModel):
    title: Optional[str] = None
    content: str
    post_type: str = "text"
    hook: Optional[str] = None
    hashtags: list[str] = []
    call_to_action: Optional[str] = None


class GeneratePostRequest(BaseModel):
    topic: str
    post_type: str = "text"
    hook: Optional[str] = None


class HookRequest(BaseModel):
    topic: str


class HashtagRequest(BaseModel):
    topic: str
    content: Optional[str] = None


@router.get("/posts")
def list_posts(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    posts = svc.get_posts(db, current_user.id, skip, limit)
    return [
        {
            "id": p.id,
            "title": p.title,
            "content": p.content[:200],
            "post_type": p.post_type,
            "status": p.status,
            "ai_score": p.ai_score,
            "hashtags": json.loads(p.hashtags or "[]"),
            "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in posts
    ]


@router.post("/posts")
def create_post(
    req: CreatePostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = svc.create_post(db, current_user.id, req.model_dump())
    return {"id": post.id, "status": post.status}


@router.get("/posts/{post_id}")
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = svc.get_post(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "post_type": post.post_type,
        "hook": post.hook,
        "hashtags": json.loads(post.hashtags or "[]"),
        "call_to_action": post.call_to_action,
        "status": post.status,
        "ai_score": post.ai_score,
        "score_breakdown": json.loads(post.score_breakdown or "{}"),
        "word_count": post.word_count,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
    }


@router.put("/posts/{post_id}")
def update_post(
    post_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = svc.get_post(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    svc.update_post(db, post, payload)
    return {"updated": True}


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = svc.get_post(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    svc.delete_post(db, post)
    return {"deleted": True}


@router.post("/posts/{post_id}/score")
async def score_post_endpoint(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = svc.get_post(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    user_profile = get_user_profile(db, current_user.id)
    post = await svc.score_and_save(db, post, user_profile)
    return {
        "ai_score": post.ai_score,
        "score_breakdown": json.loads(post.score_breakdown or "{}"),
    }


@router.post("/generate/hooks")
async def get_hooks(
    req: HookRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    profile_dict = user_profile_to_dict(user_profile_obj) if user_profile_obj else {}
    hooks = await generate_hooks(req.topic, profile_dict)
    return {"hooks": hooks}


@router.post("/generate/post")
async def generate_post_stream(
    req: GeneratePostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    profile_dict = user_profile_to_dict(user_profile_obj) if user_profile_obj else {}

    hook = req.hook
    if not hook:
        hooks = await generate_hooks(req.topic, profile_dict)
        hook = hooks[0]["hook"] if hooks else req.topic

    top_posts = svc.get_top_performing_posts(db, current_user.id, limit=3)
    top_examples = [p.content[:300] for p in top_posts]

    async def stream():
        full_text = ""
        async for token in stream_post(
            topic=req.topic,
            post_type=req.post_type,
            hook=hook,
            user_profile=profile_dict,
            top_performing_examples=top_examples,
        ):
            full_text += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/generate/hashtags")
async def get_hashtags(
    req: HashtagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    industry = user_profile_obj.industry if user_profile_obj else ""
    hashtags = await generate_hashtags(req.topic, industry, req.content or "")
    return {"hashtags": hashtags}


@router.post("/ideas/generate")
async def generate_ideas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    profile_dict = user_profile_to_dict(user_profile_obj) if user_profile_obj else {}

    async def stream():
        async for token in stream_content_ideas(profile_dict):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
