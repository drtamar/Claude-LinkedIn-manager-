import json
from app.ai.claude_client import complete, stream_response

NEXT_QUESTION_SYSTEM = """You are a world-class LinkedIn strategist conducting a deep intake interview.
Your goal is to fully understand the user's professional situation, goals, target audience, and voice
so you can help them dominate LinkedIn.

Ask ONE focused question at a time. Adapt based on prior answers. Be warm, specific, and insightful.
Return ONLY valid JSON — no markdown, no explanation, just the JSON object."""

NEXT_QUESTION_PROMPT = """User type: {{ user_type }}
Previous answers: {{ answers_json }}
Step: {{ step_number }} of {{ total_steps }}
Topics still to cover: {{ topics_remaining }}

Generate the next question. Return JSON:
{
  "step_id": "unique_snake_case_id",
  "question": "The question text",
  "question_type": "text|select|multi_select|scale|boolean",
  "options": ["option1", "option2"],  // only for select/multi_select
  "scale_min": 1,  // only for scale
  "scale_max": 10,  // only for scale
  "placeholder": "hint text for text inputs",
  "why_asking": "brief internal note on why this matters"
}"""

SYNTHESIZE_SYSTEM = """You are a LinkedIn strategy expert. Synthesize interview answers into a precise
professional profile. Extract concrete, actionable data. Be specific — use the user's exact words where
they describe their achievements, differentiators, and audience. Return ONLY valid JSON."""

SYNTHESIZE_PROMPT = """User type: {{ user_type }}
All interview answers:
{{ answers_json }}

Synthesize into a professional profile JSON:
{
  "goals": ["goal1", "goal2"],
  "industry": "string",
  "sub_industry": "string",
  "target_audience": {
    "description": "string",
    "job_titles": ["title1"],
    "company_sizes": ["startup", "smb"],
    "geographies": ["US", "Global"],
    "pain_points": ["pain1", "pain2"]
  },
  "content_tone": "professional|conversational|thought_leader|storyteller|educator",
  "posting_frequency": "daily|3x_week|weekly|bi_weekly",
  "career_stage": "entry|mid|senior|executive|founder",
  "company_size_focus": "string",
  "geographic_focus": "string",
  "unique_value_prop": "one sentence",
  "pain_points": ["point1"],
  "achievements": ["achievement with metrics"],
  "keywords": ["keyword1"],
  "competitors": ["name1"],
  "brand_voice_notes": "specific tone and style notes from their writing sample",
  "content_pillars": ["pillar1", "pillar2", "pillar3"]
}"""

QUESTION_BANK = [
    {"id": "goal_primary", "topic": "Primary LinkedIn goal"},
    {"id": "goal_detail", "topic": "Goal specifics and success metrics"},
    {"id": "current_situation", "topic": "Current role, company, daily work"},
    {"id": "career_stage", "topic": "Career stage / seniority level"},
    {"id": "industry", "topic": "Industry"},
    {"id": "sub_industry", "topic": "Niche or specialty"},
    {"id": "years_experience", "topic": "Years of experience"},
    {"id": "target_audience", "topic": "Who they want to reach on LinkedIn"},
    {"id": "audience_titles", "topic": "Job titles of target audience"},
    {"id": "audience_company_size", "topic": "Company sizes of target audience"},
    {"id": "audience_geography", "topic": "Geographic targeting"},
    {"id": "audience_pain_points", "topic": "Target audience pain points"},
    {"id": "your_solution", "topic": "How user solves those pain points"},
    {"id": "competitors_peers", "topic": "Admired LinkedIn peers for tone analysis"},
    {"id": "unique_differentiator", "topic": "Unique differentiator"},
    {"id": "biggest_achievements", "topic": "Top 3 achievements with metrics"},
    {"id": "credentials", "topic": "Credentials and certifications"},
    {"id": "signature_frameworks", "topic": "Signature methods or frameworks"},
    {"id": "social_proof", "topic": "Notable clients, employers, press"},
    {"id": "content_tone", "topic": "Content tone style"},
    {"id": "topics_love", "topic": "Topics they love writing about"},
    {"id": "topics_avoid", "topic": "Topics to avoid"},
    {"id": "posting_frequency_goal", "topic": "Posting frequency goal"},
    {"id": "content_format_preference", "topic": "Preferred content formats"},
    {"id": "writing_style_sample", "topic": "Writing sample in natural voice"},
    {"id": "hashtag_strategy", "topic": "Hashtag strategy preference"},
    {"id": "success_metric", "topic": "Most important success metrics"},
    {"id": "current_linkedin_activity", "topic": "Current LinkedIn activity level"},
    {"id": "past_performance", "topic": "Past content performance"},
    {"id": "automation_comfort", "topic": "Comfort with automation"},
    {"id": "time_commitment", "topic": "Weekly time commitment"},
]

USER_TYPE_QUESTIONS = {
    "job_seeker": [
        {"id": "target_role", "topic": "Target job role titles"},
        {"id": "target_companies", "topic": "Target companies"},
        {"id": "open_to_work_visibility", "topic": "Open to Work visibility setting"},
        {"id": "relocation_willingness", "topic": "Relocation or remote preference"},
    ],
    "founder": [
        {"id": "startup_stage", "topic": "Startup stage"},
        {"id": "fundraising_goal", "topic": "Fundraising plans"},
        {"id": "hiring_for", "topic": "Hiring needs"},
        {"id": "partnership_goals", "topic": "Partnership and BD goals"},
    ],
    "sales": [
        {"id": "product_service", "topic": "What they are selling"},
        {"id": "deal_size", "topic": "Typical deal size"},
        {"id": "sales_cycle", "topic": "Typical sales cycle length"},
        {"id": "existing_pipeline", "topic": "Ideal customer profile characteristics"},
    ],
    "creator": [
        {"id": "monetization_model", "topic": "Monetization model"},
        {"id": "existing_audience", "topic": "Existing audience on other platforms"},
        {"id": "content_niche_depth", "topic": "Niche depth preference"},
        {"id": "collaboration_interest", "topic": "Collaboration interest"},
    ],
}


async def get_next_question(
    user_type: str,
    answers: dict,
    step_number: int,
) -> dict:
    answered_ids = set(answers.keys())
    all_questions = QUESTION_BANK + USER_TYPE_QUESTIONS.get(user_type, USER_TYPE_QUESTIONS["founder"])
    remaining = [q for q in all_questions if q["id"] not in answered_ids]
    topics_remaining = [q["topic"] for q in remaining[:10]]

    prompt = NEXT_QUESTION_PROMPT\
        .replace("{{ user_type }}", user_type)\
        .replace("{{ answers_json }}", json.dumps(answers, indent=2))\
        .replace("{{ step_number }}", str(step_number))\
        .replace("{{ total_steps }}", "35")\
        .replace("{{ topics_remaining }}", json.dumps(topics_remaining))

    result = await complete(prompt, system=NEXT_QUESTION_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=512)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        # Fallback to a safe generic question
        return {
            "step_id": f"step_{step_number}",
            "question": "Tell me more about your professional goals and what success looks like for you.",
            "question_type": "text",
            "placeholder": "Share as much detail as you like...",
        }


async def synthesize_profile(user_type: str, answers: dict) -> dict:
    prompt = SYNTHESIZE_PROMPT\
        .replace("{{ user_type }}", user_type)\
        .replace("{{ answers_json }}", json.dumps(answers, indent=2))

    result = await complete(prompt, system=SYNTHESIZE_SYSTEM, model="claude-opus-4-8", max_tokens=2048)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "synthesis_failed", "raw": result}
