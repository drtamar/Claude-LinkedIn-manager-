"""Command-line interface for the LinkedIn manager.

Subcommands:
    post      Draft a LinkedIn post (optionally publish it).
    comment   Draft a comment in reply to a post.
    connect   Draft a connection-request note.
    profile   Get optimization suggestions for your profile.
    cv        Generate a CV from your background.

Run ``python -m linkedin_manager --help`` for details.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import content, cv, engagement, linkedin, profile, prompts
from .claude_client import ClaudeClient
from .config import Config


def _read_input(value: str) -> str:
    """Resolve an argument that may be literal text, a file path, or '-'.

    '-' reads from stdin; an existing file path reads the file; otherwise the
    value is treated as literal text. This makes the CLI ergonomic for both
    quick one-liners and longer pasted content.
    """
    if value == "-":
        return sys.stdin.read().strip()
    # A long literal string (a full post, profile, or CV) can exceed the OS
    # path-length limit and make Path checks raise OSError (ENAMETOOLONG /
    # EINVAL) or ValueError (embedded NULs). Treat any such failure as "not a
    # file" and fall back to literal text.
    try:
        path = Path(value)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        pass
    return value


def _save(config: Config, name: str, text: str, ext: str = "txt") -> Path:
    """Write generated text to the output directory and return the path.

    Raises a :class:`RuntimeError` (which ``main`` turns into a clean message)
    if the directory can't be created or written — e.g. permissions, a
    read-only filesystem, or a full disk.
    """
    try:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = config.output_dir / f"{name}-{stamp}.{ext}"
        path.write_text(text, encoding="utf-8")
        return path
    except OSError as exc:
        raise RuntimeError(
            f"Failed to save output to {config.output_dir}: {exc}"
        ) from exc


def _build_client(config: Config) -> ClaudeClient:
    return ClaudeClient.from_config(config)


def _cmd_post(args: argparse.Namespace, config: Config) -> int:
    client = _build_client(config)
    notes = _read_input(args.notes) if args.notes else None
    text = content.draft_post(
        client,
        args.topic,
        tone=args.tone,
        audience=args.audience,
        length=args.length,
        notes=notes,
    )
    print(text)
    path = _save(config, "post", text)
    print(f"\n[saved] {path}", file=sys.stderr)

    if args.publish:
        result = linkedin.publish_post(
            text,
            access_token=config.linkedin_access_token,
            author_urn=config.linkedin_author_urn,
        )
        print(f"[linkedin] {result.detail}", file=sys.stderr)
        if not result.posted and config.can_post_to_linkedin:
            return 1
    return 0


def _cmd_comment(args: argparse.Namespace, config: Config) -> int:
    client = _build_client(config)
    post_text = _read_input(args.post)
    text = engagement.draft_comment(client, post_text, intent=args.intent)
    print(text)
    return 0


def _cmd_connect(args: argparse.Namespace, config: Config) -> int:
    client = _build_client(config)
    text = engagement.draft_connection_note(
        client, args.recipient, reason=args.reason, sender_context=args.about
    )
    print(text)
    return 0


def _cmd_profile(args: argparse.Namespace, config: Config) -> int:
    client = _build_client(config)
    profile_text = _read_input(args.profile)
    text = profile.optimize_profile(client, profile_text, target_role=args.role)
    print(text)
    path = _save(config, "profile-suggestions", text, ext="md")
    print(f"\n[saved] {path}", file=sys.stderr)
    return 0


def _cmd_cv(args: argparse.Namespace, config: Config) -> int:
    client = _build_client(config)
    background = _read_input(args.background)
    text = cv.generate_cv(client, background, target_role=args.role, style=args.style)
    print(text)
    path = _save(config, "cv", text, ext="md")
    print(f"\n[saved] {path}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser (separated out for testability)."""
    parser = argparse.ArgumentParser(
        prog="linkedin-manager",
        description="Claude-powered LinkedIn content, profile, and CV assistant.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # post
    p_post = sub.add_parser("post", help="Draft a LinkedIn post.")
    p_post.add_argument("topic", help="What the post is about.")
    p_post.add_argument(
        "--tone", default="professional", choices=prompts.TONES, help="Voice of the post."
    )
    p_post.add_argument("--audience", help="Who the post is for.")
    p_post.add_argument(
        "--length", default="medium", choices=("short", "medium", "long")
    )
    p_post.add_argument("--notes", help="Talking points: literal text, a file path, or '-'.")
    p_post.add_argument(
        "--publish", action="store_true", help="Also post to LinkedIn if configured."
    )
    p_post.set_defaults(func=_cmd_post)

    # comment
    p_comment = sub.add_parser("comment", help="Draft a reply to a post.")
    p_comment.add_argument("post", help="The post text: literal, a file path, or '-'.")
    p_comment.add_argument(
        "--intent", default="add insight", help="What the comment should achieve."
    )
    p_comment.set_defaults(func=_cmd_comment)

    # connect
    p_connect = sub.add_parser("connect", help="Draft a connection-request note.")
    p_connect.add_argument("recipient", help="Who you're connecting with.")
    p_connect.add_argument("--reason", required=True, help="Why you want to connect.")
    p_connect.add_argument("--about", help="A sentence about you, the sender.")
    p_connect.set_defaults(func=_cmd_connect)

    # profile
    p_profile = sub.add_parser("profile", help="Optimize your profile.")
    p_profile.add_argument(
        "profile", help="Your profile text: literal, a file path, or '-'."
    )
    p_profile.add_argument("--role", help="Target role to optimize for.")
    p_profile.set_defaults(func=_cmd_profile)

    # cv
    p_cv = sub.add_parser("cv", help="Generate a CV from your background.")
    p_cv.add_argument(
        "background", help="Your background: literal text, a file path, or '-'."
    )
    p_cv.add_argument("--role", help="Target role to tailor the CV for.")
    p_cv.add_argument("--style", default="standard", help="CV style descriptor.")
    p_cv.set_defaults(func=_cmd_cv)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    config = Config.from_env()
    try:
        return args.func(args, config)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
