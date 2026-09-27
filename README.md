# Test Lifecycle Skill

[![Validate Skill](https://github.com/jovd83/test-lifecycle-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/jovd83/test-lifecycle-skill/actions/workflows/validate.yml)
[![version](https://img.shields.io/badge/version-1.0.0-blue)](CHANGELOG.md)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-0a7ea4)](SKILL.md)
[![status](https://img.shields.io/badge/status-active-2ea44f)](SKILL.md)
[![category](https://img.shields.io/badge/category-testing-0a7ea4)](SKILL.md)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/jovd83)

`test-lifecycle-skill` is an Agent Skill that orchestrates a software change through **13 phases of disciplined testing** — from intake to a signed-off final report — by dispatching to phase-specific skills and pausing at HITL (human-in-the-loop) gates for explicit approval.

## What This Skill Does

The skill walks a change through the full 13-phase test lifecycle and produces:

- An auditable per-run workspace (`<codebase>/.test-lifecycle/run-<ts>/`) with one subdirectory per phase, a `state.json`, and an append-only `audit-log.jsonl`.
- A normalized acceptance-criteria list, a testability analysis, and a load-bearing `strategy.json` that drives every later phase.
- Designed test cases, a quality-gate review, generated synthetic data (when needed), and target-format exports (Gherkin, Xray, TestRail, etc.).
- Parallel execution of automated lanes (9a) and a manual track checklist (9b), aggregated into a single results bundle.
- A functional automation review that maps strategy scenarios → executed scripts → results, flagging coverage gaps and false greens.
- A disciplined heal loop that root-causes failures, re-runs only the affected lane, and respects an iteration cap.
- A final report (`report.md` + `report.json`) with a traceability matrix (requirement → AC → scenario → script → result) and the full HITL audit trail.

The orchestrator runs in **autonomous bursts between HITL gates** — it walks as many phases as the chosen mode allows, then writes a `PAUSED-PHASE-N.md` gate file and returns control to the user.

```
lite     : [1 → 12 autonomous]            → pause @ 13  → [13]
standard : [1 → 4]  → gate 4  → [5 → 8]  → gate 8  → [9a‖9b → 12]  → gate 13  → [13]
full     : [1 → 4]  → gate 4  → [5 → 8]  → gate 8  → [9a‖9b (gate 9 per lane) → 11]  → gate 12  → [13]
```

## What This Skill Does Not Do

- Design strategy docs (that's `test-strategy-skill`, phase 4).
- Author test cases (that's `test-design-orchestrator`, phase 5).
- Run individual tests (the lane skills in phase 9a).
- Define HITL controls themselves (that's `eu-ai-act-hitl-oversight-skill`, phase 1b).
- Persist shared-memory or cross-project policy.

## When To Use It

Use this skill when you need a complete, traceable, gate-controlled test pass for a change — not a one-off plan or a single test case. Good triggers:

- "Test this new checkout flow end-to-end."
- "Plan and execute testing for the billing accrual batch."
- "Run the full test chain on this release."
- "Deliver a verified, documented test pass for SOX-relevant work."
- "Resume the test lifecycle run at `<workspace>`."

Do **not** use it for:

- One-off strategy planning → use `test-strategy-skill`.
- One-off case design → use `test-design-orchestrator`.
- A single bug-fix loop → use `bug-fix-lifecycle`.
- A new-feature implementation chain → use `new-feature-sdlc-skill`.

## Install

Install from GitHub with `npx skills`:

```bash
npx skills install jovd83/test-lifecycle-skill
```

For older Skills CLI versions that use `add`:

```bash
npx skills add https://github.com/jovd83/test-lifecycle-skill --skill test-lifecycle-skill
```

You can also copy this folder into any Agent Skills-compatible skills directory:

```text
~/.codex/skills/test-lifecycle-skill
~/.agents/skills/test-lifecycle-skill
<project>/.agents/skills/test-lifecycle-skill
```

The skill name is `test-lifecycle-skill`, so explicit invocations use `$test-lifecycle-skill`.

## Usage

Example prompts:

- `Use $test-lifecycle-skill to test the new checkout flow end-to-end; standard mode, repo at ./apps/storefront.`
- `Use $test-lifecycle-skill on the billing accrual batch — risk critical, full mode, SOX-relevant.`
- `Resume the test lifecycle run at ./.test-lifecycle/run-20260525-143200/.`
- `Use $test-lifecycle-skill in lite mode for this internal admin tool change.`

## Per-Run Workspace

Every run gets a fresh workspace under the target codebase:

```
<codebase>/.test-lifecycle/run-YYYYMMDD-HHMMSS/
├── state.json           # current phase, mode, exit criteria, gate status
├── audit-log.jsonl      # append-only: phase transitions + gate decisions
├── gates/               # PAUSED / RESOLVED / REJECTED gate files
├── phase-01-intake/
├── phase-01b-hitl/
├── phase-02-ac/
├── phase-03-analysis/
├── phase-04-strategy/   # ← strategy.json is load-bearing for later phases
├── phase-05-design/
├── phase-06-quality/
├── phase-07-data/
├── phase-08-export/
├── phase-09b-manual/
├── phase-10-results/    # aggregated.json + lane-<name>/ per lane
├── phase-11-review/
├── phase-12-heal/       # iter-1.md, iter-2.md, ...
└── phase-13-report/     # report.md + report.json
```

See [references/workspace-layout.md](references/workspace-layout.md).

## Repository Layout

```text
test-lifecycle-skill/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── .github/
│   └── workflows/
│       └── validate.yml
├── references/
│   ├── phase-map.md
│   ├── workspace-layout.md
│   ├── hitl-gate-protocol.md
│   ├── heal-loop-control.md
│   ├── parallel-9a-9b.md
│   └── final-report-template.md
├── assets/
│   ├── chain.json                # ← single source of truth: phases, modes, gates, intents
│   ├── paused-gate-template.md
│   └── state-template.json
└── scripts/
    ├── init_run.py
    ├── check_exit_criteria.py
    ├── compile_report.py
    └── validate_chain.py         # consistency + runtime-skill presence checker
```

## Chain Source of Truth

The 13-phase chain (phases, mode bursts, gate map, lane-dispatch intents) is defined in **[assets/chain.json](assets/chain.json)**. The orchestrator reads chain.json at runtime; prose in `SKILL.md` and `references/*.md` mirrors it for human readability.

Validate the chain definition (catches drift, missing skills, undefined gates):

```bash
python scripts/validate_chain.py
python scripts/validate_chain.py --json
```

## Scripts

All scripts support `--json` for machine-readable output where applicable.

### `init_run.py`
Initialize a new run workspace under `<codebase>/.test-lifecycle/run-<ts>/`.

```bash
python scripts/init_run.py --codebase ./apps/storefront --change-id WEB-CHECKOUT-2026
```

### `check_exit_criteria.py`
Evaluate phase-4 exit criteria against phase-10 aggregated results. Used by phase 12 (heal loop). Returns pass/fail + per-criterion details.

```bash
python scripts/check_exit_criteria.py \
  --strategy phase-04-strategy/strategy.json \
  --results phase-10-results/aggregated.json --json
```

### `validate_chain.py`
Validate `assets/chain.json` for internal consistency and runtime-skill presence. Catches phases referenced in mode bursts that don't exist, undefined gate references, and missing skills on the runtime tree.

```bash
python scripts/validate_chain.py
python scripts/validate_chain.py --runtime-root /custom/path --json
```

### `compile_report.py`
Assemble the phase-13 final report (`report.md` + `report.json`) from artifacts in the run workspace.

```bash
python scripts/compile_report.py --workspace .test-lifecycle/run-20260525-143200
```

## Chain Dependencies

This skill dispatches to (and therefore depends on) these phase skills:

| Phase | Skill | Status |
| --- | --- | --- |
| 1b | `eu-ai-act-hitl-oversight-skill` | available |
| 2 | `acceptance-criteria-designer` | available |
| 3 | `test-analysis-skill` | available |
| 4 | `test-strategy-skill` | available |
| 5 | `test-design-orchestrator` | available |
| 6 | `test-case-reviewer` | available |
| 7 | `lifelike-synthetic-data-generator` | available |
| 8 | `test-artifact-export-skill` | available |
| 9a | per-lane skills | mostly available |
| 11 | `automated-test-reviewer` | available |

Two phase-9a lane skills are planned but not yet built:
- `data-batch-testing-skill` — covers data/ETL/batch lane
- `llm-eval-skill` — covers AI/ML eval lane (conditional, only for SUTs with a model)

When a phase 9a lane is unavailable, the strategy (phase 4) is expected to route to a documented fallback OR surface an Open Question that blocks the phase-4 gate.

## Memory Model

- **Runtime memory**: phase outputs, scratch notes, in-progress lane results. Lives in the run workspace; not promoted.
- **Project-local memory**: the per-run workspace itself (`<project>/.test-lifecycle/run-<ts>/`). Version-controllable if the team wants.
- **Shared memory**: out of scope. Cross-project policy belongs behind an external shared-memory skill.

## Gitignore Policy

`.test-lifecycle/` is intentionally NOT gitignored by default. Teams can adapt per mode:

- **Full mode** — commit completed runs (audit-trail value for regulated work)
- **Standard mode** — gitignore in-progress runs but commit final reports
- **Lite mode** — gitignore the whole directory

## Standards Alignment

- Agent Skills progressive-disclosure model and SKILL.md frontmatter conventions
- Risk-based testing model from `test-strategy-skill`
- EU AI Act HITL oversight patterns from `eu-ai-act-hitl-oversight-skill`
- IEEE 829 / ISO 29119 test plan structure (selectively borrowed by phase 4 + phase 13)

## License

MIT. See [LICENSE](LICENSE).
