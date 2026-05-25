---
name: test-lifecycle-skill
description: Use when the user wants end-to-end testing for a change — running a requirement, feature, webapp, UI, batch job, API, or release through the full 13-phase lifecycle (intake → HITL design → analysis → strategy → design → quality gate → data prep → export → automation + manual track in parallel → execution → functional review → heal loop → final report). Dispatches to phase-specific skills and pauses at HITL gates for approval. Use whenever the user asks to "test this end-to-end", "plan and execute testing", "run the test chain", or "deliver a verified, documented test pass". Do not use for one-off planning (use test-strategy-skill) or one-off case design (use test-design-orchestrator).
metadata:
  dispatcher-layer: orchestration
  dispatcher-lifecycle: active
  dispatcher-category: testing
  dispatcher-capabilities: test-orchestration, lifecycle-management, hitl-gate-control, heal-loop-control
  dispatcher-accepted-intents: run_test_lifecycle, orchestrate_end_to_end_testing, resume_test_lifecycle
  dispatcher-input-artifacts: change_request, requirement, story, feature_description, codebase_path
  dispatcher-output-artifacts: lifecycle_run_workspace, strategy_document, executed_test_results, functional_review_report, final_test_report
  dispatcher-stack-tags: testing, orchestration, framework-agnostic
  dispatcher-risk: high
  dispatcher-writes-files: true

---

# Test Lifecycle Skill

> **Author:** jovd83 | **Version:** 1.0.0

Orchestrate a software change through 13 phases of disciplined testing — from intake through to a signed-off final report — by dispatching to phase-specific skills and pausing at HITL (human-in-the-loop) gates for explicit approval.

## Responsibilities

- Walk a change through the 13-phase test lifecycle: intake → HITL design → AC normalization → analysis → strategy → design → case quality gate → test data → export → 9a automation + 9b manual track (parallel) → execution → functional review → heal loop → final report.
- Dispatch each phase to its dedicated skill via `skill-dispatcher` (intent-based routing).
- Apply the HITL mode chosen in phase 1b (`lite` / `standard` / `full`) — pause at the right gates, log every decision.
- Run the parallel 9a (automated) and 9b (manual) tracks based on the routing emitted in phase 4.
- Enforce phase-4 exit criteria in the phase-12 heal loop until met or the iteration cap is hit.
- Produce a final report (phase 13) with a traceability matrix (requirement → AC → scenario → script → result) and the audit trail.

## Boundaries

- Do not author test cases, run individual tests, design strategy docs, or analyze requirements yourself — dispatch to the phase skills.
- Do not skip HITL gates when the mode says they're active. Do not invent gates the mode does not require.
- Do not silently drop a manual-track item from the strategy's routing — phase 9b runs even if all manual cases are marked optional.
- Do not modify the strategy document mid-run. If a fix needs the strategy changed (e.g., a new scenario surfaces), pause at the phase-12 gate.
- Do not run end-to-end on production environments without the explicit env target coming from phase-4 strategy.
- Do not create persistent shared-memory behavior. Per-run state lives in the workspace; project-wide policy belongs in an external shared-memory skill.

## Dispatcher Integration

Use `skill-dispatcher` as the primary integration layer. Prefer dispatching by intent; treat direct skill paths as fallback only when the dispatcher has no registry match.

Phase → intent mapping (full table in [references/phase-map.md](references/phase-map.md)):

| Phase | Intent | Default skill |
| --- | --- | --- |
| 1 Intake | (inline — gather structured Q&A) | n/a |
| 1b HITL Controls Design | `design_hitl_controls` | `eu-ai-act-hitl-oversight-skill` |
| 2 AC Normalization (skip-if AC exist) | `normalize_acceptance_criteria` | `acceptance-criteria-designer` |
| 3 Test Analysis | `analyze_requirements_for_testability` | `test-analysis-skill` |
| 4 Test Strategy | `design_test_strategy` | `test-strategy-skill` |
| 5 Test Design | `generate_structured_test_cases` | `test-design-orchestrator` |
| 6 Case Quality Gate | `review_test_cases` | `tss-test-case-reviewer` |
| 7 Test Data (skip-if not needed) | `generate_synthetic_data` | `lifelike-synthetic-data-generator` |
| 8 Artifact Export | `render_test_artifact` | `test-artifact-export-skill` |
| 9a Automation lanes | per lane intent (from phase-4 strategy.lanes) | per lane (e.g. `playwright-skill`) |
| 9b Manual track | (inline — produce manual execution checklist) | n/a |
| 10 Execution | (per lane, runs inside 9a) | n/a |
| 11 Functional Review | `review_automation_quality` | `automated-test-reviewer` |
| 12 Heal Loop | (inline — orchestrator decides) | n/a |
| 13 Final Report | (inline — orchestrator compiles) | n/a |

