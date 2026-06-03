from typing import AsyncIterator
from app.ai.claude_client import stream_response, complete
import re

CV_SYSTEM = """You are an elite CV/resume writer with 15+ years experience placing professionals at top companies.
You write CVs that are:
- ATS-optimized: target keywords woven naturally throughout every section
- Achievement-oriented: every bullet quantifies impact with metrics (%, $, time, scale)
- Distinctive: the professional summary hooks a recruiter in the first 10 seconds
- Tailored: tone, vocabulary and emphasis match the person's exact career goals
- Clean: standard sections, consistent formatting, no gimmicks

Format output as clean, structured Markdown. Use **bold** for job titles and company names.
Use proper heading levels. Be specific, confident and concrete — avoid filler phrases like "proven track record"."""


async def stream_cv(user_profile: dict, linkedin_profile: dict) -> AsyncIterator[str]:
    """Stream a complete, professional CV generated from the user's profile data."""

    goals = user_profile.get("goals", "")
    user_type = user_profile.get("user_type", "professional")
    industry = user_profile.get("industry", "")
    sub_industry = user_profile.get("sub_industry", "")
    career_stage = user_profile.get("career_stage", "")
    achievements = user_profile.get("achievements", [])
    unique_value = user_profile.get("unique_value_prop", "")
    keywords = user_profile.get("keywords", [])
    target_audience = user_profile.get("target_audience", {})
    pain_points = user_profile.get("pain_points", [])
    content_tone = user_profile.get("content_tone", "professional")

    headline = linkedin_profile.get("headline", "")
    about = linkedin_profile.get("about_section", "")
    experience = linkedin_profile.get("experience", [])
    skills = linkedin_profile.get("skills", [])

    exp_sections = []
    for exp in experience:
        title = exp.get("title", "")
        company = exp.get("company", "")
        duration = exp.get("duration", "")
        exp_headline = exp.get("headline", "")
        bullets = exp.get("bullets", [])
        block = f"Role: {title} | Company: {company} | Duration: {duration}"
        if exp_headline:
            block += f"\nImpact summary: {exp_headline}"
        if bullets:
            block += "\nBullets:\n" + "\n".join(f"  - {b}" for b in bullets)
        exp_sections.append(block)

    exp_text = "\n\n".join(exp_sections) if exp_sections else "No experience entered yet — infer from headline and about section."
    skills_text = ", ".join(skills[:30]) if skills else "See headline/about"
    achievements_text = "\n".join(f"- {a}" for a in achievements) if achievements else "Extract from experience bullets"

    prompt = f"""Generate a complete, original, print-ready professional CV/resume for this person.

=== CAREER PROFILE ===
Primary Goal: {goals}
User Type: {user_type}
Industry: {industry} / {sub_industry}
Career Stage: {career_stage}
Unique Value: {unique_value}
Content Tone: {content_tone}
Target Keywords: {', '.join(keywords) if keywords else 'derive from experience'}
Target Audience / Buyers: {target_audience}
Key Pain Points Solved: {', '.join(str(p) for p in pain_points) if pain_points else 'see achievements'}

=== LINKEDIN HEADLINE ===
{headline}

=== LINKEDIN ABOUT SECTION ===
{about if about else '(not generated yet — infer from headline and profile)'}

=== WORK EXPERIENCE ===
{exp_text}

=== SKILLS ===
{skills_text}

=== KEY ACHIEVEMENTS ===
{achievements_text}

---

Write the complete CV with ALL of these sections. Be specific and compelling:

# [Infer Full Name from context or use "Your Name"]
[Headline / Title] | [Industry] | [Location if known, else omit]

## Professional Summary
3–4 sentences. Open with the person's core identity and biggest differentiator.
Include 2–3 target keywords naturally. End with what they're seeking or offering.

## Core Competencies
Two-column grid of 12–16 competencies (use | to separate columns, one pair per line).
Pull from skills and keywords.

## Professional Experience
For each role (reverse chronological):
**[Job Title]** | [Company Name] | [Duration]
_[One-line impact headline for the role]_
- [Achievement bullet: Action verb + what + measurable result]
- [Achievement bullet]
- [Achievement bullet]
(3–5 bullets per role, all quantified where possible)

## Key Achievements
Standalone section with 4–5 major career highlights, each with a metric:
- [Achievement]: [specific result with number]

## Education
Infer appropriate education for this career stage and industry if not provided.
Include degree, institution, year (or "Expected [year]" if early career).

## Skills & Technologies
Organize into 2–3 categories (e.g. Technical | Industry Expertise | Leadership):
- **Technical**: [list]
- **Industry**: [list]
- **Leadership / Soft**: [list]

## Certifications & Recognition *(include only if relevant, skip section if nothing to add)*
- [Cert / Award / Publication / Speaking]

Make this CV distinctive, not generic. Every line should earn its place.
Output clean Markdown only — no preamble, no "Here is your CV:" — start directly with # [Name]."""

    async for token in stream_response(prompt, system=CV_SYSTEM, model="claude-opus-4-8", max_tokens=4000):
        yield token


