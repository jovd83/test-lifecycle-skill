# Phase Map

Authoritative reference for the 13 phases of the lifecycle. Each phase has: ID, name, inputs, outputs, intent (or "inline"), default skill, skip condition, gate after.

## Burst boundaries by mode

The orchestrator runs **autonomous bursts between HITL gates**. A burst is one invocation of the orchestrator that walks as many phases as the mode allows before pausing.

```
lite     : [1, 1b, 2, 3, 4, 5, 6, 7, 8, 9a‖9b, 10, 11, 12]  →  pause @ 13  →  [13]
standard : [1, 1b, 2, 3, 4]  →  gate 4  →  [5, 6, 7, 8]  →  gate 8  →  [9a‖9b, 10, 11, 12]  →  pause @ 13  →  [13]
full     : [1, 1b, 2, 3, 4]  →  gate 4  →  [5, 6, 7, 8]  →  gate 8  →  [9a‖9b (gate 9 per lane on Critical), 10, 11]  →  gate 12  →  [13]
```

## Phase table

| # | Name | Intent | Skill | Skip if | Gate after |
| --- | --- | --- | --- | --- | --- |
| 1 | Intake | inline | — | never | no |
| 1b | HITL Controls Design | `design_hitl_controls` | `eu-ai-act-hitl-oversight-skill` | never | no |
| 2 | AC Normalization | `normalize_acceptance_criteria` | `acceptance-criteria-designer` | AC already clean | no |
| 3 | Test Analysis | `analyze_requirements_for_testability` | `test-analysis-skill` | never | no |
| 4 | Test Strategy | `design_test_strategy` | `test-strategy-skill` | never | **standard, full** |
| 5 | Test Design | `generate_structured_test_cases` | `test-design-orchestrator` | never | no |
| 6 | Case Quality Gate | `review_test_cases` | `test-case-reviewer` | never | inline mini-loop only |
| 7 | Test Data Prep | `generate_synthetic_data` | `lifelike-synthetic-data-generator` | `strategy.json.test_data.synthetic_required == false` | no |
| 8 | Artifact Export | `render_test_artifact` | `test-artifact-export-skill` | never | **standard, full** |
| 9a | Automation Lanes | per-lane intent | per-lane skill | per lane, if no scenarios route to it | **full only, per lane on Critical** |
| 9b | Manual Track | inline | — | `strategy.json.routing.manual` is empty | no |
| 10 | Execution | (inside 9a) | (inside lane skill) | never | no |
| 11 | Functional Review | `review_automation_quality` | `automated-test-reviewer` | never | no |
| 12 | Heal Loop | inline | — | exit criteria met at first pass | **full only, on cap or definition-changing fix** |
| 13 | Final Report | inline | — | never | **all modes** |

## Phase detail

### 1. Intake (inline)

**Inputs:** user prompt, codebase path (optional).
**Outputs:** `phase-01-intake/intake.md`, `state.json` populated with SUT, risk class hint, environments, available inputs, constraints.
**Required intake fields:** `sut.id`, `sut.type`, `risk_class_hint`, `hitl_mode_hint`, `environments[]`.
**Stop and ask** if the change scope is unclear or the SUT can't be classified.

### 1b. HITL Controls Design

**Intent:** `design_hitl_controls`
**Dispatches to:** `eu-ai-act-hitl-oversight-skill`
**Inputs:** intake summary + risk_class.
**Outputs:** `phase-01b-hitl/policy.md` + updated `state.json.mode`.
**Mismatch handling:** if `lite` + `critical`, refuse to auto-proceed; require explicit user override.

### 2. AC Normalization (skip-if AC exist and pass review)

**Intent:** `normalize_acceptance_criteria`
**Dispatches to:** `acceptance-criteria-designer`
**Inputs:** intake.ACs (if present) or intake.story_link.
**Outputs:** `phase-02-ac/ac.md`, `phase-02-ac/ac.json`.
**Skip condition:** intake provided clean ACs with stable IDs.

### 3. Test Analysis

**Intent:** `analyze_requirements_for_testability`
**Dispatches to:** `test-analysis-skill`
**Inputs:** normalized AC + intake.
**Outputs:** `phase-03-analysis/analysis.md`, `phase-03-analysis/risks.json`.

### 4. Test Strategy

**Intent:** `design_test_strategy`
**Dispatches to:** `test-strategy-skill`
**Inputs:** intake + HITL policy + AC + analysis.risks.
**Outputs:** `phase-04-strategy/strategy.md`, `phase-04-strategy/strategy.json`.
**Gate after:** standard + full modes pause for human approval of strategy doc.

