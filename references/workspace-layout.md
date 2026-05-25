# Workspace Layout

The orchestrator's per-run workspace lives at `<codebase>/.test-lifecycle/run-<YYYYMMDD-HHMMSS>/`.

## Tree

```
<codebase>/.test-lifecycle/run-20260525-143200/
├── state.json                   # current phase, mode, risk class, exit criteria
├── audit-log.jsonl              # append-only log of phase transitions + gate decisions
├── gates/                       # PAUSED-PHASE-N-<reason>.md files; renamed to RESOLVED- when approved
├── phase-01-intake/
│   └── intake.md
├── phase-01b-hitl/
│   └── policy.md
├── phase-02-ac/                 # skipped if AC already clean
│   ├── ac.md
│   └── ac.json
├── phase-03-analysis/
│   ├── analysis.md
│   └── risks.json
├── phase-04-strategy/
│   ├── strategy.md
│   └── strategy.json            # load-bearing — read by every later phase
├── phase-05-design/
│   └── cases/
│       ├── S-001.md
│       ├── S-002.md
│       └── ...
├── phase-06-quality/
│   └── review.md
├── phase-07-data/               # skipped if synthetic_required=false
│   ├── customers.csv
│   └── ...
├── phase-08-export/
│   ├── gherkin/                 # or xray/, testrail/, etc. per chosen format
│   └── ...
├── phase-09b-manual/
│   ├── checklist.md
│   └── results.json             # filled in by human/team after manual execution
├── phase-10-results/
│   ├── aggregated.json
│   ├── lane-unit/
│   │   ├── results.json
│   │   └── log.txt
│   ├── lane-playwright/
│   └── ...
├── phase-11-review/
│   └── review.md
├── phase-12-heal/
│   ├── iter-1.md
│   ├── iter-2.md
│   └── ...
└── phase-13-report/
    ├── report.md
    └── report.json
```

## Key files

### `state.json`

Tracks where the run is and what was decided.

```json
{
  "run_id": "run-20260525-143200",
  "started_at": "2026-05-25T14:32:00Z",
  "codebase_path": "C:/projects/foo",
  "current_phase": 4,
  "current_phase_status": "paused-at-gate",
  "mode": "standard",
  "risk_class": "high",
  "sut": { "id": "...", "type": "webapp" },
  "exit_criteria": { ... },        // mirrored from strategy.json once phase 4 is done
  "heal_cap": 4,
  "heal_iterations": 0,
  "gates_resolved": [],
  "gates_pending": ["phase-04-strategy-approval"],
  "audit_log_path": "audit-log.jsonl"
}
```

### `audit-log.jsonl`

Append-only JSON-lines. One line per phase transition or gate decision.

```jsonl
{"ts": "...", "phase": 1, "event": "start"}
{"ts": "...", "phase": 1, "event": "end", "output": "phase-01-intake/intake.md"}
{"ts": "...", "phase": 1b, "event": "dispatch", "intent": "design_hitl_controls"}
{"ts": "...", "phase": 1b, "event": "end", "output": "phase-01b-hitl/policy.md", "mode": "standard"}
...
{"ts": "...", "phase": 4, "event": "gate-write", "file": "gates/PAUSED-PHASE-04-strategy-approval.md"}
{"ts": "...", "phase": 4, "event": "gate-resolve", "decision": "approved", "approver": "user", "evidence": "phase-04-strategy/strategy.md"}
{"ts": "...", "phase": 5, "event": "start"}
```

The audit log is **load-bearing for full mode** — the final report's audit-trail section reads from it.

### `gates/`

When a HITL gate triggers, the orchestrator writes `PAUSED-PHASE-N-<reason>.md`. Format defined in [hitl-gate-protocol.md](hitl-gate-protocol.md).

When the human approves, they either:

1. Add `approved: true` (or `approved: false` with reason) to the file's top section, OR
2. Rename the file to `RESOLVED-PHASE-N-<reason>.md`

On the next orchestrator invocation, the gate is scanned and the run resumes.

## Resume semantics

When the user re-invokes the orchestrator with a workspace path:

1. Read `state.json`
2. Check `gates_pending` — for each, look in `gates/` for a resolved file
3. If all pending gates are resolved (approved), continue from `current_phase + 1`
4. If any gate is resolved with `approved: false`, log and stop the run
5. If a gate is still pending unresolved, return the same pause message

## Multiple concurrent runs

A codebase can have multiple `run-*` directories (e.g., one per feature being tested). The orchestrator operates on exactly one run at a time, specified by `--workspace` (or auto-detects the most recent unresolved run).

## Cleanup

`.test-lifecycle/` is intentionally NOT gitignored by default. Teams can choose to:

- Commit completed runs (audit-trail value for regulated work) — full mode default
- Gitignore in-progress runs but commit final reports — standard mode default
- Gitignore the whole directory — lite mode default

The orchestrator does not enforce a policy; it documents the choice in the README the user can adapt.
