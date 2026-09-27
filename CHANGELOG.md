# Changelog

All notable changes to the `test-lifecycle-skill` repository are documented in this file.

The format follows Keep a Changelog with lightweight `Added`, `Changed`, and `Fixed` sections.

## [1.1.0] - 2026-09-27

### Changed
- `disable-model-invocation: true`: the chain runs as a Claude Code agent (`test-lifecycle`) instead of being picked from its description.
- New "Chain Phases" section, generated from `config/chain_definition.json`: engine phase, skill, gate, and the matching step of this SKILL.md's workflow.
- `config/chain_definition.json` is now committed; the Chain Phases table and the Claude Code agent read it.

## [1.0.0] - 2026-05-25

### Added
- Initial release of `test-lifecycle-skill` — the 13-phase orchestrator for the test lifecycle chain.
- `SKILL.md` with dispatcher metadata, full 13-phase workflow, mode-aware HITL gate boundaries, heal-loop discipline, and final-report contract.
- Reference set:
  - `references/phase-map.md` — all 13 phases with intent/skill/skip/gate mapping
  - `references/workspace-layout.md` — `.test-lifecycle/run-<ts>/` directory structure, state.json format, audit-log conventions
  - `references/hitl-gate-protocol.md` — PAUSED gate file format, approval semantics, audit log requirements
  - `references/heal-loop-control.md` — iteration algorithm, failure classification rubric, cap behavior
  - `references/parallel-9a-9b.md` — automation lane fan-out + manual track checklist generation
  - `references/final-report-template.md` — report Markdown structure + JSON schema
- Assets:
  - `assets/paused-gate-template.md` — template for HITL pause files
  - `assets/state-template.json` — initial `state.json` structure
- Scripts:
  - `scripts/init_run.py` — workspace initialization with phase dirs and audit log bootstrap
  - `scripts/check_exit_criteria.py` — deterministic exit-criteria evaluator with allowed-scale enforcement
  - `scripts/compile_report.py` — assembles `report.md` + `report.json` from run artifacts with posture classification
  - `scripts/validate_chain.py` — consistency + runtime-skill presence validator for `chain.json`
- **`assets/chain.json`** — single machine-readable source of truth for the 13-phase chain: phases, mode bursts, gate map, approver roles per mode, lane-dispatch intents, and references to the strategy skill's lane catalog + exit-criteria scripts. The orchestrator reads chain.json at runtime; prose mirrors it for readability.
- Phase dependency map covering 9 existing phase skills + 2 planned phase-9a lane skills (`data-batch-testing-skill`, `llm-eval-skill`).
