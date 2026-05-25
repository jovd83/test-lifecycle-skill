"""Compile the phase-13 final report from a completed run's artifacts.

Reads:
- state.json
- phase-01-intake/intake.md (best-effort)
- phase-04-strategy/strategy.json
- phase-10-results/aggregated.json
- phase-09b-manual/results.json (may be [])
- phase-12-heal/iter-*.md (list)
- audit-log.jsonl

Writes:
- phase-13-report/report.md (using the section order from references/final-report-template.md)
- phase-13-report/report.json

Usage:
    python scripts/compile_report.py --workspace .test-lifecycle/run-20260525-143200
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _read_audit(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _gate_decisions(audit: list[dict]) -> list[dict]:
    return [e for e in audit if e.get("event") in ("gate-resolve", "gate-reject")]


def _heal_iters(heal_dir: Path) -> list[str]:
    if not heal_dir.exists():
        return []
    return sorted(str(p.relative_to(heal_dir.parent)) for p in heal_dir.glob("iter-*.md"))


def _posture(exit_outcome: dict, findings_by_severity: dict, gates_rejected: bool) -> str:
    if gates_rejected:
        return "blocked"
    high_open = findings_by_severity.get("High", 0)
    if not exit_outcome.get("passed"):
        return "residual-risk"
    if high_open > 0 or findings_by_severity.get("Medium", 0) > 0:
        return "green-with-caveats"
    return "green"


def compile_report(workspace: Path) -> dict:
    state = _load_json(workspace / "state.json", default={})
    strategy = _load_json(workspace / "phase-04-strategy" / "strategy.json", default={})
    results = _load_json(workspace / "phase-10-results" / "aggregated.json", default={})
    manual = _load_json(workspace / "phase-09b-manual" / "results.json", default=[])
    audit = _read_audit(workspace / "audit-log.jsonl")
    heal_log = _heal_iters(workspace / "phase-12-heal")

    # Exit-criteria outcome — best-effort; if check fails, report it.
    try:
        from check_exit_criteria import check as _check  # type: ignore
        exit_outcome = _check(strategy, results)
    except Exception:
        # Fallback: rely on whatever's already in state
        exit_outcome = {"passed": False, "summary": "exit criteria not evaluated (check failed)", "failures": []}

    gate_decisions = _gate_decisions(audit)
    gates_rejected = any(e.get("decision") == "rejected" for e in gate_decisions)

    findings_by_severity = results.get("findings_by_severity") or {}
    posture = _posture(exit_outcome, findings_by_severity, gates_rejected)

    report = {
        "schema_version": "1.0",
        "report_kind": "test-lifecycle-final-report",
        "run_id": state.get("run_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sut": state.get("sut", {}),
        "mode": state.get("mode"),
        "risk_class": state.get("risk_class"),
        "posture": posture,
        "executive_summary": _executive_summary(state, exit_outcome, posture, findings_by_severity),
        "strategy_ref": "phase-04-strategy/strategy.json",
        "exit_criteria_outcome": exit_outcome,
        "traceability": _build_traceability(strategy, results, manual),
        "lanes": _lane_summaries(results),
        "manual": manual or [],
        "heal_loop": {
            "iterations": state.get("heal_iterations", 0),
            "cap": state.get("heal_cap"),
            "outcome": "exit-criteria-met" if exit_outcome.get("passed") else "stopped-at-cap-or-failed",
            "log": heal_log,
        },
        "hitl_audit": gate_decisions,
        "residual_risks": _residual_risks(exit_outcome, findings_by_severity),
        "open_followups": [],
        "strategy_adherence": _strategy_adherence(strategy, results),
        "signoff": {
            "approved": None,
            "approver": None,
            "approver_role": None,
            "approved_at": None,
            "notes": None,
        },
    }

    report_dir = workspace / "phase-13-report"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (report_dir / "report.md").write_text(_render_markdown(report), encoding="utf-8")

    return {
        "report_md": str(report_dir / "report.md"),
        "report_json": str(report_dir / "report.json"),
        "posture": posture,
    }


def _executive_summary(state, exit_outcome, posture, findings_by_severity) -> str:
    sut = state.get("sut", {})
    return (
        f"SUT {sut.get('id', '?')} ({sut.get('type', '?')}) under {state.get('mode', '?')} mode, "
        f"risk class {state.get('risk_class', '?')}. Posture: {posture}. "
        f"Exit criteria: {'met' if exit_outcome.get('passed') else 'not met'}. "
        f"Findings: Critical={findings_by_severity.get('Critical', 0)}, "
        f"High={findings_by_severity.get('High', 0)}, "
        f"Medium={findings_by_severity.get('Medium', 0)}."
    )


def _build_traceability(strategy: dict, results: dict, manual: list) -> list[dict]:
    scenarios = strategy.get("scenarios") or []
    per_scenario = {s.get("scenario_id"): s for s in (results.get("per_scenario") or [])}
    manual_by_scenario = {m.get("scenario_id"): m for m in (manual or [])}
    rows = []
    for sc in scenarios:
        sid = sc.get("id")
        executed = per_scenario.get(sid, {})
        manual_match = manual_by_scenario.get(sid)
        rows.append({
            "requirement": None,
            "ac_id": sc.get("source"),
            "scenario_id": sid,
            "designed_case": f"phase-05-design/cases/{sid}.md",
            "executed_by": executed.get("executed_in", []) + (["manual"] if manual_match else []),
            "result": executed.get("result") or (manual_match.get("result") if manual_match else "uncovered"),
            "notes": manual_match.get("notes") if manual_match else "",
        })
    return rows


def _lane_summaries(results: dict) -> list[dict]:
    return results.get("lanes") or []


def _residual_risks(exit_outcome: dict, findings: dict) -> list[dict]:
    risks = []
    for f in exit_outcome.get("failures") or []:
        risks.append({
            "id": f"R-{f['criterion']}",
            "risk": f"Exit criterion not met: {f['criterion']}",
            "severity": "High" if "critical" in str(f['criterion']).lower() or "p1" in str(f['criterion']).lower() else "Medium",
            "why_not_addressed": "Heal loop stopped at cap or fix would change a stored definition.",
            "waived_by": None,
            "mitigations": [],
        })
    return risks


def _strategy_adherence(strategy: dict, results: dict) -> dict:
    declared_lanes = {l.get("lane_skill") for l in (strategy.get("lanes") or [])}
    executed_lanes = {l.get("lane") for l in (results.get("lanes") or [])}
    deviations = []
    missing = declared_lanes - executed_lanes - {None}
    extra = executed_lanes - declared_lanes - {None}
    if missing:
        deviations.append({"kind": "declared_but_not_executed", "lanes": sorted(missing)})
    if extra:
        deviations.append({"kind": "executed_but_not_declared", "lanes": sorted(extra)})
    match = "yes" if not deviations else ("mostly" if len(deviations) <= 1 else "partial")
    return {"match": match, "deviations": deviations}


def _render_markdown(report: dict) -> str:
    sut = report["sut"]
    lines = [
        f"# Final Test Report — {sut.get('id', '?')}",
        "",
        "## 1. Executive Summary",
        "",
        report["executive_summary"],
        "",
        f"- Posture: **{report['posture']}**",
        f"- Mode: {report['mode']} | Risk: {report['risk_class']}",
        f"- Exit criteria: {'met' if report['exit_criteria_outcome'].get('passed') else 'not met'}",
        "",
        "## 2. Strategy Snapshot",
        f"See `{report['strategy_ref']}` for full strategy.",
        "",
        "## 3. Traceability Matrix",
        "| Scenario | AC / Source | Designed case | Executed by | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["traceability"]:
        lines.append(
            f"| {row['scenario_id']} | {row['ac_id'] or '-'} | {row['designed_case']} | "
            f"{', '.join(row['executed_by']) if row['executed_by'] else '-'} | {row['result']} |"
        )
    lines += [
        "",
        "## 4. Per-Lane Summary",
        "| Lane | Total | Passed | Failed | Skipped | Blocked | Critical |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for lane in report["lanes"]:
        lines.append(
            f"| {lane.get('lane', '?')} | {lane.get('total', 0)} | {lane.get('passed', 0)} | "
            f"{lane.get('failed', 0)} | {lane.get('skipped', 0)} | {lane.get('blocked', 0)} | "
            f"{lane.get('critical_findings', 0)} |"
        )
    lines += ["", "## 5. Manual Track Summary"]
    if not report["manual"]:
        lines.append("(no manual cases routed)")
    else:
        lines.append("| ID | Type | Owner | Result | Notes |")
        lines.append("| --- | --- | --- | --- | --- |")
        for m in report["manual"]:
            lines.append(f"| {m.get('id')} | {m.get('type', '-')} | {m.get('owner', '-')} | {m.get('result')} | {m.get('notes', '')} |")
    lines += [
        "",
        "## 6. Heal Loop",
        f"- Iterations: {report['heal_loop']['iterations']} (cap: {report['heal_loop']['cap']})",
        f"- Outcome: {report['heal_loop']['outcome']}",
    ]
    lines += [
        "",
        "## 7. HITL Audit Trail",
        "| Phase | Decision | Approver | Role | Approved at | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for g in report["hitl_audit"]:
        lines.append(
            f"| {g.get('phase')} | {g.get('decision')} | {g.get('approver', '-')} | "
            f"{g.get('approver_role', '-')} | {g.get('ts') or g.get('approved_at', '-')} | {g.get('notes', '')} |"
        )
    lines += ["", "## 8. Residual Risks and Waivers"]
    if not report["residual_risks"]:
        lines.append("(none)")
    else:
        lines.append("| ID | Risk | Severity | Why not addressed |")
        lines.append("| --- | --- | --- | --- |")
        for r in report["residual_risks"]:
            lines.append(f"| {r['id']} | {r['risk']} | {r['severity']} | {r['why_not_addressed']} |")
    lines += [
        "",
        "## 9. Open Follow-ups",
        "(none)" if not report["open_followups"] else "",
        "",
        "## 10. Strategy Adherence",
        f"Match: **{report['strategy_adherence']['match']}**",
    ]
    for d in report["strategy_adherence"]["deviations"]:
        lines.append(f"- {d['kind']}: {', '.join(d['lanes'])}")
    lines += [
        "",
        "## 11. Sign-off",
        "Filled in at the phase-13 HITL gate.",
        "",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="Path to .test-lifecycle/run-<ts>/")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.workspace.exists():
        print(f"Error: workspace not found: {args.workspace}", file=sys.stderr)
        return 2
    result = compile_report(args.workspace)
    print(f"Wrote: {result['report_md']}")
    print(f"Wrote: {result['report_json']}")
    print(f"Posture: {result['posture']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
