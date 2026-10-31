"""Website adapter: writes an article to a file (plan B4.2).

The magazine site is still being built, so there is no endpoint to post to and
no platform to commit to. This adapter therefore produces **Markdown with YAML
front-matter**, which is what WordPress, Ghost, Astro and Eleventy all ingest.
When the site lands, this class grows an HTTP path and the article format does
not change.

The subject becomes the magazine section, so four subjects produce four
sections with one article each per month (decision 0.7).

Front-matter is written by hand rather than with PyYAML: the field set is
small and fixed, and this keeps the adapter dependency-free like the rest of
the layer. `_quote` handles the cases that actually occur in a title.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import unicodedata
from pathlib import Path

from app.channels.base import ChannelAdapter, Piece, PublishResult, ValidationIssue
from app.subjects import Channel, get_subject

# Where articles are written. Anchored on the backend package so a Windows
# shortcut launching from System32 still finds it.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "output" / "articles"

# The line appended when a piece was AI-drafted. Set at write time rather than
# left to the writer to remember (plan G3.3).
AI_DISCLOSURE = (
    "*This article was drafted with AI assistance and reviewed by "
    "Dr Tamar Savtchenko, DVM, before publication.*"
)


def output_dir() -> Path:
    override = os.environ.get("SOCIAL_DESK_ARTICLE_DIR", "").strip()
    return Path(override) if override else DEFAULT_OUTPUT_DIR


def slugify(text: str) -> str:
    """URL-safe slug. Strips accents rather than dropping accented words.

    Cyprus means Greek names and clinical terms carry diacritics; a naive
    ASCII filter would turn "Λευκωσία" into nothing and collide filenames.
    """
    normalised = unicodedata.normalize("NFKD", text)
    ascii_text = normalised.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug.strip("-") or "untitled"


def _quote(value: str) -> str:
    """Quote a YAML scalar safely for the characters titles actually contain."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_front_matter(piece: Piece, *, published: _dt.date) -> str:
    subject = get_subject(piece.subject)
    lines = [
        "---",
        f"title: {_quote(piece.title)}",
        f"date: {published.isoformat()}",
        # Both keys on purpose: different static-site generators look for
        # different names, and carrying both means the import works either way.
        f"section: {_quote(subject.name)}",
        f"category: {_quote(subject.name)}",
        f"subject_id: {piece.subject}",
        f"audience: {_quote(subject.audience)}",
        f"reading_level: {subject.reading_level}",
        f"ai_assisted: {str(piece.ai_assisted).lower()}",
        f"publish_key: {piece.idempotency_key}",
    ]
    if piece.tags:
        lines.append("tags:")
        lines.extend(f"  - {_quote(t)}" for t in piece.tags)
    if piece.sources:
        lines.append("sources:")
        lines.extend(f"  - {_quote(s)}" for s in piece.sources)
    if piece.idea_id is not None:
        lines.append(f"idea_id: {piece.idea_id}")
    lines.append("---")
    return "\n".join(lines)


def render_article(piece: Piece, *, published: _dt.date | None = None) -> str:
    """The complete file: front-matter, body, sources, disclosure."""
    published = published or _dt.date.today()
    parts = [render_front_matter(piece, published=published), "", piece.body.strip()]

    if piece.sources:
        parts += ["", "## Sources", ""]
        parts += [f"- {s}" for s in piece.sources]

    if piece.ai_assisted:
        parts += ["", "---", "", AI_DISCLOSURE]

    return "\n".join(parts) + "\n"


class WebsiteAdapter(ChannelAdapter):
    channel = Channel.WEBSITE
    # A magazine article has no length ceiling worth enforcing, and a title
    # longer than this is a sign something went wrong upstream.
    max_title_chars = 200
    requires_ai_disclosure = True

    def __init__(self, directory: Path | None = None):
        self.directory = directory or output_dir()

    def is_configured(self) -> bool:
        """Always true: writing a file needs no credentials.

        This is why the website is first in the roadmap — it is the one
        channel that works before any API is set up.
        """
        return True

    def validate(self, piece: Piece) -> list[ValidationIssue]:
        issues = super().validate(piece)
        if not piece.title.strip():
            issues.append(ValidationIssue("title", "an article needs a title"))
        if not piece.sources:
            # Not blocking: a practice-note article can legitimately have no
            # citation. But a research piece without one is a mistake, and
            # this is where it shows up.
            issues.append(ValidationIssue(
                "sources",
                "no sources — fine for a practice note, wrong for anything "
                "citing research",
                blocking=False,
            ))
        return issues

    def path_for(self, piece: Piece, *, published: _dt.date | None = None) -> Path:
        """Where this article goes: output/articles/<section>/<date>-<slug>.md."""
        published = published or _dt.date.today()
        return (
            self.directory
            / piece.subject
            / f"{published.isoformat()}-{slugify(piece.title)}.md"
        )

    def publish(self, piece: Piece) -> PublishResult:
        published = _dt.date.today()
        path = self.path_for(piece, published=published)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Idempotency (G3.1): if this exact content is already on disk,
            # report success without rewriting. A re-run of the same publish
            # is a no-op rather than a duplicate or a churned file.
            if path.exists():
                existing = path.read_text(encoding="utf-8")
                if f"publish_key: {piece.idempotency_key}" in existing:
                    return PublishResult(
                        published=True,
                        detail="Already written with identical content.",
                        external_id=piece.idempotency_key,
                        location=str(path),
                    )
            path.write_text(render_article(piece, published=published),
                            encoding="utf-8")
        except OSError as exc:
            return PublishResult(
                published=False,
                detail=f"Could not write the article: {exc}",
            )

        return PublishResult(
            published=True,
            detail=f"Article written to {path.name}.",
            external_id=piece.idempotency_key,
            location=str(path),
        )
