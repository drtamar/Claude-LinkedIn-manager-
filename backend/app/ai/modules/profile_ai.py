import json
from app.ai.claude_client import complete, stream_response
from typing import AsyncIterator

HEADLINE_SYSTEM = """You are the world's top LinkedIn headline specialist.
Headlines must: include the primary role, a unique value proposition, and a credibility signal.
Be under 220 characters. Use | or · as separators. No buzzwords like "passionate" or "guru".
Keywords matter for LinkedIn search. Return ONLY valid JSON."""

ABOUT_SYSTEM = """You are a master LinkedIn About section writer.
Use the StoryBrand framework: open with the reader's problem, position the user as the guide,
show the transformation they enable. Write in first person, short paragraphs (2-3 sentences max),
mobile-optimized. 300-500 words. End with a specific CTA. No corporate jargon. Return the section as plain text."""

EXPERIENCE_SYSTEM = """You are a LinkedIn experience section optimizer.
For each role: start with an impact statement (what changed because of this person),
use action verbs + metrics + context (X by Y% by doing Z), highlight promotions and scope growth.
Return ONLY valid JSON array."""

SKILLS_SYSTEM = """You are a LinkedIn skills strategist.
Select the 30-50 most strategic skills for this profile: mix core technical skills,
industry keywords that appear in job descriptions/connection searches, and soft skills with credibility.
Prioritize skills that appear in LinkedIn's algorithm-favored endorsement categories.
Return ONLY valid JSON array of strings."""

SCORER_SYSTEM = """You are a LinkedIn profile auditor. Score the profile 0-100 across 6 dimensions.
Return ONLY valid JSON."""


async def generate_headline(user_profile: dict, performance_hints: str = "") -> dict:
    prompt = f"""User profile:
{json.dumps(user_profile, indent=2)}

Performance hints from past data:
{performance_hints or "No prior data yet."}

Generate 3 LinkedIn headline variants. Return JSON:
{{
  "variants": [
    {{"headline": "...", "rationale": "...", "keyword_focus": ["kw1", "kw2"]}},
    {{"headline": "...", "rationale": "...", "keyword_focus": ["kw1", "kw2"]}},
    {{"headline": "...", "rationale": "...", "keyword_focus": ["kw1", "kw2"]}}
  ],
  "recommended": 0
}}"""

    result = await complete(prompt, system=HEADLINE_SYSTEM, model="claude-opus-4-8", max_tokens=1024)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"variants": [], "raw": result}


async def stream_about(user_profile: dict, headline: str) -> AsyncIterator[str]:
    prompt = f"""User profile:
{json.dumps(user_profile, indent=2)}

Their headline: {headline}

Write a powerful LinkedIn About section (300-500 words) following StoryBrand:
1. Open with their target audience's biggest pain/challenge (hook them in)
2. Empathize — show you understand the struggle
3. Position the user as the guide with authority
4. Describe the transformation/outcome
5. List 3-4 specific ways they help (bullet points)
6. End with a CTA (DM me, visit my website, connect)

Write in their voice based on: {user_profile.get('brand_voice_notes', 'professional and clear')}
Tone: {user_profile.get('content_tone', 'professional')}"""

    async for token in stream_response(prompt, system=ABOUT_SYSTEM, model="claude-opus-4-8", max_tokens=1024):
        yield token


async def generate_experience(user_profile: dict) -> dict:
    prompt = f"""User profile and achievements:
{json.dumps(user_profile, indent=2)}

Based on their career stage ({user_profile.get('career_stage', 'mid')}) and achievements,
generate optimized LinkedIn experience entries. For each role they mentioned or implied, create:
{{
  "experiences": [
    {{
      "title": "Role Title",
      "company": "Company Name",
      "duration": "Jan 2021 - Present",
      "headline": "One-line impact statement",
      "bullets": ["Achievement with metric", "Achievement with metric", "Achievement with metric"],
      "skills": ["skill1", "skill2"]
    }}
  ]
}}

Prioritize quantified achievements. Use the user's actual accomplishments from:
{json.dumps(user_profile.get('achievements', []))}"""

    result = await complete(prompt, system=EXPERIENCE_SYSTEM, model="claude-opus-4-8", max_tokens=2048)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"experiences": [], "raw": result}


