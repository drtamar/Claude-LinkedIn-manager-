import json
from app.ai.claude_client import complete

ANALYZER_SYSTEM = """You are a LinkedIn content performance analyst and prompt engineering expert.
Analyze performance data to find what's working and what needs to improve.
Be specific with numbers. Return ONLY valid JSON."""

REFINER_SYSTEM = """You are a prompt engineering expert specializing in LinkedIn content generation.
You improve AI prompts by incorporating performance learnings.
The new prompt must maintain the original structure but produce better outputs based on what worked.
Return ONLY valid JSON."""


async def analyze_performance(
    user_profile: dict,
    posts_with_metrics: list,
    current_prompt_versions: list,
) -> dict:
    prompt = f"""Analyze 30-day LinkedIn performance data to identify patterns.

User profile:
{json.dumps(user_profile, indent=2)}

Posts with performance metrics (last 30 days):
{json.dumps(posts_with_metrics, indent=2)}

Current prompt versions being used:
{json.dumps([{{"module": p["module"], "version": p["version"]}} for p in current_prompt_versions], indent=2)}

Analyze and return JSON:
{{
  "summary": {{
    "total_posts": 0,
    "avg_impressions": 0,
    "avg_engagement_rate": 0,
    "top_post_impressions": 0
  }},
  "high_performing_patterns": [
    {{
      "pattern": "description",
      "metric": "impressions|engagement_rate|comments",
      "avg_value": 0,
      "examples": ["post excerpt 1"]
    }}
  ],
  "low_performing_patterns": [
    {{
      "pattern": "description",
      "avg_value": 0,
      "why_it_fails": "..."
    }}
  ],
  "best_post_types": ["type1", "type2"],
  "best_topics": ["topic1"],
  "best_hooks_style": "description of what hook styles work",
  "optimal_length": 0,
  "prompt_improvement_suggestions": [
    {{
      "module": "content.post_writer",
      "priority": "high|medium|low",
      "suggestion": "specific change to make",
      "rationale": "why this will help",
      "expected_improvement": "10-20% higher engagement"
    }}
  ]
}}"""

    result = await complete(prompt, system=ANALYZER_SYSTEM, model="claude-opus-4-8", max_tokens=2048)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "analysis_failed", "prompt_improvement_suggestions": []}


async def refine_prompt(
    module: str,
    current_prompt: str,
    current_system: str,
    performance_findings: dict,
    high_performing_examples: list,
) -> dict:
    prompt = f"""Improve this AI prompt based on performance learnings.

Module: {module}
Current prompt template:
---
{current_prompt}
---

Current system message:
---
{current_system}
---

Performance findings:
{json.dumps(performance_findings, indent=2)}

High-performing examples (content that got 3x+ avg engagement):
{json.dumps(high_performing_examples[:3], indent=2)}

Rewrite the prompt to incorporate these learnings:
1. Add specific instructions that mirror high-performing patterns
2. Add explicit instructions to avoid low-performing patterns
3. Include examples of what "good" looks like based on data
4. Maintain the original structure and purpose

Return JSON:
{{
  "new_prompt_template": "the improved prompt",
  "new_system_message": "improved system message if needed, or same",
  "change_summary": "what you changed and why",
  "expected_improvement": "what metric should improve and by how much",
  "version_notes": "brief note for the version history"
}}"""

    result = await complete(prompt, system=REFINER_SYSTEM, model="claude-opus-4-8", max_tokens=2048)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "refinement_failed"}
