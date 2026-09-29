# Fameweb --- Technical Architecture

## Stack

-   Backend: Flask + Python
-   Database: SQLite initially, PostgreSQL-ready
-   ORM/migrations: SQLAlchemy + Alembic
-   Frontend: existing vanilla JS + Tailwind
-   AI: Gemini API
-   Existing pandas/openpyxl functionality can be retained where useful

## Major Components

### Authentication

`auth.py` - Signup - Login - Logout - Session middleware -
Verification/reset flows where enabled

### LinkedIn Profile Intake

`profile_intake.py` - Parse uploaded LinkedIn PDF/data export - Parse
pasted profile information - Structure profile data with Gemini - Save
to `users_linkedin_details`

### LinkedIn OIDC

`oidc_linkedin.py` - Initiate LinkedIn OIDC - Handle callback - Maintain
connection status - Store only required encrypted auth data if
applicable

### Company Analysis

Reuse and modify existing `analyzer.py`. - Website extraction - Public
web enrichment where permitted - SSRF-safe URL fetching - Gemini
structuring - Respect user-edited fields

### Profile Optimization

Reuse and modify `profile_optimizer.py`. Input: - Stored LinkedIn
profile - Stored ICP Output: - Optimization suggestions

### Research

`research_service.py` - Global DB lookup - Deterministic filtering -
Rule-based scoring - Gemini only where ambiguity requires it -
Deduplication - User/global separation

### Job Worker

`jobs/worker.py` - Research jobs - Atomic claiming - Heartbeats -
Progress updates - Retry/stop logic

### Outreach

`outreach_service.py` - Thread creation - Connection/message
generation - Conversation state - Follow-up scheduling

`OutreachExecutor` - `ManualExecutor` for V1 - Future executors can
implement the same interface

### Scheduler

`scheduler.py` - Find due follow-up tasks - Surface tasks to the user -
V1 must not automatically perform LinkedIn actions

### Security

`crypto.py` - Encryption/decryption for applicable tokens

`url_guard.py` - SSRF protection for company website requests

## Existing Code Reuse

-   `analyzer.py` → company analysis
-   `profile_optimizer.py` → optimization
-   `gtm_engine.py` → research/qualification orchestration after
    removing legacy LinkedIn discovery
-   Existing Tailwind/JS → UI
-   pandas/openpyxl → imports/exports

## Legacy LinkedIn Automation

Existing Playwright/Voyager/session code is frozen behind:
`LINKEDIN_AUTOMATION_ENABLED=false`

It must not be extended or migrated into the new multi-user
architecture.
