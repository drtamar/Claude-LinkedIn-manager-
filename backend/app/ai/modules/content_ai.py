import json
from typing import AsyncIterator
from app.ai.claude_client import complete, stream_response

POST_WRITER_SYSTEM = """You are a top LinkedIn content strategist. You write posts that go viral because they:
1. Open with an irresistible hook (first line must stop the scroll)
2. Use extreme whitespace — one idea per paragraph, max 2-3 lines each
3. Include a clear story arc or insight progression
4. End with an engagement-driving question or CTA
5. NEVER use hashtags in the body — they go at the end
6. Optimize for mobile reading
7. Create dwell time by making readers feel they're getting real value
The LinkedIn algorithm rewards saves and comments far more than likes."""

HOOK_SYSTEM = """You are a LinkedIn hook master. Hooks are the ONLY thing that determines if a post gets read.
Generate hooks under 25 words each. They must create pattern interruption and irresistible curiosity.
Return ONLY valid JSON."""

HASHTAG_SYSTEM = """You are a LinkedIn hashtag strategist.
Mix: 2 broad (100k+ followers), 3 medium (10k-100k), 2 niche (<10k).
Hashtags should be relevant, not spammy. No more than 7 total.
Return ONLY valid JSON."""

SCORER_SYSTEM = """You are a LinkedIn algorithm expert. Score posts based on what actually drives
LinkedIn's algorithm: early engagement velocity, comment-to-like ratio, dwell time signals, share potential.
Return ONLY valid JSON with specific, actionable feedback."""

IDEAS_SYSTEM = """You are a LinkedIn content strategist generating content ideas.
Ideas must be specific, timely, and resonant for the user's audience.
Each idea should have clear viral potential and align with LinkedIn's content trends.
Return ONLY valid JSON."""


async def generate_hooks(topic: str, user_profile: dict) -> list[dict]:
    prompt = f"""Topic: {topic}
User's industry: {user_profile.get('industry', '')}
Target audience: {json.dumps(user_profile.get('target_audience', {}))}
User's tone: {user_profile.get('content_tone', 'professional')}

Generate 5 LinkedIn hooks for this topic, each using a different formula:
1. Contrarian statement (challenges common belief)
2. Specific number (credibility through specificity)
3. Story opener (personal moment or observation)
4. Bold claim (strong opinion or prediction)
5. Question (creates immediate curiosity)

Return JSON:
{{
  "hooks": [
    {{"type": "contrarian", "hook": "...", "why_it_works": "..."}},
    {{"type": "number", "hook": "...", "why_it_works": "..."}},
    {{"type": "story", "hook": "...", "why_it_works": "..."}},
    {{"type": "claim", "hook": "...", "why_it_works": "..."}},
    {{"type": "question", "hook": "...", "why_it_works": "..."}}
  ]
}}"""

    result = await complete(prompt, system=HOOK_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=1024)
    try:
        data = json.loads(result)
        return data.get("hooks", [])
    except json.JSONDecodeError:
        return []


async def stream_post(
    topic: str,
    post_type: str,
    hook: str,
    user_profile: dict,
    top_performing_examples: list = None,
    avoid_patterns: list = None,
) -> AsyncIterator[str]:
    examples_text = ""
    if top_performing_examples:
        examples_text = f"\n\nHigh-performing posts from this user (study their pattern):\n" + \
                        "\n---\n".join(top_performing_examples[:2])

    avoid_text = ""
    if avoid_patterns:
        avoid_text = f"\n\nPatterns to AVOID (low performers): {json.dumps(avoid_patterns)}"

    prompt = f"""Write a LinkedIn {post_type} post.

Hook to use (MUST be the first line exactly): {hook}

Topic: {topic}
User's tone: {user_profile.get('content_tone', 'professional')}
Target audience: {json.dumps(user_profile.get('target_audience', {}))}
Industry: {user_profile.get('industry', '')}
Brand voice: {user_profile.get('brand_voice_notes', 'clear and direct')}
{examples_text}
{avoid_text}

Post format requirements:
- First line = the hook provided (do not change it)
- Then blank line
- 150-300 words total
- Max 2-3 sentences per paragraph
- One blank line between each paragraph
- End with a question that drives comments
- After the post, add on a new line: "HASHTAGS:" followed by 5-7 hashtags

Write the full post now:"""

    async for token in stream_response(prompt, system=POST_WRITER_SYSTEM, model="claude-opus-4-8", max_tokens=1024):
        yield token


