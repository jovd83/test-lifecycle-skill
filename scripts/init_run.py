"""Initialize a new test-lifecycle run workspace.

Creates `<codebase>/.test-lifecycle/run-YYYYMMDD-HHMMSS/` with:
- state.json (from assets/state-template.json)
- audit-log.jsonl (empty)
- gates/ (empty directory)
- phase-NN-* subdirectories per phase

Usage:
    python scripts/init_run.py --codebase ./apps/storefront --change-id WEB-CHECKOUT-2026
    python scripts/init_run.py --codebase . --change-id ad-hoc --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PHASE_DIRS = [
    "phase-01-intake",
    "phase-01b-hitl",
    "phase-02-ac",
    "phase-03-analysis",
    "phase-04-strategy",
    "phase-05-design",
    "phase-06-quality",
    "phase-07-data",
    "phase-08-export",
    "phase-09b-manual",
    "phase-10-results",
    "phase-11-review",
    "phase-12-heal",
    "phase-13-report",
]


def find_state_template() -> Path:
    """Find the assets/state-template.json next to this script."""
    here = Path(__file__).resolve().parent
    candidate = here.parent / "assets" / "state-template.json"
    if not candidate.exists():
        raise FileNotFoundError(f"state template not found at {candidate}")
    return candidate


def init_run(codebase: Path, change_id: str) -> dict:
    if not codebase.exists():
        raise FileNotFoundError(f"codebase path does not exist: {codebase}")

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    run_id = f"run-{timestamp}"

    lifecycle_root = codebase / ".test-lifecycle"
    run_dir = lifecycle_root / run_id

    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")

    run_dir.mkdir(parents=True)
    (run_dir / "gates").mkdir()
    for phase in PHASE_DIRS:
        (run_dir / phase).mkdir()

    state_template = find_state_template()
    state = json.loads(state_template.read_text(encoding="utf-8"))
    state["run_id"] = run_id
    state["started_at"] = now.isoformat()
    state["codebase_path"] = str(codebase.resolve())
    if change_id:
        state["sut"]["id"] = change_id

    (run_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (run_dir / "audit-log.jsonl").write_text("", encoding="utf-8")

    # Bootstrap audit entry
    audit_entry = {
        "ts": now.isoformat(),
        "phase": 0,
        "event": "run-init",
        "run_id": run_id,
        "change_id": change_id,
    }
    with (run_dir / "audit-log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(audit_entry) + "\n")

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "state_path": str(run_dir / "state.json"),
        "audit_log_path": str(run_dir / "audit-log.jsonl"),
        "phase_dirs_created": len(PHASE_DIRS),
    }


def format_text(result: dict) -> str:
    lines = [
        f"Initialized run: {result['run_id']}",
        f"  Run directory:   {result['run_dir']}",
        f"  State file:      {result['state_path']}",
        f"  Audit log:       {result['audit_log_path']}",
        f"  Phase dirs:      {result['phase_dirs_created']}",
        "",
        "Next step: dispatch phase 1 (Intake) — gather SUT, risk class, mode hint.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codebase", type=Path, required=True, help="Path to the target codebase.")
    parser.add_argument("--change-id", default="", help="Short ID for the change being tested (e.g. WEB-CHECKOUT-2026).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = init_run(args.codebase, args.change_id)
    except (FileNotFoundError, FileExistsError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
