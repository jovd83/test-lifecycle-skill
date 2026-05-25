# Parallel 9a + 9b

Phase 9 runs two tracks in parallel: **9a automation lanes** (per-lane skill dispatch) and **9b manual track** (checklist for human execution). Both feed phase 11 (functional review).

## Phase 9a — Automation lanes

### Lane discovery

Read `strategy.json.lanes`. For each entry:

- `availability == "available"` AND `routing == "automated"` → in-scope for 9a
- `availability == "unavailable"` → already handled in phase 4 via documented fallback OR open question
- `routing == "manual"` → goes to 9b

### Lane fan-out

Run lanes in parallel where the underlying skills support it. The orchestrator:

1. Groups scenarios by lane (each scenario in `strategy.json.scenarios` declares its `lane`)
2. Dispatches each lane's intent with the scenario subset as input
3. Each lane writes results to `phase-10-results/lane-<name>/results.json` and a free-form log

Lane parallelism is bounded by:

- Independence of lanes (most lanes are independent; perf is usually serialized to avoid noise)
- Shared environment constraints (don't run perf against the same staging instance that E2E is using)

### Per-lane Critical pause (full mode)

When a lane reports a Critical-severity finding, the lane:

1. Stops further test execution within itself
2. Writes its partial results to `phase-10-results/lane-<name>/`
3. Signals the orchestrator

The orchestrator writes `gates/PAUSED-PHASE-09-lane-<name>-critical.md` and continues other lanes. Once human decides, only that lane resumes (or is marked complete with the finding as a blocker).

In `standard` and `lite` modes, Critical findings are logged but lanes continue; they get surfaced in phase 11 review and may trigger heal-loop work.

### Lane result schema

Each lane's `results.json`:

```json
{
  "lane": "playwright-skill",
  "started_at": "...",
  "ended_at": "...",
  "scenarios_executed": ["S-001", "S-003", "S-005"],
  "stats": {
    "total": 12,
    "passed": 10,
    "failed": 2,
    "skipped": 0,
    "blocked": 0
  },
  "findings": [
    {
      "id": "F-001",
      "severity": "High",
      "scenario": "S-003",
      "summary": "Address validation bypassed via paste",
      "evidence": "lane-playwright/screenshots/S-003.png"
    }
  ],
  "lane_critical_pause": null   // or { "finding_id": "F-XXX", "paused_at": "..." }
}
```

### Aggregation

After all lanes report (or pause), the orchestrator writes `phase-10-results/aggregated.json`:

```json
{
  "lanes": [...per-lane summary...],
  "totals": {"total": N, "passed": N, "failed": N, "skipped": N, "blocked": N},
  "findings_by_severity": {"Critical": 0, "High": 2, "Medium": 5, "Low": 3},
  "per_scenario": [
    {"scenario_id": "S-001", "executed_in": ["lane-unit", "lane-playwright"], "result": "pass"},
    {"scenario_id": "S-003", "executed_in": ["lane-playwright"], "result": "fail", "finding": "F-001"}
  ]
}
```

This is the input to phase 11 (functional review) and phase 12 (heal loop).

## Phase 9b — Manual track

### Checklist generation

For each scenario in `strategy.json.routing.manual` (and any hybrid scenario's manual component):

1. Look up the scenario in `strategy.json.scenarios`
2. Look up the corresponding designed case from `phase-05-design/cases/<scenario-id>.md`
3. Generate a checklist entry with:
   - Scenario ID + name + source (AC/risk driver)
   - Steps (from the designed case)
   - Expected result
   - Result entry slot (pass / fail / blocked + notes)
   - Owner (from manual-type routing — exploratory: QA, UAT: product owner, OAT: ops, doc review: writer)

### Checklist file format

Write `phase-09b-manual/checklist.md`:

```markdown
# Manual Test Checklist — Run <run-id>

## How to use

1. For each item, execute the steps in your environment.
2. Mark the result: ✅ pass | ❌ fail | ⏸ blocked
3. Add notes for failures or anomalies.
4. When all items are done, fill in `phase-09b-manual/results.json` and ping QA lead.

## MAN-001 — Exploratory: edge queries

**Owner:** QA lead
**Source:** strategy.routing.manual (exploratory at risk ≥ medium)

**Steps:**
1. Charter: explore the search redirect feature with typos, long-tail queries, empty input.
2. Time-box: 90 minutes.
3. Document anything that surprises you — both broken and worse-than-expected.

**Expected outcome:** No obviously wrong top results; regressions triaged and accepted before ramp.

**Result:** ___
**Notes:** ___

---

## MAN-002 — UAT: product owner walkthrough

**Owner:** Product owner
...
```

### Results filing

The human/team fills in `phase-09b-manual/results.json`:

```json
[
  {
    "id": "MAN-001",
    "scenario_id": "S-012",
    "result": "pass",
    "executed_by": "qa-lead-name",
    "executed_at": "2026-05-25T16:00:00Z",
    "notes": "Charter session: 3 minor edge cases found, none blocking. Filed as backlog."
  },
  {
    "id": "MAN-002",
    "scenario_id": "AC-7",
    "result": "fail",
    "executed_by": "product-owner-name",
    "executed_at": "2026-05-25T16:30:00Z",
    "notes": "Checkout summary panel does not match approved design for tax-exempt customers."
  }
]
```

When the orchestrator resumes after phase 9 (looking for both 9a completion and 9b results), it picks up the results, integrates them into aggregated.json (treating manual fails as findings), and proceeds to phase 11.

### Manual track is never silent

Even if the strategy has zero manual scenarios:

- Write `phase-09b-manual/checklist.md` with content: "No manual cases routed in this strategy. Phase 9b is intentionally empty."
- Write `phase-09b-manual/results.json` as `[]`
- This guarantees the audit trail records the explicit absence rather than appearing dropped.

## Wait condition for phase 11

Phase 11 (functional review) runs when:

- All non-paused lanes in 9a have completed (or are paused at a per-lane Critical gate)
- `phase-09b-manual/results.json` is filled in (or is `[]` for empty manual tracks)

If the orchestrator hits a re-invocation and 9b results are missing, it should write a gentle "waiting for manual results" message and stop, not proceed with incomplete data.

## Coverage truth in phase 11

The functional review skill's job (phase 11) is to map both tracks back to the strategy's scenarios:

- **Automated-passed:** scenario executed by a lane and passed
- **Manual-passed:** scenario executed manually and passed
- **Automated-failed / Manual-failed:** with the finding
- **Uncovered:** scenario in strategy.routing but no executor reported a result

Uncovered scenarios are a hard signal — either a lane silently dropped them or a manual entry was missed. The review must flag, not silently merge.
