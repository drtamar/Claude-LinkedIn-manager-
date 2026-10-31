"""Command line checks that spend nothing (plan A3.4).

    python -m app.cli doctor      # is this set up correctly?
    python -m app.cli cost        # month-to-date spend, by stage
    python -m app.cli routes      # where each step runs, and why
    python -m app.cli estimate --input 8000 --output 1500

Every command here is read-only and makes no API call, so it is safe to run
when you are not sure what something will cost.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Tick/cross degrade to ASCII: the Windows console still defaults to a code
# page that cannot print these, and a UnicodeEncodeError in the diagnostic
# tool is a bad first impression.
def _symbols() -> tuple[str, str, str]:
    try:
        "✓✗▸".encode(sys.stdout.encoding or "utf-8")
        return "✓", "✗", "▸"
    except (UnicodeEncodeError, LookupError):
        return "OK", "XX", ">"


OK, BAD, BULLET = _symbols()


def cmd_doctor(_args) -> int:
    from app.routers.system import doctor

    report = doctor()
    print("\nSocial Desk — setup check\n" + "=" * 46)
    for check in report["checks"]:
        mark = OK if check["ok"] else (
            "!!" if check.get("severity") == "warning" else BAD)
        print(f"  {mark}  {check['name']}: {check['detail']}")
        # Some checks use the same text for both; don't say it twice.
        if check.get("fix") and check["fix"] != check["detail"]:
            print(f"      {BULLET} {check['fix']}")

    hw = report["hardware"]
    box = hw["hardware"]
    print(f"\n  Machine: {box['system']}, {box['cpu_cores']} cores, "
          f"{box['ram_gb']}GB RAM, GPU: {box['gpu_name'] or 'none'}")
    print(f"  Local tier: {hw['tier']} -> {hw['local_model']}")
    for warning in hw["warnings"]:
        print(f"      {BULLET} {warning}")

    spend = report["cost"]
    print(f"\n  Spent this month: ${spend['total_usd']:.4f} of "
          f"${spend['cap_usd']:.2f} ({spend['percent_used']}%) "
          f"across {spend['calls']} paid calls")

    print(f"\n{OK if report['ok'] else BAD} "
          f"{'Ready.' if report['ok'] else 'Not ready — see the fixes above.'}\n")
    return 0 if report["ok"] else 1


def cmd_cost(args) -> int:
    from app.llm import cost

    data = cost.summary() if not args.month else {
        **cost.month_to_date(args.month), "cap_usd": cost.monthly_cap()}

    print(f"\nSpend for {data['month']}\n" + "=" * 46)
    if not data["by_stage"]:
        print("  Nothing spent yet this month.")
    for stage, row in data["by_stage"].items():
        print(f"  {stage:<30} ${row['usd']:>9.4f}  ({row['calls']} calls)")
    print("-" * 46)
    print(f"  {'TOTAL':<30} ${data['total_usd']:>9.4f}")
    print(f"  {'Monthly cap':<30} ${data['cap_usd']:>9.2f}")
    if data.get("ledger_error"):
        print(f"\n  {BAD} Ledger unreadable: {data['ledger_error']}")
        print("     The cap cannot be enforced until this is fixed.")
    print(f"\n  Local-model work is free and is not listed here.")
    print(f"  Prices last reviewed {cost.PRICES_REVIEWED}.\n")
    return 0


def cmd_routes(_args) -> int:
    from app.routers.system import routes

    data = routes()
    print(f"\nRouting — local tier '{data['tier']}', model {data['local_model']}")
    print("=" * 78)
    print(f"  {'step':<16}{'runs on':<10}{'model':<22}why / fallback")
    print("-" * 78)
    for plan in data["routes"]:
        model = plan["model"] or "-"
        note = plan["fallback_reason"] or ""
        print(f"  {plan['task']:<16}{plan['actual_destination']:<10}{model:<22}{note}")
    print("-" * 78)
    print(f"  {data['free_steps']} step(s) free, {data['paid_steps']} paid.")
    if data["fallbacks_active"]:
        print(f"\n  {BULLET} Some steps are falling back to paid models:")
        for fb in data["fallbacks_active"]:
            print(f"      {fb['task']}: {fb['reason']}")
    print()
    return 0


def cmd_estimate(args) -> int:
    from app.llm import cost

    data = cost.estimate(args.model, args.input, args.output)
    print(f"\nEstimate — {data['model']}")
    print(f"  {args.input:,} input + {args.output:,} output tokens")
    print(f"  Cost: ${data['estimated_usd']:.4f}")
    print(f"  Budget left this month: ${data['remaining_budget_usd']:.4f}")
    if data["would_exceed_cap"]:
        print(f"  {BAD} This single call would exceed the remaining budget.")
    print("\n  Nothing was sent. This is arithmetic only.\n")
    return 0


def cmd_subjects(_args) -> int:
    from app.subjects import NO_SELF_PROMOTION
    from app.subjects.definitions import matrix

    print("\nSubjects and channels\n" + "=" * 78)
    for row in matrix():
        print(f"\n  {row['name']}  ({row['id']})")
        print(f"    audience   {row['audience']}, reading level {row['reading_level']}")
        if row["primary"]:
            print(f"    primary    {', '.join(row['primary'])}")
        if row["secondary"]:
            print(f"    secondary  {', '.join(row['secondary'])}")
        if row["participate"]:
            subs = ", ".join(f"r/{s}" for s in row["subreddits"])
            print(f"    take part  {', '.join(row['participate'])}  ({subs})")
        if row["skip"]:
            print(f"    skip       {', '.join(row['skip'])}")
        print(f"    {BULLET} {row['rationale']}")

    promo = ", ".join(c.value for c in NO_SELF_PROMOTION)
    print(f"\n  {BULLET} No self-promotion on: {promo} — the system drafts")
    print("    answers to other people's questions there, never posts about you.\n")
    return 0


def cmd_channels(_args) -> int:
    from app.channels import status

    print("\nChannels\n" + "=" * 70)
    print(f"  {'channel':<12}{'built':<8}{'ready':<8}note")
    print("-" * 70)
    for row in status():
        built = OK if row["implemented"] else "--"
        ready = OK if row.get("configured") else BAD
        note = row.get("note", "")
        if row["implemented"] and not row.get("configured"):
            note = "needs credentials — see doctor"
        elif row["implemented"]:
            note = f"max {row.get('max_body_chars') or 'unlimited'} chars"
        print(f"  {row['channel']:<12}{built:<8}{ready:<8}{note}")
    print()
    return 0


def cmd_publish(args) -> int:
    """Render a piece to its channel. --dry-run writes nothing anywhere."""
    from app.channels import ChannelNotImplemented, Piece, get_adapter
    from app.channels.website import render_article
    from app.subjects import Channel, get_subject

    try:
        subject = get_subject(args.subject)
    except ValueError as exc:
        print(f"{BAD} {exc}")
        return 2

    try:
        channel = Channel(args.channel)
    except ValueError:
        print(f"{BAD} Unknown channel {args.channel!r}. "
              f"Known: {', '.join(c.value for c in Channel)}")
        return 2

    reach = subject.reach(channel)
    if reach.value == "skip":
        print(f"{BAD} {subject.name} deliberately skips {channel.value}. "
              f"Run `subjects` to see why.")
        return 2

    body = Path(args.body).read_text(encoding="utf-8") if args.body else args.text or ""
    if not body.strip():
        print(f"{BAD} Nothing to publish — pass --text or --body <file>.")
        return 2

    piece = Piece(
        title=args.title,
        body=body,
        subject=subject.id,
        channel=channel,
        sources=tuple(args.source or ()),
        tags=tuple(args.tag or ()),
    )

    try:
        adapter = get_adapter(channel)
    except ChannelNotImplemented as exc:
        print(f"{BAD} {exc}")
        return 2

    issues = adapter.validate(piece)
    for issue in issues:
        mark = BAD if issue.blocking else "!!"
        print(f"  {mark}  {issue.field}: {issue.problem}")

    if args.dry_run:
        print(f"\n{BULLET} Dry run — nothing was sent or written.")
        print(f"  subject   {subject.name} ({reach.value} on {channel.value})")
        print(f"  key       {piece.idempotency_key}")
        if channel is Channel.WEBSITE:
            print(f"  would go  {adapter.path_for(piece)}")
            print("\n" + "-" * 70)
            print(render_article(piece))
            print("-" * 70)
        else:
            import json as _json
            print("  payload:")
            print(_json.dumps(adapter.build_payload(piece), indent=2)
                  if adapter.is_configured()
                  else "    (not configured — run doctor)")
        return 0

    result = adapter.check_then_publish(piece)
    mark = OK if result.published else BAD
    print(f"\n{mark} {result.detail}")
    if result.location:
        print(f"  {result.location}")
    return 0 if result.published else 1


def cmd_connect_linkedin(args) -> int:
    """One-time OAuth. Writes the token and author URN to .env."""
    from app.channels.linkedin_oauth import LinkedInAuthError, run_flow
    from app.config import get_settings

    settings = get_settings()
    client_id = (settings.linkedin_client_id or "").strip()
    client_secret = (settings.linkedin_client_secret or "").strip()

    if not client_id or not client_secret:
        print(f"""
{BAD} No LinkedIn app credentials yet.

  One-time setup, about five minutes and free:
    1. Go to https://developer.linkedin.com/ and create an app.
    2. Add the "Share on LinkedIn" and "Sign In with LinkedIn using OpenID
       Connect" products to it.
    3. Under Auth, add this exact redirect URL:
         {settings.linkedin_redirect_uri}
    4. Put the Client ID and Client Secret in your .env file as
       LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET.
    5. Run this command again.