### 5. Test Design

**Intent:** `generate_structured_test_cases`
**Dispatches to:** `test-design-orchestrator`
**Inputs:** AC + strategy.scenarios.
**Outputs:** `phase-05-design/cases/<scenario-id>.md` per scenario.

### 6. Case Quality Gate

**Intent:** `review_test_cases`
**Dispatches to:** `test-case-reviewer`
**Inputs:** all designed cases from phase 5.
**Outputs:** `phase-06-quality/review.md`.
**Mini-loop:** if a case fails review, route ONLY that case back to phase 5 (no HITL gate). Max 2 rewrites per case before escalating in the case-quality report.

### 7. Test Data Prep (skip-if not needed)

**Intent:** `generate_synthetic_data`
**Dispatches to:** `lifelike-synthetic-data-generator`
**Inputs:** strategy.test_data.fixture_notes.
**Outputs:** `phase-07-data/` (CSVs, JSONs, etc.).
**Skip condition:** `strategy.json.test_data.synthetic_required == false`.

### 8. Artifact Export

**Intent:** `render_test_artifact`
**Dispatches to:** `test-artifact-export-skill`
**Inputs:** approved cases from phase 6 + target format from intake/strategy.
**Outputs:** `phase-08-export/` (Gherkin / Xray-import / TestRail-import).
**Gate after:** standard + full modes pause for export approval.

### 9a. Automation Lanes (parallel)

**Inputs:** `strategy.json.lanes` where `availability=available` and `routing=automated`.
**For each lane** in the strategy, dispatch the lane's intent. Lanes run in parallel; the orchestrator awaits all and aggregates.

Common lane intents (defined in respective lane skills):

| Lane | Intent | Skill |
| --- | --- | --- |
| Unit / component | `run_stack_aware_unit_tests` | `stack-aware-unit-testing-skill` |
| Java unit | `run_junit5_tests` | `junit5-skill` |
| API system | `run_restassured_tests` | `restassured-skill` |
| Contract drift | `detect_contract_drift` | `api-contract-sentinel` |
| E2E UI (modern) | `run_playwright_e2e` | `playwright-skill` |
| E2E UI (alt) | `run_cypress_e2e` | `cypress-skill` |
| Responsive | `run_responsive_tests` | `responsive-testing` |
| Accessibility | `run_a11y_audit` | `a11y-audit-agent-skill` |
| Performance | `run_perf_tests` | `performance-testing-skill` |
| Security review | `run_appsec_review` | `defensive-appsec-review-skill` |
| Data / batch | `run_data_batch_tests` | `data-batch-testing-skill` (planned) |
| LLM evals | `run_llm_evals` | `llm-eval-skill` (planned) |

**Gate per lane (full only):** if a lane surfaces a Critical-severity finding mid-run, that lane pauses and writes `gates/PAUSED-PHASE-09-lane-<name>-critical.md`. Other lanes continue.

**Outputs:** `phase-10-results/lane-<name>/` per lane.

### 9b. Manual Track (inline, parallel to 9a)

**Inputs:** `strategy.json.routing.manual`.
**Outputs:** `phase-09b-manual/checklist.md` — a human-executable checklist for each manual case (exploratory, UAT, OAT, doc review, usability).
**Note:** the orchestrator does NOT execute manual cases. It writes the checklist and waits for results to be filed into `phase-09b-manual/results.json` (the user or team fills this in).

### 10. Execution

Inside each phase-9a lane. Each lane emits:

- Per-test results (pass/fail/skipped/blocked)
- Per-lane summary stats
- Findings list with severity

Orchestrator aggregates into `phase-10-results/aggregated.json` once all lanes complete.

### 11. Functional Review

**Intent:** `review_automation_quality`
**Dispatches to:** `automated-test-reviewer`
**Inputs:** strategy + aggregated results + manual track results.
**Outputs:** `phase-11-review/review.md` mapping:

- Strategy scenarios → executed scripts → result
- Coverage gaps
- False greens
- Manual-track integration

### 12. Heal Loop (inline)

Algorithm in [heal-loop-control.md](heal-loop-control.md).

**Outputs:** `phase-12-heal/iter-<n>.md` per iteration.
**Gate (full only):** pause on cap reached OR fix requires definition change.

### 13. Final Report (inline)

Generated by `scripts/compile_report.py`.

**Outputs:** `phase-13-report/report.md` + `phase-13-report/report.json`.
**Gate after:** all modes pause for final sign-off.
