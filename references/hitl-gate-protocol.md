# HITL Gate Protocol

Every HITL pause in the chain follows the same protocol. Read this whenever you write a PAUSED file or evaluate one for resume.

## When a gate triggers

The orchestrator:

1. Writes `gates/PAUSED-PHASE-<N>-<short-reason>.md` (see template below)
2. Appends a `gate-write` line to `audit-log.jsonl`
3. Updates `state.json`: `current_phase_status: "paused-at-gate"`, adds the gate name to `gates_pending`
4. Returns a short message to the user with:
   - The gate file path
   - What's being approved (one sentence)
   - How to approve (the two methods below)
5. Stops. Does not invoke any further phase.

## How the human resolves a gate

Two equivalent methods:

### Method A — edit the file in place

Open the `PAUSED-PHASE-N-<reason>.md` file. At the top, replace the `approved:` line:

```markdown
---
status: paused
phase: 4
reason: strategy-approval
approved: true                # or: false
approver: jovd83
approver_role: QA lead
approved_at: 2026-05-25T15:10:00Z
notes: Looks good. R3 risk owner is confirmed as SRE.
---
```

(If rejecting, set `approved: false` and put the rejection reason in `notes`.)

### Method B — rename the file

Rename `PAUSED-PHASE-04-strategy-approval.md` → `RESOLVED-PHASE-04-strategy-approval.md`. The orchestrator treats the rename as `approved: true` with no notes.

(For rejection, rename to `REJECTED-PHASE-04-strategy-approval.md`.)

Method A is preferred when there's nuance (notes, approver identity, conditional approval). Method B is the quick-confirm path.

## How the orchestrator evaluates a gate on resume

1. Find any `PAUSED-PHASE-N-*.md` file in `gates/`.
2. Parse the frontmatter. If `approved: true` or filename is `RESOLVED-*`, the gate is approved.
3. Append a `gate-resolve` line to `audit-log.jsonl` with the decision, approver, evidence link.
4. Move `gates_pending` → `gates_resolved` in `state.json`.
5. Continue from `current_phase + 1`.

If `approved: false` or filename is `REJECTED-*`:

- Append a `gate-reject` line to `audit-log.jsonl`.
- Stop the run. Set `state.json.current_phase_status: "rejected"`.
- Return a clear message to the user with the rejection reason.
- Do not auto-retry. The user must explicitly start a new run or address the rejection and re-invoke.

## Gate file template

```markdown
---
status: paused
phase: 4
phase_name: strategy-approval
mode: standard
risk_class: high
approver_role: QA lead
approved:                       # ← human fills in: true | false
approver:                       # ← human fills in
approved_at:                    # ← human fills in: ISO-8601
notes:                          # ← optional rejection reason or qualifying notes
---

# Phase 4 — Strategy Approval

## What you're approving

The test strategy for [SUT id and short summary].

## Artifacts to review

- `phase-04-strategy/strategy.md` — full strategy document
- `phase-04-strategy/strategy.json` — machine-readable sidecar (read by later phases)

## Key decisions in the strategy

- Mode: standard | Risk class: high
- Levels in scope: unit, component, integration, system
- Lanes: stack-aware-unit-testing-skill, playwright-skill, performance-testing-skill, a11y-audit-agent-skill, defensive-appsec-review-skill
- Top 3 scenarios (Critical/High): [list]
- Exit criteria: overall_pass_rate ≥ 95%, P1 = 100%, open High = 0
- HITL gates active downstream: phase 8, phase 13

## Open Questions (you may want to resolve before approving)

| ID | Question | Blocker | Owner |
| --- | --- | --- | --- |
| Q-1 | ... | yes | Product |

## How to approve

**Quick:** rename this file to `RESOLVED-PHASE-04-strategy-approval.md`.
**With notes:** edit the frontmatter above (`approved: true`, fill in approver fields, add notes).

**To reject:** set `approved: false` with a reason in `notes`, OR rename to `REJECTED-PHASE-04-strategy-approval.md`.

## What happens next

On approval, the chain resumes at phase 5 (test design). The next gate will be at phase 8 (export approval).
```

## Approver role expectations

Mode-aware (from phase 1b policy):

| Phase | Lite | Standard | Full |
| --- | --- | --- | --- |
| 4 | n/a | QA lead | QA lead + Security |
| 8 | n/a | QA lead | QA lead |
| 9 (per lane) | n/a | n/a | Lane owner |
| 12 | n/a | n/a | QA lead |
| 13 | Owner / QA lead | Product owner | Product owner + Compliance |

The gate file pre-fills `approver_role`. The human is expected to be (or stand in for) that role.

## Audit log entries for gates

```jsonl
{"ts": "2026-05-25T15:00:00Z", "phase": 4, "event": "gate-write", "file": "gates/PAUSED-PHASE-04-strategy-approval.md", "approver_role": "QA lead"}
{"ts": "2026-05-25T15:10:00Z", "phase": 4, "event": "gate-resolve", "decision": "approved", "approver": "jovd83", "approver_role": "QA lead", "evidence": "phase-04-strategy/strategy.md", "notes": "R3 risk owner is confirmed as SRE."}
```

## Special cases

### Per-lane Critical pause (phase 9, full mode)

When a single lane surfaces a Critical-severity finding mid-execution, **only that lane pauses**. Other lanes continue. The gate file lists the specific finding and which lane is blocked. On approval, the user can:

- "Continue with triage outcome" — the lane resumes (perhaps with the finding marked as accepted residual risk)
- "Stop the lane" — the lane is marked complete with the finding as a blocker; the chain continues to phase 11 with that lane's results frozen

### Heal-loop cap pause (phase 12, full mode)

When the heal loop hits its iteration cap without exit criteria met, OR a fix requires changing a stored case definition (a phase-8 artifact), pause. The gate file summarizes:

- What exit criteria are not met
- What iterations were attempted
- The proposed next action (stop with residual risk, increase cap, redesign cases — which would invalidate the phase-8 approval)

### Final sign-off (phase 13, all modes)

Always paused. The user signs off on the final report. The sign-off identity + timestamp are appended to `audit-log.jsonl` and embedded in `phase-13-report/report.json`.
