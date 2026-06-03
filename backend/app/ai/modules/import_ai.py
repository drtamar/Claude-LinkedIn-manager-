import json
from app.ai.claude_client import complete

IMPORT_SYSTEM = """You are a professional profile parser. Extract structured data from a CV/resume or LinkedIn profile export.
Return ONLY a single valid JSON object — no markdown, no explanation, no code fences.
For any field not found in the text, use reasonable inferences or null.
Be thorough and extract every piece of information available."""


async def extract_profile_from_text(raw_text: str, user_type: str = "founder") -> dict:
    """Parse a CV/LinkedIn export into structured UserProfile + LinkedInProfile data."""

    prompt = f"""Extract all professional profile data from this CV/LinkedIn profile text.

--- RAW PROFILE TEXT ---
{raw_text}
--- END ---

Return a JSON object with EXACTLY these two top-level keys: "user_profile" and "linkedin_profile".

"user_profile" must contain:
{{
  "goals": "primary career/business goal as a string",
  "industry": "primary industry (e.g. Veterinary Medicine)",
  "sub_industry": "niche/sub-industry",
  "career_stage": "one of: early, mid, senior, executive",
  "unique_value_prop": "what makes this person uniquely valuable (2-3 sentences)",
  "content_tone": "one of: professional, conversational, authoritative, inspirational",
  "posting_frequency": "one of: daily, 3x_week, weekly, biweekly",
  "target_audience": {{"primary": "...", "secondary": "..."}},
  "pain_points": ["problem they solve 1", "problem 2", "problem 3"],
  "achievements": ["achievement with metric 1", "achievement 2", "achievement 3", "achievement 4"],
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7", "keyword8"],
  "brand_voice_notes": "notes on their writing style and personality"
}}

"linkedin_profile" must contain:
{{
  "headline": "optimized LinkedIn headline under 220 chars",
  "about_section": "compelling LinkedIn About section (300-500 words, first person, StoryBrand framework)",
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "duration": "Month Year – Month Year (X years Y months)",
      "headline": "one-line impact statement for this role",
      "bullets": ["achievement bullet 1", "achievement bullet 2", "achievement bullet 3"]
    }}
  ],
  "skills": ["skill1", "skill2", ... up to 50 skills, ordered by strategic importance],
  "skills_categorized": {{
    "Category Name": ["skill1", "skill2"],
    "Another Category": ["skill3"]
  }},
  "education": [
    {{
      "degree": "Degree Name",
      "institution": "University/School",
      "year": "Graduation year or range",
      "notes": "relevant details"
    }}
  ],
  "certifications": ["cert1", "cert2"]
}}

Extract ALL experience entries. For skills, include every skill mentioned plus infer additional relevant ones.
For the about_section, write a compelling first-person narrative using their actual background.
Make the headline specific and keyword-rich."""

    result = await complete(prompt, system=IMPORT_SYSTEM, model="claude-opus-4-8", max_tokens=4000)

    # Strip markdown code fences if present
    result = result.strip()
    if result.startswith("```"):
        lines = result.split("\n")
        result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(result)
        return data
    except json.JSONDecodeError:
        # Try to salvage partial JSON
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        raise ValueError(f"Claude returned unparseable JSON: {result[:200]}")