async def generate_skills(user_profile: dict) -> list[str]:
    prompt = f"""User profile:
Industry: {user_profile.get('industry', '')}
Sub-industry: {user_profile.get('sub_industry', '')}
Career stage: {user_profile.get('career_stage', 'mid')}
Keywords from their profile: {json.dumps(user_profile.get('keywords', []))}
Goals: {json.dumps(user_profile.get('goals', []))}

Generate the optimal 40 LinkedIn skills for this person. Mix:
- Technical/functional skills (50%)
- Industry/domain skills (30%)
- Leadership/soft skills (20%)

Order from most to least strategic for LinkedIn search visibility.
Return JSON: {{"skills": ["skill1", "skill2", ...]}}"""

    result = await complete(prompt, system=SKILLS_SYSTEM, model="claude-opus-4-8", max_tokens=512)
    try:
        data = json.loads(result)
        return data.get("skills", [])
    except json.JSONDecodeError:
        return []


CATEGORIZE_SYSTEM = """You are a skills taxonomy expert. Group skills into clear, meaningful professional categories.
Use 4–7 categories that make sense for this person's profile.
Common categories (adapt as needed): Technical Skills, Domain Expertise, Tools & Platforms,
Leadership & Management, Sales & Business Development, Data & Analytics, Soft Skills, Languages, etc.
Return ONLY valid JSON. No explanation."""


async def categorize_skills(skills: list[str], user_profile: dict | None = None) -> dict[str, list[str]]:
    """Group a flat list of skills into professional categories using Claude."""
    context = ""
    if user_profile:
        context = f"\nUser context: {user_profile.get('industry', '')} | {user_profile.get('career_stage', '')} | {user_profile.get('goals', '')}"

    prompt = f"""Organize these {len(skills)} skills into 4–7 professional categories.{context}

Skills to categorize:
{json.dumps(skills, indent=2)}

Rules:
- Every skill must appear in exactly one category
- Category names should be professional and specific (not "Other" or "Miscellaneous")
- Order skills within each category from most to least important
- Use 4–7 categories total

Return JSON:
{{
  "Category Name": ["skill1", "skill2", ...],
  "Another Category": ["skill3", ...]
}}"""

    result = await complete(prompt, system=CATEGORIZE_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=1024)
    try:
        data = json.loads(result)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Fallback: put everything in one category
    return {"Skills": skills}


async def score_profile(headline: str, about: str, skills: list, experience: list) -> dict:
    prompt = f"""LinkedIn Profile:
Headline: {headline}
About section (first 500 chars): {about[:500] if about else ""}
Skills count: {len(skills)}
Experience entries: {len(experience)}

Score this profile 0-100 across:
- Headline quality (20pts): keywords, clarity, value prop, credibility
- About section (25pts): hook, storytelling, CTA, length
- Skills optimization (15pts): relevance, count, strategic selection
- Experience quality (20pts): quantified achievements, action verbs, impact
- Completeness (10pts): all key sections present and detailed
- Keyword density (10pts): searchability in LinkedIn algorithm

Return JSON:
{{
  "total_score": 0,
  "breakdown": {{
    "headline": {{"score": 0, "max": 20, "feedback": "..."}},
    "about": {{"score": 0, "max": 25, "feedback": "..."}},
    "skills": {{"score": 0, "max": 15, "feedback": "..."}},
    "experience": {{"score": 0, "max": 20, "feedback": "..."}},
    "completeness": {{"score": 0, "max": 10, "feedback": "..."}},
    "keywords": {{"score": 0, "max": 10, "feedback": "..."}}
  }},
  "top_improvements": ["improvement1", "improvement2", "improvement3"]
}}"""

    result = await complete(prompt, system=SCORER_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=1024)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"total_score": 50, "breakdown": {}, "top_improvements": []}
