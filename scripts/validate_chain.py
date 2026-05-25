"""Validate the chain.json definition for internal consistency and runtime alignment.

Checks:
1. Schema integrity (required fields per phase, mode, gate)
2. Every phase referenced in a mode's burst exists in phases[]
3. Every gate referenced as ends_with_gate or in active_gates is defined in gates[]
4. Every default_skill named in a phase exists on the runtime skills tree (~/.agents/skills/) — warning, not error
5. Every gate phase ID matches an existing phase
6. Mode bursts cover all non-skip-only phases (every phase appears in some burst per mode)
7. mode_risk_pairings has all four risk classes

Exit code 0 = no errors. Non-zero = errors found (warnings do not fail).

Usage:
    python scripts/validate_chain.py                  # uses assets/chain.json next to script
    python scripts/validate_chain.py --chain path.json --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REQUIRED_PHASE_FIELDS = {"id", "ordinal", "name", "inline", "intent", "default_skill", "gate_after"}
REQUIRED_MODE_FIELDS = {"bursts", "heal_cap", "active_gates", "mode_risk_pairings"}
REQUIRED_GATE_FIELDS = {"phase", "modes_active", "approver_role", "what_is_approved"}
ALL_MODES = {"lite", "standard", "full"}
ALL_RISKS = {"low", "medium", "high", "critical"}


def default_chain_path() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "assets" / "chain.json"


def default_runtime_root() -> Path:
    env = os.environ.get("SKILLS_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".agents" / "skills"


def validate(chain: dict, runtime_root: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Schema integrity — phases
    phases = chain.get("phases") or []
    if not phases:
        errors.append("phases[] is empty")
    phase_ids = {p.get("id") for p in phases if isinstance(p, dict)}
    for p in phases:
        if not isinstance(p, dict):
            errors.append(f"non-object in phases[]: {p!r}")
            continue
        missing = REQUIRED_PHASE_FIELDS - set(p.keys())
        if missing:
            errors.append(f"phase {p.get('id', '?')!r} missing fields: {sorted(missing)}")
        gate_after = p.get("gate_after") or {}
        for mode in ALL_MODES:
            if mode not in gate_after:
                errors.append(f"phase {p.get('id')!r}.gate_after missing mode '{mode}'")

    # 2. Modes integrity
    modes = chain.get("modes") or {}
    if set(modes.keys()) != ALL_MODES:
        errors.append(f"modes must define exactly {sorted(ALL_MODES)}, got {sorted(modes.keys())}")
    for mode_name, mode_def in modes.items():
        if not isinstance(mode_def, dict):
            errors.append(f"mode {mode_name!r} is not an object")
            continue
        missing = REQUIRED_MODE_FIELDS - set(mode_def.keys())
        if missing:
            errors.append(f"mode {mode_name!r} missing fields: {sorted(missing)}")
        # mode_risk_pairings
        pairings = mode_def.get("mode_risk_pairings") or {}
        if set(pairings.keys()) != ALL_RISKS:
            errors.append(f"mode {mode_name!r}.mode_risk_pairings must cover {sorted(ALL_RISKS)}, got {sorted(pairings.keys())}")
        # bursts reference real phases
        bursts = mode_def.get("bursts") or []
        seen_in_bursts: set[str] = set()
        for i, burst in enumerate(bursts):
            for pid in burst.get("phases") or []:
                if pid not in phase_ids:
                    errors.append(f"mode {mode_name!r} burst {i} references unknown phase {pid!r}")
                seen_in_bursts.add(pid)
        # Every non-skip-only phase should appear in at least one burst
        for p in phases:
            pid = p.get("id")
            if pid not in seen_in_bursts:
                # Skip-conditional phases still appear in bursts; absence is a real issue
                errors.append(f"mode {mode_name!r}: phase {pid!r} appears in no burst")

    # 3. Gates integrity
    gates = chain.get("gates") or {}
    for gate_name, gate_def in gates.items():
        missing = REQUIRED_GATE_FIELDS - set(gate_def.keys())
        if missing:
            errors.append(f"gate {gate_name!r} missing fields: {sorted(missing)}")
        gate_phase = gate_def.get("phase")
        if gate_phase not in phase_ids:
            errors.append(f"gate {gate_name!r} references unknown phase {gate_phase!r}")
        for mode in gate_def.get("modes_active") or []:
            if mode not in ALL_MODES:
                errors.append(f"gate {gate_name!r} has invalid mode {mode!r}")

    # Gates referenced from modes must exist in gates[]
    for mode_name, mode_def in modes.items():
        for gate_name in mode_def.get("active_gates") or []:
            if gate_name not in gates:
                errors.append(f"mode {mode_name!r}.active_gates references undefined gate {gate_name!r}")
        for burst in mode_def.get("bursts") or []:
            ends = burst.get("ends_with_gate")
            if ends and not any(ends.startswith(g) for g in gates):
                # Allow conditional notations like "phase-12-heal-decision (conditional)"
                bare = ends.split(" ")[0]
                if bare not in gates:
                    warnings.append(f"mode {mode_name!r} burst ends_with_gate {ends!r} does not match any gate name")

    # 4. Skills present on runtime tree (warning, not error)
    if runtime_root.exists():
        present_skills = {p.name for p in runtime_root.iterdir() if p.is_dir()}
    else:
        present_skills = set()
        warnings.append(f"runtime skills root not found: {runtime_root}")
    for p in phases:
        skill = p.get("default_skill")
        if skill and isinstance(skill, str) and skill not in present_skills:
            warnings.append(f"phase {p.get('id')!r}.default_skill {skill!r} not present in runtime tree")

    # Lane-dispatch skills (phase 9a)
    for p in phases:
        if p.get("id") == "9a":
            for lane_skill in (p.get("lane_dispatch_intents") or {}):
                if lane_skill not in present_skills:
                    warnings.append(f"phase 9a lane {lane_skill!r} not present in runtime tree (expected for planned skills)")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "phase_count": len(phases),
        "modes_count": len(modes),
        "gates_count": len(gates),
        "runtime_root": str(runtime_root),
        "runtime_root_exists": runtime_root.exists(),
    }


def format_text(result: dict) -> str:
    lines = []
    status = "OK" if result["ok"] else "FAIL"
    lines.append(f"chain.json validation: {status}")
    lines.append(f"  phases:  {result['phase_count']}")
    lines.append(f"  modes:   {result['modes_count']}")
    lines.append(f"  gates:   {result['gates_count']}")
    lines.append(f"  runtime: {result['runtime_root']} (exists={result['runtime_root_exists']})")
    if result["errors"]:
        lines.append("")
        lines.append(f"ERRORS ({len(result['errors'])}):")
        for e in result["errors"]:
            lines.append(f"  - {e}")
    if result["warnings"]:
        lines.append("")
        lines.append(f"WARNINGS ({len(result['warnings'])}):")
        for w in result["warnings"]:
            lines.append(f"  - {w}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chain", type=Path, default=None, help="Path to chain.json (default: assets/chain.json)")
    parser.add_argument("--runtime-root", type=Path, default=None, help="Override runtime skills root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    chain_path = args.chain or default_chain_path()
    runtime_root = args.runtime_root or default_runtime_root()

    try:
        chain = json.loads(chain_path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"Error reading {chain_path}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Error: chain.json is not valid JSON: {exc}", file=sys.stderr)
        return 2

    result = validate(chain, runtime_root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