async def generate_hashtags(topic: str, industry: str, content: str = "") -> list[str]:
    prompt = f"""Topic: {topic}
Industry: {industry}
Post content preview: {content[:200] if content else ""}

Generate 7 optimized LinkedIn hashtags. Mix:
- 2 broad hashtags (huge audiences, general relevance)
- 3 medium hashtags (specific to topic/industry)
- 2 niche hashtags (specific community, less competition)

Return JSON: {{"hashtags": ["#hashtag1", "#hashtag2", ...]}}"""

    result = await complete(prompt, system=HASHTAG_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=256)
    try:
        data = json.loads(result)
        return data.get("hashtags", [])
    except json.JSONDecodeError:
        return []


async def score_post(content: str, post_type: str, user_profile: dict) -> dict:
    prompt = f"""LinkedIn Post to Score:
---
{content}
---
Post type: {post_type}
Target audience: {json.dumps(user_profile.get('target_audience', {}))}

Score 0-100 across these dimensions:
- Hook strength (25pts): Does the first line stop the scroll? Create curiosity?
- Readability (20pts): Mobile-friendly? Short paragraphs? Easy to scan?
- Engagement triggers (20pts): Does it provoke comments? Strong ending question?
- Value delivery (20pts): Does it teach, inspire, or entertain the target audience?
- CTA quality (10pts): Clear next action?
- Keyword relevance (5pts): Industry terms present?

Return JSON:
{{
  "total_score": 0,
  "breakdown": {{
    "hook": {{"score": 0, "max": 25, "feedback": "specific feedback"}},
    "readability": {{"score": 0, "max": 20, "feedback": "..."}},
    "engagement": {{"score": 0, "max": 20, "feedback": "..."}},
    "value": {{"score": 0, "max": 20, "feedback": "..."}},
    "cta": {{"score": 0, "max": 10, "feedback": "..."}},
    "keywords": {{"score": 0, "max": 5, "feedback": "..."}}
  }},
  "improvements": ["specific improvement 1", "specific improvement 2"],
  "estimated_engagement_level": "low|medium|high|viral"
}}"""

    result = await complete(prompt, system=SCORER_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=1024)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"total_score": 50, "breakdown": {}, "improvements": []}


async def stream_content_ideas(user_profile: dict, count: int = 10) -> AsyncIterator[str]:
    prompt = f"""Generate {count} specific, viral-potential LinkedIn content ideas.

User profile:
- Industry: {user_profile.get('industry', '')}
- Target audience: {json.dumps(user_profile.get('target_audience', {}))}
- Content pillars: {json.dumps(user_profile.get('content_pillars', []))}
- Tone: {user_profile.get('content_tone', 'professional')}
- Goals: {json.dumps(user_profile.get('goals', []))}

For each idea, provide:
1. Specific topic (not generic)
2. The unique angle that makes it interesting
3. Best post format for this idea
4. Why this will resonate with their audience
5. A sample hook

Format as a numbered list. Be specific — no generic "share your expertise" ideas.
Think about: contrarian takes, personal stories, data insights, behind-the-scenes,
lessons learned, industry myths debunked, hot takes, "I wish someone told me" posts."""

    async for token in stream_response(prompt, system=IDEAS_SYSTEM, model="claude-opus-4-8", max_tokens=2048):
        yield token
