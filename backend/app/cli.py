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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
