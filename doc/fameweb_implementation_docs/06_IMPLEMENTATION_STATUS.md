# Fameweb --- Implementation Status

This file is the shared progress board for the team.

## Phase 0 --- Audit & Backup

-   [ ] Existing project audit
-   [ ] Database backup
-   [ ] Legacy LinkedIn automation feature flag
-   [ ] Freeze legacy LinkedIn session code

## Phase 1 --- Database

-   [ ] SQLAlchemy setup
-   [ ] Alembic setup
-   [ ] 8-table schema
-   [ ] Constraints/indexes
-   [ ] Migration dry run
-   [ ] Migration verification

## Phase 2 --- Authentication

-   [ ] Signup
-   [ ] Login
-   [ ] Logout
-   [ ] Session middleware
-   [ ] Password hashing
-   [ ] CSRF
-   [ ] Rate limiting
-   [ ] Verification/reset

## Phase 3 --- Onboarding

-   [ ] LinkedIn OIDC
-   [ ] Profile upload
-   [ ] Profile paste
-   [ ] Company analysis
-   [ ] Company review
-   [ ] ICP
-   [ ] ICP summary
-   [ ] Resumable onboarding

## Phase 4 --- Optimization

-   [ ] Generate suggestions
-   [ ] Save suggestions
-   [ ] Optimization UI

## Phase 5 --- Dashboard

-   [ ] Dashboard shell
-   [ ] Research entry
-   [ ] Lead status
-   [ ] Outreach/today queue

## Phase 6 --- Global Profiles

-   [ ] Import
-   [ ] Upsert/dedupe
-   [ ] Qualification
-   [ ] Atomic recommendation count

## Phase 7 --- Research Jobs

-   [ ] Worker
-   [ ] Job state
-   [ ] Progress
-   [ ] Budgets
-   [ ] Pause/resume/cancel
-   [ ] Retry/reaper

## Phase 8 --- Outreach

-   [ ] Thread creation
-   [ ] Connection draft
-   [ ] Manual send confirmation
-   [ ] Accepted state
-   [ ] Message generation
-   [ ] Reply capture
-   [ ] Follow-up generation
-   [ ] Scheduling
-   [ ] Pause/resume/stop

## Phase 9 --- Integration

-   [ ] Full onboarding → dashboard flow
-   [ ] Research → leads
-   [ ] Leads → outreach
-   [ ] Outreach → today queue

## Phase 10 --- Hardening

-   [ ] IDOR/authorization tests
-   [ ] Input validation
-   [ ] SSRF tests
-   [ ] Backup/restore
-   [ ] Performance review
-   [ ] PostgreSQL migration decision
-   [ ] Remove legacy LinkedIn automation
