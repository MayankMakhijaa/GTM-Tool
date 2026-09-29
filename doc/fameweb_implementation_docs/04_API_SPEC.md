# Fameweb --- API Contract

## Authentication

-   POST `/api/auth/signup`
-   POST `/api/auth/login`
-   POST `/api/auth/logout`
-   GET `/api/auth/me`
-   POST `/api/auth/verify-email`
-   POST `/api/auth/request-reset`
-   POST `/api/auth/reset`

## Onboarding

-   GET `/api/onboarding/state`
-   POST `/api/onboarding/company/analyze`
-   GET `/api/onboarding/company`
-   PUT `/api/onboarding/company`
-   PUT `/api/onboarding/icp`
-   POST `/api/onboarding/icp/summary`
-   POST `/api/onboarding/complete`

## LinkedIn

-   GET `/api/linkedin/connect`
-   GET `/api/linkedin/callback`
-   GET `/api/linkedin/status`
-   POST `/api/linkedin/disconnect`
-   POST `/api/linkedin/profile/upload`
-   POST `/api/linkedin/profile/paste`
-   GET `/api/linkedin/profile`

## Optimization

-   POST `/api/optimization/generate`
-   GET `/api/optimization`
-   POST `/api/optimization/skip`

## Research

-   POST `/api/research/jobs`
-   GET `/api/research/jobs`
-   GET `/api/research/jobs/<id>`
-   POST `/api/research/jobs/<id>/cancel`
-   POST `/api/research/jobs/<id>/pause`
-   POST `/api/research/jobs/<id>/resume`
-   POST `/api/research/import`

## Leads

-   GET `/api/leads`
-   GET `/api/leads/<users_profile_id>`
-   PATCH `/api/leads/<id>`
-   POST `/api/leads/requalify`
-   POST `/api/leads/<id>/opt-out`

## Outreach

-   POST `/api/outreach/threads`
-   GET `/api/outreach/threads`
-   GET `/api/outreach/threads/<id>`
-   POST `/api/outreach/threads/<id>/connection/generate`
-   POST `/api/outreach/threads/<id>/connection/mark-sent`
-   POST `/api/outreach/threads/<id>/accepted`
-   POST `/api/outreach/threads/<id>/messages/generate`
-   PATCH `/api/outreach/threads/<id>/messages/<msg_id>`
-   POST `/api/outreach/threads/<id>/messages/<msg_id>/mark-sent`
-   POST `/api/outreach/threads/<id>/replies`
-   POST `/api/outreach/threads/<id>/pause`
-   POST `/api/outreach/threads/<id>/resume`
-   POST `/api/outreach/threads/<id>/stop`
-   GET `/api/outreach/today`

## Settings

-   GET/PUT `/api/settings/profile`
-   GET/PUT `/api/settings/icp`
-   GET/PUT `/api/settings/company`
-   POST `/api/settings/export`
-   DELETE `/api/settings/account`

## Contract Rules

-   All user-owned resources must enforce authorization.
-   Thread mutations use optimistic locking through `version`.
-   A stale version returns HTTP 409 and the client refetches.
-   Message updates target message ID, never array index.
