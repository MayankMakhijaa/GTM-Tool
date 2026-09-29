# Fameweb --- Implementation Plan

## Phase 0 --- Audit & Backup

-   Audit the existing Flask application and modules.
-   Back up the current database and code.
-   Add `LINKEDIN_AUTOMATION_ENABLED=false`.
-   Freeze legacy LinkedIn Playwright/session functionality.
-   Do not port legacy LinkedIn cookies/session data into the new
    architecture.

## Phase 1 --- Database & Data Access

-   Introduce SQLAlchemy models.
-   Introduce Alembic migrations.
-   Define the approved 8-table schema.
-   Add required foreign keys, unique constraints, CHECK constraints and
    JSON validation for SQLite.
-   Perform a migration dry run.
-   Keep old tables until migration verification is complete.
-   Introduce repositories/data-access layer.

## Phase 2 --- Authentication

-   Signup with name, email, phone and password.
-   Validate business-email requirement according to product rules.
-   Hash passwords with Argon2id.
-   Login with email or phone.
-   Secure Flask server session.
-   CSRF protection.
-   Rate limiting.
-   Email verification/password reset if enabled in the current product
    scope.

## Phase 3 --- Onboarding

Order: 1. LinkedIn connection/profile intake 2. Company website analysis
3. Company review/edit 4. ICP input 5. ICP summary 6. Optional profile
optimization 7. Complete onboarding

Onboarding must be resumable using `onboarding_step`.

## Phase 4 --- Profile Optimization

-   Reuse the existing optimization logic where practical.
-   Generate suggestions from stored LinkedIn profile + ICP.
-   Store suggestions against the user's LinkedIn details.
-   Do not require LinkedIn browser automation.

## Phase 5 --- Dashboard

-   Preserve useful existing dashboard components.
-   Add GTM Research entry point.
-   Add leads/research status.
-   Add outreach/today queue.
-   Keep navigation consistent.

## Phase 6 --- Global Profile Intelligence

-   Import/upsert global profiles.
-   Normalize LinkedIn identifiers.
-   Apply `do_not_contact`.
-   Store only global/shared facts.
-   Keep user-specific score/reason/status in `users_profiles`.
-   Increment `recommended_no_of_times` atomically when a profile is
    newly recommended to a user.

## Phase 7 --- Research Jobs

-   Create persistent `research_jobs`.
-   Add queue/running/paused/completed/failed/cancelled states.
-   Add progress and budget JSON.
-   Add heartbeat and retry handling.
-   Enforce one active research job per user.
-   Add cancel/pause/resume.
-   Stop on target reached, budget exhausted, no more candidates,
    cancellation or error.

## Phase 8 --- Connect & Message

-   Create/get one thread per user + global profile.
-   Generate connection draft.
-   User copies/executes the action.
-   User marks it sent.
-   User marks connection accepted.
-   Generate contextual messages.
-   Store replies.
-   Generate follow-ups using conversation history.
-   Schedule/pause/resume/stop follow-up sequence.
-   Use optimistic locking through `version`.

## Phase 9 --- UX

-   Research progress UI.
-   Lead list and qualification details.
-   Outreach thread view.
-   Today's outreach tasks.
-   Clear status transitions.
-   Error/retry states.

## Phase 10 --- Hardening

-   Authorization/IDOR tests.
-   Input validation.
-   SSRF protection for website fetching.
-   Secret/token encryption where applicable.
-   Backups.
-   Migration verification.
-   Performance checks.
-   Final decision on PostgreSQL migration.
-   Remove frozen legacy LinkedIn automation before multi-user
    production.