## Inputs To Confirm Or Infer

Before initializing a run, confirm or infer:

- **Change scope** — what is being tested (story ID, feature name, PR, requirement doc).
- **Codebase path** — for stack detection in phase 4 and lane wiring in phase 9a.
- **Risk class hint** — low / medium / high / critical (the orchestrator may override based on phase 3 analysis).
- **HITL mode hint** — lite / standard / full (phase 1b will confirm with the user).
- **Workspace root** — defaults to `<codebase_path>/.test-lifecycle/`. Each run gets `run-YYYYMMDD-HHMMSS/`.

If the change scope is unclear, stop and ask. Do not invent a SUT to test.

## Workspace Initialization

Every run gets a fresh workspace. Run:

```bash
python scripts/init_run.py --codebase <path> --change-id <id>
```

This creates `<codebase>/.test-lifecycle/run-<timestamp>/` with:

- `state.json` — current phase, gate status, mode, risk class, configured exits
- `phase-01-intake/` … `phase-13-report/` — one subdirectory per phase
- `gates/` — for PAUSED-PHASE-N.md files written when HITL gates trigger
- `audit-log.jsonl` — append-only log of every phase transition and gate decision

See [references/workspace-layout.md](references/workspace-layout.md) for the full layout.

## Chain Source of Truth

The 13-phase definition, mode bursts, gate map, approver roles, and lane-dispatch intents are all defined in **[assets/chain.json](assets/chain.json)** — a single machine-readable artifact. The orchestrator reads chain.json at runtime; the prose in SKILL.md and `references/*.md` mirrors it for human readability.

To check that chain.json is internally consistent and that the named skills exist on the runtime tree, run:

```bash
python scripts/validate_chain.py
```

This catches: missing required fields, mode bursts that reference unknown phases, gate references that don't resolve, and skills that aren't installed. If chain.json and the prose drift apart, the validator is the canonical reference — fix the prose.

## Workflow

The chain runs in **autonomous bursts between HITL gates**. The orchestrator does as many phases as the mode allows in a single invocation, then writes a PAUSED-PHASE-N.md gate file and returns control to the user. The user reviews, approves (or rejects with feedback), and re-invokes the orchestrator to continue.

### Burst boundaries by mode

| Mode | Autonomous bursts | Gates that pause |
| --- | --- | --- |
| **lite** | One burst covers phases 1 → 12 (auto-stop on heal cap). Then burst 2 = phase 13. | phase 13 only |
| **standard** | Burst 1: 1 → 4. Burst 2: 5 → 8. Burst 3: 9a‖9b → 12. Burst 4: 13. | phases 4, 8, 13 |
| **full** | Burst 1: 1 → 4. Burst 2: 5 → 8. Burst 3: 9a‖9b (with per-lane Critical pauses) → 11. Burst 4: 12 (paused on cap or definition-changing fix). Burst 5: 13. | phases 4, 8, 9, 12, 13 |

### 1. Intake (inline)

Gather and write `phase-01-intake/intake.md` with at minimum:

- SUT id, type (requirement / feature / webapp / UI / batch / API / library / ml-model)
- Risk class (low / medium / high / critical) — provisional
- HITL mode hint
- Environments available
- Inputs available (story link, AC list, code path, prior analysis)
- Constraints (deadlines, regulated data, compliance posture)

If acceptance criteria are inlined in the user's prompt, capture them now. Persist intake to `state.json`.

### 1b. HITL Controls Design

Dispatch `design_hitl_controls` to produce a HITL policy doc. Persist to `phase-01b-hitl/policy.md` and update `state.json` with the confirmed mode.

If `lite` mode is chosen but risk class is `critical`, the policy step must surface this mismatch (the skill should refuse to auto-proceed; the human can override but only after explicit acknowledgement).

### 2. AC Normalization (skip-if AC exist and pass review)

If intake supplied clean ACs, skip to phase 3 and note the skip in audit log.

Otherwise dispatch `normalize_acceptance_criteria`. Persist normalized AC list to `phase-02-ac/ac.md` and `phase-02-ac/ac.json`.

### 3. Test Analysis

Dispatch `analyze_requirements_for_testability` against the AC list + intake. Persist to `phase-03-analysis/analysis.md` and the structured findings to `phase-03-analysis/risks.json`.

### 4. Test Strategy

Dispatch `design_test_strategy` with intake + HITL policy + ACs + analysis. The phase-4 skill writes `phase-04-strategy/strategy.md` and `phase-04-strategy/strategy.json`. The latter is load-bearing — every later phase reads it.

### Gate: Phase 4 (lite: skip · standard, full: pause)

Write `gates/PAUSED-PHASE-04-strategy-approval.md` summarizing:

- The strategy doc location
- Open Questions from the strategy
- What the human is approving (scope, levels, types, lanes, exit criteria, mode/risk pairing)

