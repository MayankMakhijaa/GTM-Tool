# Fameweb --- Parallel Development / Work Split

## Rule

Before changing a shared module, check the current implementation status
and update `CHANGELOG.md` / `IMPLEMENTATION_STATUS.md`.

## Track A --- Foundation + Backend

Responsible for: - SQLAlchemy models - Alembic migrations -
Repositories - Authentication - Security helpers - Shared API utilities

Primary files: - `models/` - `repositories/` - `auth.py` - `crypto.py` -
`url_guard.py` - migrations

## Track B --- Onboarding + Profile

Responsible for: - Onboarding state - Company analysis/review - ICP -
LinkedIn OIDC - Profile upload/paste intake - Profile optimization

Primary files: - `profile_intake.py` - `oidc_linkedin.py` - onboarding
routes/services - optimization routes/services - related frontend views

## Track C --- GTM Research + Leads

Responsible for: - Global profile import/upsert - Qualification -
Research jobs - Progress/budget/cancel/pause/resume - Lead UI

Primary files: - `research_service.py` - `jobs/worker.py` - research
routes - lead routes - related frontend views

## Track D --- Outreach

Responsible for: - `connect_and_message` - OutreachExecutor -
ManualExecutor - Gemini message generation - Reply capture - Follow-up
scheduler - Today's task queue

Primary files: - `outreach_service.py` - `scheduler.py` - outreach
routes - outreach frontend views

## Integration Rules

-   Do not independently change database schema without updating
    `03_DATABASE_SCHEMA.md`.
-   Do not add endpoints without updating `04_API_SPEC.md`.
-   Do not change an architecture decision silently.
-   Keep commits small and focused.
-   Rebase/merge frequently before touching shared files.
-   Run tests after each phase.
-   If a requirement conflicts with the PRD, stop and resolve the
    conflict before implementation.

## Suggested Order

Foundation → Auth → Onboarding → Profile → Research → Outreach →
Integration → Hardening.