""")
        return 2

    try:
        token = run_flow(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=settings.linkedin_redirect_uri,
            open_browser=not args.no_browser,
        )
    except LinkedInAuthError as exc:
        print(f"\n{BAD} {exc}")
        return 1

    env_path = Path(__file__).resolve().parents[2] / ".env"
    _upsert_env(env_path, "LINKEDIN_ACCESS_TOKEN", token.access_token)
    _upsert_env(env_path, "LINKEDIN_AUTHOR_URN", token.author_urn)

    print(f"\n{OK} Connected as {token.author_urn}")
    print(f"  Saved to {env_path}")
    if token.expires_in_days:
        print(f"  {BULLET} This token lasts about {token.expires_in_days} days. "
              "There is no refresh on the self-serve product, so run this "
              "command again when posting starts failing with a 401.")
    print("  Restart the app to pick it up.\n")
    return 0


def _upsert_env(path: Path, key: str, value: str) -> None:
    """Set KEY=value in .env, replacing an existing line rather than appending
    a second one. Creates the file if it is missing."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"# {key}="):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Read-only checks. None of these make a paid API call.",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    subs.add_parser("doctor", help="is this set up correctly?").set_defaults(
        func=cmd_doctor)

    p_cost = subs.add_parser("cost", help="month-to-date spend, by stage")
    p_cost.add_argument("--month", help="YYYY-MM (default: this month)")
    p_cost.set_defaults(func=cmd_cost)

    subs.add_parser("routes", help="where each step runs, and why").set_defaults(
        func=cmd_routes)

    p_est = subs.add_parser("estimate", help="price a call without making it")
    p_est.add_argument("--model", default="claude-opus-5-5")
    p_est.add_argument("--input", type=int, required=True)
    p_est.add_argument("--output", type=int, default=0)
    p_est.set_defaults(func=cmd_estimate)

    subs.add_parser("subjects", help="the four subjects and their channels"
                    ).set_defaults(func=cmd_subjects)
    subs.add_parser("channels", help="which channels are built and ready"
                    ).set_defaults(func=cmd_channels)

    p_pub = subs.add_parser("publish", help="render or publish one piece")
    p_pub.add_argument("--subject", required=True)
    p_pub.add_argument("--channel", required=True)
    p_pub.add_argument("--title", default="")
    p_pub.add_argument("--text", help="body text inline")
    p_pub.add_argument("--body", help="read the body from a file")
    p_pub.add_argument("--source", action="append", help="DOI or URL (repeatable)")
    p_pub.add_argument("--tag", action="append", help="tag (repeatable)")
    p_pub.add_argument("--dry-run", action="store_true",
                       help="render it and send nothing")
    p_pub.set_defaults(func=cmd_publish)

    p_li = subs.add_parser("connect-linkedin",
                           help="one-time LinkedIn authorisation")
    p_li.add_argument("--no-browser", action="store_true",
                      help="print the URL instead of opening a browser")
    p_li.set_defaults(func=cmd_connect_linkedin)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
