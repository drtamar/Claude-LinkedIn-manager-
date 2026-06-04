import json
from app.ai.claude_client import complete

TIMING_SYSTEM = """You are a LinkedIn algorithm specialist with deep knowledge of engagement timing patterns.
Analyze the user's historical performance data to recommend optimal posting times.
Return ONLY valid JSON."""

INSIGHTS_SYSTEM = """You are a LinkedIn growth analyst. Extract actionable insights from performance data.
Be specific with numbers. Return ONLY valid JSON."""


# LinkedIn algorithm knowledge base — embedded in all scoring
ALGORITHM_KNOWLEDGE = """
LinkedIn Algorithm Key Facts (2024-2025):
- Golden Hour: First 60 minutes after posting are critical. Early engagement velocity determines reach.
- Comment > Like > Reaction in terms of algorithmic weight
- Saves signal "I'll read later" — very high value signal
- Dwell time: Time spent reading matters. Longer posts can win if they hold attention.
- External links in posts REDUCE reach by ~40% (LinkedIn wants users to stay on platform)
- Native documents (PDFs/carousels) get 3x more reach than text posts on average
- Polls get 5x more engagement but often lower quality connections
- First-degree connection comments in first hour = massive reach boost
- Hashtags: 3-7 is optimal. More = spam signal
- Posting same time weekly trains the algorithm and your audience
- Creator Mode: Enables follower option, boosts content reach
- SSI Score impacts who sees your content (higher SSI = more reach)
- Personal profiles get more reach than company pages
- Videos get 5x more reach but must hook in first 3 seconds
"""

OPTIMAL_TIMES = {
    "default": {
        "best_days": ["Tuesday", "Wednesday", "Thursday"],
        "best_times": ["7:30-8:30 AM", "12:00-1:00 PM", "5:00-6:00 PM"],
        "timezone_note": "Based on target audience timezone",
        "worst_days": ["Saturday", "Sunday"],
        "worst_times": ["After 8 PM", "Before 7 AM"]
    }
}


async def get_optimal_times(user_profile: dict, historical_data: list = None) -> dict:
    if not historical_data or len(historical_data) < 5:
        return {
            "recommendation": OPTIMAL_TIMES["default"],
            "confidence": "low",
            "based_on": "industry defaults",
            "note": "Post 5+ times with metrics to get personalized recommendations"
        }

    prompt = f"""Analyze this user's LinkedIn post performance data to find optimal posting times.

User industry: {user_profile.get('industry', '')}
Target audience: {json.dumps(user_profile.get('target_audience', {}))}

Historical post data (date, time, impressions, engagement_rate):
{json.dumps(historical_data, indent=2)}

Find patterns:
1. Which days of week get highest impressions?
2. Which times of day get highest engagement rate?
3. Any content type vs time correlations?

Return JSON:
{{
  "best_days": ["Day1", "Day2"],
  "best_times": ["HH:MM AM/PM"],
  "best_combinations": [{{"day": "Tuesday", "time": "8:00 AM", "avg_impressions": 0}}],
  "worst_times": ["..."],
  "confidence": "high|medium|low",
  "sample_size": 0,
  "insights": ["specific insight 1", "insight 2"]
}}"""

    result = await complete(prompt, system=TIMING_SYSTEM, model="claude-haiku-4-5-20251001", max_tokens=512)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return OPTIMAL_TIMES["default"]


async def generate_insights(user_profile: dict, posts_with_metrics: list) -> list[dict]:
    if not posts_with_metrics or len(posts_with_metrics) < 3:
        return [
            {
                "type": "timing",
                "insight": "Post Tuesday-Thursday between 7-9 AM in your audience's timezone",
                "confidence": 0.8,
                "actionable": True
            },
            {
                "type": "format",
                "insight": "Native document uploads (PDF carousels) get 3x more reach than text posts",
                "confidence": 0.9,
                "actionable": True
            },
            {
                "type": "engagement",
                "insight": "Ask a specific question in every post to boost comments 5x",
                "confidence": 0.85,
                "actionable": True
            }
        ]

    prompt = f"""Analyze LinkedIn post performance and generate actionable insights.

User profile:
- Industry: {user_profile.get('industry', '')}
- Content tone: {user_profile.get('content_tone', '')}
- Goals: {json.dumps(user_profile.get('goals', []))}

Posts and their metrics:
{json.dumps(posts_with_metrics[:20], indent=2)}

Generate 5-8 specific, data-driven insights. Focus on:
- What content types perform best for this user
- Which hooks/openings get most engagement
- Best posting times based on data
- Topics that resonate with their audience
- Patterns in underperforming content

Return JSON array:
[
  {{
    "type": "timing|hook|format|length|hashtag|engagement|topic",
    "insight": "specific, quantified finding",
    "confidence": 0.0-1.0,
    "based_on_count": 0,
    "actionable": true,
    "action": "what to do differently"
  }}
]"""

    result = await complete(prompt, system=INSIGHTS_SYSTEM, model="claude-opus-4-8", max_tokens=1024)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return []
