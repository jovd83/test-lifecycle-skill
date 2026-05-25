"""Evaluate strategy.json.exit_criteria against phase-10 aggregated results.

Used by phase 12 (heal loop) to decide pass vs iterate vs cap-stop.

Exit criteria keys supported (all numeric or boolean):
- overall_pass_rate_min       (float)
- p1_case_pass_rate_min       (float)
- p2_case_pass_rate_min       (float; null = no limit)
- regression_pass_rate_min    (float; null = no limit)
- open_findings.Critical      (int or null = no limit)
- open_findings.High          (int or null = no limit)
- open_findings.Medium        (int or null = no limit)
- additional[]                (list of {key, op, value} extras for full mode)

The aggregated.json must contain:
- totals: { total, passed, failed, skipped, blocked }
- findings_by_severity: { Critical, High, Medium, Low }
- per_priority: { P1: { total, passed }, P2: { total, passed }, P3: { total, passed } }   (optional but recommended)
- regression: { total, passed }                                                            (optional)
- extras: { ...arbitrary keys referenced by additional[] ... }                             (optional)

Usage:
    python scripts/check_exit_criteria.py --strategy phase-04-strategy/strategy.json \\
        --results phase-10-results/aggregated.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _rate(passed: int, total: int) -> float | None:
    if total == 0:
        return None
    return passed / total


def _eval_threshold(actual: float | int | None, op: str, expected) -> bool:
    if actual is None:
        return False
    if op == ">=":
        return actual >= expected
    if op == "<=":
        return actual <= expected
    if op == "==":
        return actual == expected
    if op == ">":
        return actual > expected
    if op == "<":
        return actual < expected
    raise ValueError(f"unsupported op: {op}")


def check(strategy: dict, results: dict) -> dict:
    criteria = strategy.get("exit_criteria") or {}
    failures: list[dict] = []

    totals = results.get("totals") or {}
    total = totals.get("total", 0)
    passed = totals.get("passed", 0)
    overall = _rate(passed, total)

    def _record(key: str, actual, op: str, expected):
        if not _eval_threshold(actual, op, expected):
            failures.append({"criterion": key, "actual": actual, "op": op, "expected": expected})

    if (v := criteria.get("overall_pass_rate_min")) is not None:
        _record("overall_pass_rate_min", overall, ">=", v)

    per_priority = results.get("per_priority") or {}
    for tier in ("P1", "P2"):
        threshold = criteria.get(f"{tier.lower()}_case_pass_rate_min")
        if threshold is None:
            continue
        tier_stats = per_priority.get(tier) or {}
        tier_rate = _rate(tier_stats.get("passed", 0), tier_stats.get("total", 0))
        _record(f"{tier.lower()}_case_pass_rate_min", tier_rate, ">=", threshold)

    reg_threshold = criteria.get("regression_pass_rate_min")
    if reg_threshold is not None:
        reg = results.get("regression") or {}
        reg_rate = _rate(reg.get("passed", 0), reg.get("total", 0))
        _record("regression_pass_rate_min", reg_rate, ">=", reg_threshold)

    open_findings = (criteria.get("open_findings") or {})
    actual_findings = results.get("findings_by_severity") or {}
    for severity in ("Critical", "High", "Medium"):
        limit = open_findings.get(severity)
        if limit is None:
            continue
        actual = actual_findings.get(severity, 0)
        _record(f"open_findings.{severity}", actual, "<=", limit)

    for extra in criteria.get("additional") or []:
        key = extra["key"]
        op = extra["op"]
        expected = extra["value"]
        # Navigate dotted key in results.extras
        actual = results.get("extras") or {}
        for part in key.split("."):
            if isinstance(actual, dict):
                actual = actual.get(part)
            else:
                actual = None
                break
        _record(key, actual, op, expected)

    return {
        "passed": len(failures) == 0,
        "summary": "exit criteria met" if not failures else f"{len(failures)} criterion failure(s)",
        "failures": failures,
        "evaluated_at_overall_pass_rate": overall,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", type=Path, required=True, help="Path to strategy.json")
    parser.add_argument("--results", type=Path, required=True, help="Path to aggregated.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        strategy = json.loads(args.strategy.read_text(encoding="utf-8"))
        results = json.loads(args.results.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading inputs: {exc}", file=sys.stderr)
        return 2

    try:
        outcome = check(strategy, results)
    except (ValueError, KeyError) as exc:
        print(f"Error evaluating: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(outcome, indent=2))
    else:
        print(f"Passed: {outcome['passed']}")
        print(f"Summary: {outcome['summary']}")
        if outcome["failures"]:
            print("Failures:")
            for f in outcome["failures"]:
                print(f"  - {f['criterion']}: actual={f['actual']} {f['op']} expected={f['expected']}")
    return 0 if outcome["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
