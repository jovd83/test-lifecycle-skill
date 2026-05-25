# Final Report Template

Phase 13 output. Defined here both as a Markdown template and as a JSON schema. The compile script (`scripts/compile_report.py`) assembles both from artifacts in the run workspace.

## Markdown structure

The report MUST follow this section order (sections may be empty if not applicable, but the headings must be present):

```markdown
# Final Test Report — <SUT id>

## 1. Executive Summary
- SUT, mode, risk class
- Posture: green | green-with-caveats | residual-risk | blocked
- Top 3 outcomes (one-liners)
- Sign-off block (filled in at phase 13 HITL gate)

## 2. Strategy Snapshot
(Mirrors phase-04-strategy/strategy.md highlights)
- Levels in scope
- Lanes used
- Exit criteria
- Heal cap

## 3. Traceability Matrix
| Requirement | AC ID | Scenario ID | Designed case | Executed by | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- |

## 4. Per-Lane Summary
| Lane | Total | Passed | Failed | Skipped | Blocked | Critical findings |
| --- | --- | --- | --- | --- | --- | --- |

## 5. Manual Track Summary
| Manual ID | Type | Owner | Result | Notes |
| --- | --- | --- | --- | --- |

## 6. Heal Loop
- Iterations: N (cap: M)
- Outcome: exit-criteria-met | stopped-at-cap | gate-12-decision-made
- Iteration log (per iter: classification of failures, actions, results)

## 7. HITL Audit Trail
| Phase | Gate | Decision | Approver | Approver role | Approved at | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |

## 8. Residual Risks and Waivers
| ID | Risk | Severity | Why not addressed | Waived by | Mitigations in place |
| --- | --- | --- | --- | --- | --- |

## 9. Open Follow-ups
| ID | Item | Owner | Due |
| --- | --- | --- | --- |

## 10. Strategy Adherence
- Did the executed work match the approved phase-4 strategy? yes | mostly | partial | no
- Deviations (and why)

## 11. Sign-off
Filled in at the phase-13 HITL gate.
```

## JSON schema (`report.json`)

```json
{
  "schema_version": "1.0",
  "report_kind": "test-lifecycle-final-report",
  "run_id": "run-20260525-143200",
  "generated_at": "2026-05-25T18:00:00Z",
  "sut": { "id": "...", "type": "webapp", "summary": "..." },
  "mode": "standard",
  "risk_class": "high",
  "posture": "green | green-with-caveats | residual-risk | blocked",
  "executive_summary": "string",
  "strategy_ref": "phase-04-strategy/strategy.json",
  "exit_criteria_outcome": {
    "evaluated_against": "phase-10-results/aggregated.json",
    "passed": true,
    "details": { ... mirror from check_exit_criteria.py output ... }
  },
  "traceability": [
    {
      "requirement": "string or null",
      "ac_id": "AC-12",
      "scenario_id": "S-001",
      "designed_case": "phase-05-design/cases/S-001.md",
      "executed_by": ["lane-playwright", "lane-unit"],
      "result": "pass | fail | blocked | skipped",
      "notes": "string"
    }
  ],
  "lanes": [
    {
      "lane": "playwright-skill",
      "total": 12, "passed": 10, "failed": 2, "skipped": 0, "blocked": 0,
      "critical_findings": 0,
      "results_path": "phase-10-results/lane-playwright/results.json"
    }
  ],
  "manual": [
    {
      "id": "MAN-001",
      "type": "exploratory",
      "owner": "QA lead",
      "result": "pass",
      "notes": "string"
    }
  ],
  "heal_loop": {
    "iterations": 2,
    "cap": 4,
    "outcome": "exit-criteria-met",
    "log": ["phase-12-heal/iter-1.md", "phase-12-heal/iter-2.md"]
  },
  "hitl_audit": [
    {
      "phase": 4,
      "gate": "strategy-approval",
      "decision": "approved",
      "approver": "jovd83",
      "approver_role": "QA lead",
      "approved_at": "2026-05-25T15:10:00Z",
      "evidence": "phase-04-strategy/strategy.md",
      "notes": "R3 risk owner confirmed as SRE"
    }
  ],
  "residual_risks": [],
  "open_followups": [],
  "strategy_adherence": {
    "match": "yes | mostly | partial | no",
    "deviations": []
  },
  "signoff": {
    "approved": null,            // filled at phase-13 HITL gate
    "approver": null,
    "approver_role": null,
    "approved_at": null,
    "notes": null
  }
}
```

## Compile script

`scripts/compile_report.py --workspace <path-to-run>` reads:

- `state.json` — for mode, risk, run id
- `phase-01-intake/intake.md` — for SUT details
- `phase-04-strategy/strategy.json` — for strategy snapshot, traceability seed (scenarios)
- `phase-10-results/aggregated.json` — for per-lane results, per-scenario outcomes
- `phase-09b-manual/results.json` — for manual track
- `phase-12-heal/iter-*.md` — for heal loop log
- `audit-log.jsonl` — for HITL audit trail entries

And writes `phase-13-report/report.md` and `phase-13-report/report.json`.

## Posture decision

```
posture =
  "blocked"             if any phase-12 gate is rejected, or a Critical finding remains unresolved
  "residual-risk"       if heal loop stopped at cap with open High findings or unmet P1 pass rate
  "green-with-caveats"  if exit criteria met but residual Medium findings or waivers exist
  "green"               if exit criteria met clean
```

The posture is computed by `compile_report.py` based on `exit_criteria_outcome` + residual findings count by severity.

## Distinguishing "done" from "stopped at cap"

The posture must NOT collapse:

- `posture: green` → exit criteria met, no caveats
- `posture: green-with-caveats` → exit criteria met but minor open items
- `posture: residual-risk` → **stopped at cap** OR exit criteria failed and the heal loop ran out of room
- `posture: blocked` → gate rejected, run aborted

The executive summary must restate this in plain language so a reviewer doesn't have to infer.