Return to the user with the pause message. Do not proceed.

### 5. Test Design

After phase 4 gate is approved, dispatch `generate_structured_test_cases` per scenario in `strategy.json`. Persist to `phase-05-design/cases/<scenario-id>.md`.

### 6. Case Quality Gate

Dispatch `review_test_cases` against the designed cases. If any case fails quality, route back to phase 5 for that case only (mini-loop, not a HITL pause). Persist review report to `phase-06-quality/review.md`.

### 7. Test Data Prep (skip-if `strategy.json` says synthetic_required is false)

Dispatch `generate_synthetic_data` per the strategy's test_data section. Persist to `phase-07-data/`.

### 8. Artifact Export

Dispatch `render_test_artifact` to convert designed cases to the target format (Gherkin, Xray, TestRail, etc.). Persist to `phase-08-export/`.

### Gate: Phase 8 (lite: skip · standard, full: pause)

Write `gates/PAUSED-PHASE-08-export-approval.md`. The human approves the exported artifacts before automation cost is paid. Return to the user.

### 9a + 9b in parallel

After phase 8 gate is approved, fan out:

- **9a automation lanes** — for each lane in `strategy.json.lanes` with `availability=available` and `routing=automated`, dispatch the lane's intent. See [references/parallel-9a-9b.md](references/parallel-9a-9b.md) for fan-out logic.
- **9b manual track** — produce `phase-09b-manual/checklist.md` from `strategy.json.routing.manual`. The orchestrator does NOT execute manual cases — it writes the checklist for human/team execution and waits for results to be filed back into `phase-09b-manual/results.json`.

### 10. Execution

Each lane (9a) emits its own results into `phase-10-results/lane-<name>/`. The orchestrator collects them into `phase-10-results/aggregated.json`.

In `full` mode: when any lane surfaces a Critical-severity finding, that lane pauses and writes `gates/PAUSED-PHASE-09-lane-<name>-critical.md`. Other lanes continue. The user triages and approves continuation.

### 11. Functional Review

Dispatch `review_automation_quality` against the aggregated results + the original strategy. The review skill produces a mapping of:

- Strategy scenarios → executed scripts → result (pass/fail/blocked)
- Coverage gaps
- False greens (passed but missing assertions)
- Manual-track results integrated

Persist to `phase-11-review/review.md`.

### 12. Heal Loop

The orchestrator evaluates exit criteria from `strategy.json.exit_criteria` against `phase-10-results/aggregated.json` + `phase-11-review/review.md`. See [references/heal-loop-control.md](references/heal-loop-control.md) for the algorithm.

Outcomes:

- **Exit criteria met** → proceed to phase 13
- **Failures present, iterations < heal_cap** → triage each failure (real bug, flaky test, wrong assertion), apply fixes, re-run affected lanes (back to 9a/10/11)
- **Iteration cap reached OR fix would change a stored case definition (a phase-8 artifact)** → in `full` mode, pause at gate `PAUSED-PHASE-12-heal-decision.md` for human decision. In `standard`/`lite` mode, log and stop.

Each iteration writes a `phase-12-heal/iter-<n>.md` log.

### Gate: Phase 12 (full only: pause on cap or definition-changing fix)

### 13. Final Report

Run:

```bash
python scripts/compile_report.py --workspace <path-to-run>
```

This assembles `phase-13-report/report.md` and `phase-13-report/report.json` from:

- Intake + strategy summary
- Traceability matrix (requirement → AC → scenario → script → result)
- Heal-loop iteration log
- Manual-track results
- Per-phase HITL gate decisions (the audit trail)
- Risk-ranked residual gaps + waivers (if any)

### Gate: Phase 13 (all modes: pause for sign-off)

Write `gates/PAUSED-PHASE-13-final-signoff.md`. The user signs off (and the sign-off identity + timestamp are appended to `audit-log.jsonl`). Done.

## HITL Gate Protocol

Each gate follows the same protocol — write a `PAUSED-PHASE-N-<reason>.md` file in `gates/`, return a short message to the user with the file path and what they're being asked to approve, and stop. To resume, the user re-invokes the orchestrator with the run workspace path; the orchestrator reads `state.json`, checks for a resolved gate file (the user has either renamed it to `RESOLVED-PHASE-N.md` or written an `approved: true|false` line in the file), and proceeds or aborts accordingly.

See [references/hitl-gate-protocol.md](references/hitl-gate-protocol.md) for the gate-file format, approval semantics, and audit-log requirements.

## Heal Loop Discipline

- Cap iterations per the mode (lite: 2, standard: 4, full: 6 — from `strategy.json.heal_cap`).
- Root-cause every failure: real bug? flaky test? wrong assertion? assert one of these in the iteration log; never just "rerun and hope".
- If a fix requires changing a stored case definition (phase-8 artifact), pause for human decision (full mode) or log and stop (standard/lite). Definition changes invalidate the phase-8 approval.
- Re-run only the affected lane after a fix; do not re-run the whole chain.

