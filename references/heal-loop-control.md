# Heal Loop Control

Phase 12 of the chain. Decides when the chain is done vs needs another iteration vs needs a HITL pause.

## Inputs

- `strategy.json.exit_criteria` — the gates to evaluate
- `phase-10-results/aggregated.json` — current run results
- `phase-11-review/review.md` — functional review findings
- `state.json.heal_iterations` — how many heal cycles have already run

## Algorithm

```
heal_iter = state.heal_iterations + 1
state.heal_iterations = heal_iter

result = check_exit_criteria(strategy.exit_criteria, aggregated.json)

if result.passed:
    state.current_phase = 13
    write phase-12-heal/iter-<N>.md (status: exit-criteria-met)
    proceed to phase 13

elif heal_iter >= strategy.heal_cap:
    write phase-12-heal/iter-<N>.md (status: cap-reached, failures)
    if mode == "full":
        write gates/PAUSED-PHASE-12-heal-decision.md
        pause
    else:
        log and stop; mark run with residual risk; proceed to phase 13 with explicit "stopped at cap" flag

else:
    # iterate: triage failures, fix, re-run affected lanes
    for failure in result.failures:
        classify(failure):
            "real bug"        -> fix code, re-run affected lane
            "flaky test"      -> stabilize test (retries, fixtures), re-run
            "wrong assertion" -> if change requires case definition update (phase-8 artifact):
                                    in full mode: write gates/PAUSED-PHASE-12-definition-change.md, pause
                                    else: log, mark as residual risk, do not auto-modify phase-8 artifact
                                 else: update assertion, re-run
            "env issue"       -> fix env, re-run
    write phase-12-heal/iter-<N>.md (status: iterating, classifications, actions)
    re-run only the affected lanes (back to phase 9a for those lanes -> phase 10 -> phase 11 -> phase 12)
```

## `check_exit_criteria` helper

Implemented in `scripts/check_exit_criteria.py`. Reads exit criteria from strategy and results from aggregated, returns:

```json
{
  "passed": false,
  "summary": "overall_pass_rate 0.93 below threshold 0.95",
  "failures": [
    {"criterion": "overall_pass_rate_min", "actual": 0.93, "expected": 0.95},
    {"criterion": "open_findings.High", "actual": 2, "expected": 0}
  ]
}
```

Usage:

```bash
python scripts/check_exit_criteria.py \
  --strategy phase-04-strategy/strategy.json \
  --results phase-10-results/aggregated.json \
  --json
```

## Failure classification rubric

| Class | Signals | Action |
| --- | --- | --- |
| **Real bug** | Same test fails deterministically across runs; assertion is correct per AC. | Fix code, re-run affected lane. |
| **Flaky test** | Test passes intermittently; failure is timing/environment dependent. | Add retries, fix timing, stabilize fixture. Do NOT delete a "flaky" test that catches real intermittent bugs — investigate first. |
| **Wrong assertion** | The assertion no longer matches intended behavior. AC has changed OR the original assertion was misstated. | If AC changed: pause (definition change). Otherwise update the assertion. |
| **Env issue** | Failure caused by environment misconfiguration (missing creds, network, version skew). | Fix env. Do not loosen test. |

Each iteration log (`phase-12-heal/iter-<N>.md`) must capture, per failure:

- Failure ID and which lane/scenario
- Classification + reasoning
- Action taken
- Result of re-run

## Heal cap by mode (default, from strategy)

| Mode | Default cap | Behavior on cap |
| --- | --- | --- |
| lite | 2 | log, stop, residual risk flagged |
| standard | 4 | log, stop, residual risk flagged |
| full | 6 | **pause at gate 12** for human decision |

## Definition-changing fixes

A fix is "definition-changing" if it would require modifying a stored phase-8 artifact (an exported case in Gherkin / Xray / TestRail / etc.). This invalidates the phase-8 approval.

- **Full mode:** pause at `PAUSED-PHASE-12-definition-change.md`. Human decides:
  - Approve the case change → re-run phase 8 export → re-approve phase 8 gate → resume.
  - Reject → mark the failure as residual risk and continue heal loop with other failures.
- **Standard / lite:** log the fact, mark the failure as residual risk in the final report, do not modify the phase-8 artifact.

## "Done" vs "Stopped at cap"

These are different outcomes and must be distinguished in the final report:

- **Done (exit criteria met):** `phase-12-heal/iter-<N>.md` status = `exit-criteria-met`. Final report shows green posture.
- **Stopped at cap:** `phase-12-heal/iter-<N>.md` status = `cap-reached`. Final report shows residual risk explicitly with a section listing each unmet criterion.

Do not collapse "stopped at cap" into "done with caveats". The audit trail must preserve the distinction.

## Anti-patterns

- **Bulk-rerunning everything** — re-run only the affected lane(s). Re-running the full chain wastes hours and dilutes signal.
- **Reclassifying failures to fit time pressure** — the rubric is rigid for a reason. A "real bug" doesn't become a "flaky test" because the deadline is tomorrow.
- **Silent test deletion** — never delete a test labeled "flaky" without classifying why. Flaky tests sometimes catch real intermittent issues.
- **Bumping the cap without HITL** — the heal cap comes from the phase-4-approved strategy. Changing it requires re-approval of phase 4 (or the phase-12 gate decision in full mode).
- **Marking residual risk and shipping** — that's a legitimate outcome, but the final report must call it out explicitly. Do not bury it.
