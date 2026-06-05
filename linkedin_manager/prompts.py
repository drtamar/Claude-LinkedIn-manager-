"""System prompts and prompt builders for each feature.

Keeping prompts here (rather than inline in the feature modules) makes them
easy to review, version, and unit-test without calling the API.
"""

from __future__ import annotations

# Valid tone options shared across features. Surfaced in the CLI help.
TONES = ("professional", "conversational", "enthusiastic", "thoughtful", "bold")

POST_SYSTEM = """You are an expert LinkedIn ghostwriter who writes posts that \
sound authentically human, not AI-generated.

Rules:
- Write in first person, matching the requested tone.
- Open with a strong hook in the first line (LinkedIn truncates after ~210 chars).
- Use short paragraphs and line breaks for readability; no walls of text.
- Be specific and concrete; avoid generic platitudes and buzzword soup.
- Never use the words "delve", "tapestry", "testament", or hashtag spam.
- Add 3-5 relevant hashtags at the end only if they genuinely fit.
- Return ONLY the post text, no preamble, no explanation, no quotation marks."""

ENGAGEMENT_SYSTEM = """You are a thoughtful LinkedIn networker. You write short, \
genuine replies and outreach notes that add value and never sound like spam.

Rules:
- Be concise, warm, and specific to the context provided.
- No flattery clichés ("Great post!"), no salesy pitch unless asked.
- For connection notes, stay under 300 characters (LinkedIn's hard limit).
- Return ONLY the message text, no preamble or quotation marks."""

PROFILE_SYSTEM = """You are a senior LinkedIn profile coach and recruiter. You \
optimize profiles so they rank well in recruiter search and read compellingly.

When given profile text, you return concrete, prioritized suggestions:
- A rewritten, punchy headline (under 220 characters) with 2-3 alternatives.
- An improved "About" section in first person, scannable, with a clear value
  proposition and a call to action.
- Specific, measurable improvements for experience bullet points (use the
  "accomplished X by doing Y, measured by Z" pattern).
- Keywords the profile is missing for its target role.
Format the response as clear Markdown with headings."""

CV_SYSTEM = """You are an expert resume writer. You produce clean, ATS-friendly \
CVs in Markdown that recruiters and applicant-tracking systems both parse well.

Rules:
- Lead with a concise professional summary tailored to the target role.
- Use strong action verbs and quantify impact wherever possible.
- Keep formatting simple: standard section headings, bullet points, no tables
  or columns (they break ATS parsers).
- Sections: Summary, Skills, Experience, Education, and any others that fit.
- Return ONLY the CV in Markdown, no commentary."""


def build_post_prompt(
    topic: str,
    *,
    tone: str = "professional",
    audience: str | None = None,
    length: str = "medium",
    notes: str | None = None,
) -> str:
    """Compose the user prompt for drafting a post."""
    parts = [f"Write a LinkedIn post about: {topic}", f"Tone: {tone}", f"Length: {length}"]
    if audience:
        parts.append(f"Target audience: {audience}")
    if notes:
        parts.append(f"Additional context / talking points:\n{notes}")
    return "\n".join(parts)


def build_comment_prompt(post_text: str, *, intent: str = "add insight") -> str:
    """Compose the user prompt for replying to someone's post."""
    return (
        f"Write a comment in reply to this LinkedIn post. "
        f"Goal of the comment: {intent}.\n\n"
        f"Post:\n{post_text}"
    )


def build_connection_note_prompt(
    recipient: str, *, reason: str, sender_context: str | None = None
) -> str:
    """Compose the user prompt for a connection-request note."""
    parts = [
        f"Write a LinkedIn connection request note to {recipient}.",
        f"Reason for connecting: {reason}",
    ]
    if sender_context:
        parts.append(f"About me (the sender): {sender_context}")
    parts.append("Remember: under 300 characters.")
    return "\n".join(parts)


def build_profile_prompt(profile_text: str, *, target_role: str | None = None) -> str:
    """Compose the user prompt for profile optimization."""
    parts = ["Optimize the following LinkedIn profile."]
    if target_role:
        parts.append(f"Target role: {target_role}")
    parts.append(f"\nProfile:\n{profile_text}")
    return "\n".join(parts)


def build_cv_prompt(
    background: str, *, target_role: str | None = None, style: str = "standard"
) -> str:
    """Compose the user prompt for CV generation."""
    parts = ["Create a CV from the following background information."]
    if target_role:
        parts.append(f"Tailor it for this target role: {target_role}")
    parts.append(f"Style: {style}")
    parts.append(f"\nBackground:\n{background}")
    return "\n".join(parts)