## Final Report Contract

The phase-13 report must include:

- Executive summary (SUT, mode, posture, residual risk)
- Traceability matrix (requirement → AC → scenario → script → result)
- Per-lane summary (counts, pass rates, top failures)
- Manual-track summary
- Heal-loop iteration count + outcomes
- HITL gate audit trail (who approved what, when, with what evidence)
- Open follow-ups + waivers (if any)
- Strategy adherence: did the executed work match the approved phase-4 strategy?

Template in [assets/final-report-template.md](assets/final-report-template.md). JSON schema in [references/final-report-template.md](references/final-report-template.md).

## Memory Model

- **Runtime memory**: phase outputs, scratch notes, in-progress lane results. Lives in the run workspace; not promoted.
- **Project-local memory**: the per-run workspace itself (`<project>/.test-lifecycle/run-<ts>/`). Version-controllable if the team wants.
- **Shared memory**: out of scope. Cross-project policy (e.g., "team always prefers Playwright") belongs behind an external shared-memory skill.

Do not auto-promote findings into persistent storage. The final report is the durable artifact.

## Failure Handling

- **Phase skill missing or returns error**: log to audit, pause at the nearest gate with a `PAUSED-PHASE-N-skill-error.md` describing the failure and asking the user to install the skill, accept a fallback, or abort.
- **Strategy doc unavailable or malformed**: cannot proceed past phase 4. Pause and surface the schema error.
- **Lane unavailable mid-run**: fall back per the strategy's documented fallback. If no fallback is documented, pause at the next gate.
- **Heal cap reached with failures**: write a clear residual-risk section to the final report; do not silently mark green.
- **HITL gate file rejected**: read the user's rejection reason from the file, log, and stop the chain. Do not auto-loop into another attempt.
- **Workspace corrupted or inconsistent state**: refuse to resume; require the user to either fix the state or start a new run.

## Gotchas

- **Mode/risk mismatch ignored** — phase 1b should refuse `lite` for `critical` risk; never proceed silently.
- **Skipping phase 9b** — even when the manual list is short or "optional", emit the checklist. Silent drops break traceability.
- **Re-running the whole chain on a small fix** — phase 12 only re-runs the *affected lane*. Re-running everything wastes hours and dilutes signals.
- **Stale `strategy.json`** — the heal loop reads exit criteria from the strategy. If the human approved a different version mid-run, the orchestrator must refuse to proceed without re-approving the strategy gate.
- **Lane Critical findings stop only that lane** — other lanes continue in parallel; do not halt the world for one finding.
- **Audit log gaps** — every phase transition and gate decision MUST append a line to `audit-log.jsonl`. If the file is unwritable, fail the run; the audit trail is load-bearing for full mode.
- **"Done at heal cap" is not "done"** — exit criteria met is "done"; cap reached is "stopped, residual risk documented". The final report must distinguish these.

## Resource Map

- [references/phase-map.md](references/phase-map.md): 13 phases with intents, inputs, outputs, and skip conditions
- [references/workspace-layout.md](references/workspace-layout.md): `.test-lifecycle/run-<ts>/` directory structure and file conventions
- [references/hitl-gate-protocol.md](references/hitl-gate-protocol.md): PAUSED gate file format and resume semantics
- [references/heal-loop-control.md](references/heal-loop-control.md): iteration algorithm and cap behavior
- [references/parallel-9a-9b.md](references/parallel-9a-9b.md): lane fan-out and manual-track checklist generation
- [references/final-report-template.md](references/final-report-template.md): report structure and schema
- [assets/chain.json](assets/chain.json): **single source of truth** — 13 phases, mode bursts, gate map, lane-dispatch intents
- [assets/paused-gate-template.md](assets/paused-gate-template.md): template for PAUSED-PHASE-N gate files
- [assets/state-template.json](assets/state-template.json): initial `state.json` template
- [scripts/init_run.py](scripts/init_run.py): workspace + state initialization
- [scripts/check_exit_criteria.py](scripts/check_exit_criteria.py): evaluate strategy exit criteria against results
- [scripts/compile_report.py](scripts/compile_report.py): assemble final report from artifacts
- [scripts/validate_chain.py](scripts/validate_chain.py): chain.json consistency + runtime-skill presence validator

## Quick Prompt Examples

- `Use $test-lifecycle-skill to test the new checkout flow end-to-end; standard mode, repo at ./apps/storefront.`
- `Use $test-lifecycle-skill on the billing accrual batch — risk critical, full mode, SOX-relevant.`
- `Resume the test lifecycle run at ./.test-lifecycle/run-20260525-143200/.`
- `Use $test-lifecycle-skill in lite mode for this internal admin tool change.`
