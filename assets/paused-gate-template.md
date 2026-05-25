---
status: paused
phase: __PHASE__
phase_name: __PHASE_NAME__
mode: __MODE__
risk_class: __RISK_CLASS__
approver_role: __APPROVER_ROLE__
approved:                       # ← human fills in: true | false
approver:                       # ← human fills in
approved_at:                    # ← human fills in: ISO-8601
notes:                          # ← optional rejection reason or qualifying notes
---

# Phase __PHASE__ — __PHASE_NAME__

## What you're approving

__WHAT_BEING_APPROVED__

## Artifacts to review

__ARTIFACT_LIST__

## Key decisions / findings at this gate

__KEY_DECISIONS__

## Open Questions

__OPEN_QUESTIONS__

## How to approve

**Quick:** rename this file to `RESOLVED-PHASE-__PHASE__-__SHORT_REASON__.md`.

**With notes:** edit the frontmatter above (`approved: true`, fill in approver fields, add notes).

**To reject:** set `approved: false` with a reason in `notes`, OR rename to `REJECTED-PHASE-__PHASE__-__SHORT_REASON__.md`.

## What happens next

__NEXT_STEPS_ON_APPROVAL__

__NEXT_STEPS_ON_REJECTION__
