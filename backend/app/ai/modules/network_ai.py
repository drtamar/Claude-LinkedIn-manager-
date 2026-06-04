import json
from typing import AsyncIterator
from app.ai.claude_client import complete, stream_response

ICP_SYSTEM = """You are a LinkedIn networking strategist specializing in Ideal Customer/Connection Profiles.
Build precise, actionable ICPs that result in high connection acceptance rates.
Return ONLY valid JSON."""

NOTE_SYSTEM = """You are a LinkedIn outreach specialist. Write connection notes that get accepted.
Rules: under 300 characters, genuine not salesy, reference something specific, clear reason to connect.
Return ONLY the note text — no quotes, no explanation."""

SEQUENCE_SYSTEM = """You are a LinkedIn outreach sequence expert.
Write multi-touch sequences that convert connections to conversations to meetings.
Each message must provide value first. Return ONLY valid JSON."""


async def stream_icp(user_profile: dict) -> AsyncIterator[str]:
    prompt = f"""Build a precise LinkedIn ICP (Ideal Connection Profile) for this user.

User profile:
- Goals: {json.dumps(user_profile.get('goals', []))}
- Industry: {user_profile.get('industry', '')}
- Target audience description: {json.dumps(user_profile.get('target_audience', {}))}
- Career stage: {user_profile.get('career_stage', '')}
- User type: {user_profile.get('career_stage', 'professional')}

Generate 2 distinct ICPs (e.g., "Primary decision makers" and "Influencers/champions").
For each ICP, provide:

**ICP Name:** [descriptive name]
**Job Titles (10+ variations):** [list]
**Industries:** [list]
**Company Sizes:** [list]
**Seniority Levels:** [list]
**Geographies:** [list]
**Keywords to search (10):** [list — terms they'd use in their LinkedIn headline/about]
**Keywords to exclude (5):** [list — indicators of bad fit]
**Pain points they have:** [list]
**Connection note template:** [personalized template with [NAME], [COMPANY] placeholders]
**Why connect with them:** [strategic rationale]

Be very specific. These ICPs will drive automated connection requests."""

    async for token in stream_response(prompt, system=ICP_SYSTEM, model="claude-opus-4-8", max_tokens=2048):
        yield token


async def generate_connection_note(
    prospect_name: str,
    prospect_title: str,
    prospect_company: str,
    prospect_bio_snippet: str,
    user_profile: dict,
) -> str:
    prompt = f"""Write a LinkedIn connection note for this prospect.

Prospect: {prospect_name}, {prospect_title} at {prospect_company}
Their bio snippet: {prospect_bio_snippet[:300] if prospect_bio_snippet else "Not available"}

My profile:
- Goals: {json.dumps(user_profile.get('goals', []))}
- Industry: {user_profile.get('industry', '')}
- Unique value: {user_profile.get('unique_value_prop', '')}

Write the note. Under 300 characters. Reference something specific about them.
Don't be salesy. Give a genuine reason to connect."""

    return await complete(prompt, system=NOTE_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=128)


async def stream_sequence(user_profile: dict, icp_name: str, icp_description: str) -> AsyncIterator[str]:
    prompt = f"""Create a 3-step LinkedIn outreach sequence for: {icp_name}
{icp_description}

User sending the messages:
- Goals: {json.dumps(user_profile.get('goals', []))}
- Value prop: {user_profile.get('unique_value_prop', '')}
- Industry: {user_profile.get('industry', '')}

Generate JSON:
{{
  "name": "Sequence name",
  "icp_description": "who this is for",
  "step_1": {{
    "type": "connection_note",
    "timing": "When sending request",
    "message": "Under 300 chars — genuine connection reason",
    "goal": "get accepted"
  }},
  "step_2": {{
    "type": "follow_up_after_accept",
    "delay_days": 3,
    "message": "First message after they accept — 100 words max, provide value, no ask",
    "goal": "start conversation"
  }},
  "step_3": {{
    "type": "soft_ask",
    "delay_days": 7,
    "message": "150 words max — reference step 2, make specific low-friction ask",
    "goal": "schedule call or get reply"
  }}
}}"""

    async for token in stream_response(prompt, system=SEQUENCE_SYSTEM, model="claude-opus-4-8", max_tokens=1024):
        yield token