def markdown_to_print_html(md: str, display_name: str = "") -> str:
    """Wrap CV markdown in a print-ready, styled HTML document."""

    def convert(text: str) -> str:
        lines = text.split("\n")
        out = []
        in_list = False
        in_competencies = False

        for line in lines:
            s = line.strip()

            if not s:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                in_competencies = False
                out.append("<br>")
                continue

            # Headings
            if s.startswith("# "):
                if in_list: out.append("</ul>"); in_list = False
                out.append(f'<h1>{_inline(s[2:])}</h1>')
                continue
            if s.startswith("## "):
                if in_list: out.append("</ul>"); in_list = False
                section = s[3:]
                in_competencies = "competenc" in section.lower()
                out.append(f'<h2>{_inline(section)}</h2>')
                if in_competencies:
                    out.append('<div class="competencies">')
                continue
            if s.startswith("### "):
                if in_list: out.append("</ul>"); in_list = False
                out.append(f'<h3>{_inline(s[4:])}</h3>')
                continue

            # List items
            if s.startswith("- ") or s.startswith("* "):
                if in_competencies:
                    # render competency pairs side-by-side
                    parts = s[2:].split("|")
                    if len(parts) == 2:
                        out.append(f'<div class="comp-row"><span>{_inline(parts[0].strip())}</span><span>{_inline(parts[1].strip())}</span></div>')
                    else:
                        out.append(f'<div class="comp-row"><span>{_inline(s[2:])}</span></div>')
                    continue
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{_inline(s[2:])}</li>")
                continue

            # Close list if needed
            if in_list:
                out.append("</ul>")
                in_list = False

            # Close competency block when next non-list line appears
            if in_competencies and not s.startswith("- ") and not s.startswith("* "):
                out.append("</div>")
                in_competencies = False

            out.append(f"<p>{_inline(s)}</p>")

        if in_list:
            out.append("</ul>")
        if in_competencies:
            out.append("</div>")

        return "\n".join(out)

    body = convert(md)
    title = display_name or "CV"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1a1a1a;
    max-width: 820px;
    margin: 0 auto;
    padding: 48px 56px;
    background: #fff;
  }}
  h1 {{
    font-size: 22pt;
    font-weight: 700;
    color: #0077B5;
    border-bottom: 2.5px solid #0077B5;
    padding-bottom: 6px;
    margin-bottom: 2px;
    letter-spacing: -0.5px;
  }}
  h2 {{
    font-size: 10pt;
    font-weight: 700;
    color: #0077B5;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    border-bottom: 1px solid #d0d7de;
    padding-bottom: 3px;
    margin: 20px 0 10px;
  }}
  h3 {{
    font-size: 10.5pt;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 2px;
  }}
  p {{
    margin-bottom: 6px;
    color: #2c2c2c;
  }}
  em {{ color: #555; font-style: italic; }}
  strong {{ color: #0d0d0d; }}
  ul {{
    margin: 4px 0 10px 18px;
  }}
  li {{
    margin-bottom: 3px;
    color: #2c2c2c;
  }}
  .competencies {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2px 24px;
    margin: 6px 0 12px;
  }}
  .comp-row {{
    display: contents;
  }}
  .comp-row span {{
    padding: 2px 0;
    color: #2c2c2c;
    font-size: 10pt;
  }}
  .comp-row span::before {{ content: "▪ "; color: #0077B5; font-size: 8pt; }}
  br {{ display: block; margin: 4px 0; content: ""; }}
  @media print {{
    body {{ padding: 20px 28px; font-size: 10pt; }}
    h1 {{ font-size: 20pt; }}
    a {{ color: inherit; text-decoration: none; }}
    @page {{ margin: 1.2cm 1cm; size: A4; }}
  }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _inline(text: str) -> str:
    """Convert inline markdown (bold, italic, links) to HTML."""
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.*?)_', r'<em>\1</em>', text)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
    return text
