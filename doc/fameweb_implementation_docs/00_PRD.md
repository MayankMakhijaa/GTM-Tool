# Fameweb — Product Requirements Document

**Project:** Fameweb AI GTM / Outbound Platform
**Current Development Cycle:** Cycle 1 — LinkedIn / Voyager HTTP Outreach
**Next Development Cycle:** Cycle 2 — Email Outreach
**Status:** Development / Implementation
**Primary Reference:** This document + supporting architecture/database/API documents

---

# 1. Product Vision

Fameweb is being developed as an **AI-powered GTM and outbound platform**.

The product is inspired by the overall workflow of modern AI GTM platforms such as Gojiberry:

```text
Company
   ↓
ICP Understanding
   ↓
AI GTM Research
   ↓
Relevant Prospects
   ↓
Lead Qualification
   ↓
Intent / Buying Signals
   ↓
Personalized Outreach
   ↓
Conversation
   ↓
AI Follow-ups
   ↓
Qualified Opportunity
```

Fameweb should not be treated as only a LinkedIn scraper or lead generator.

The long-term product is a **GTM intelligence + outreach platform** where the same lead, company, ICP and conversation context can be reused across multiple outreach channels.

The first implementation cycle focuses on **LinkedIn outreach through the Voyager HTTP/API integration layer**.

Email will be introduced as the next outreach channel.

---

# 2. Product Development Strategy

Fameweb will be developed incrementally.

## Cycle 1 — LinkedIn / Voyager HTTP Outreach

Cycle 1 establishes the complete GTM foundation:

```text
Authentication
      ↓
Onboarding
      ↓
Company Understanding
      ↓
ICP Understanding
      ↓
LinkedIn Profile
      ↓
GTM Research
      ↓
Lead Qualification
      ↓
Prospect
      ↓
Connection
      ↓
Message
      ↓
Conversation
      ↓
AI Follow-up
```

The LinkedIn channel will use the **Voyager HTTP/API layer** for LinkedIn interaction.

Cycle 1 must therefore establish a clean integration boundary around Voyager.

---

## Cycle 2 — Email Outreach

Once Cycle 1 is stable, Email Outreach will be added.

Email should reuse the existing:

* users
* companies
* ICP
* global profiles
* qualified leads
* AI personalization
* conversation context
* outreach threads
* follow-up concepts

The product should not require a separate GTM system for Email.

Long term:

```text
                         ┌── LinkedIn / Voyager
                         │
GTM Intelligence ────────┼── Email
                         │
                         └── Future Channels
```

---

# 3. Core Product Principles

The implementation must follow these principles.

## 3.1 Build the product, not a demo

The architecture must support the eventual multi-user SaaS product.

However, do not overengineer the first version.

Avoid introducing:

* microservices
* unnecessary queues
* Redis
* Celery
* Kubernetes
* complex event systems
* unnecessary database normalization
* unnecessary tables

unless a concrete requirement appears.

---

## 3.2 Keep business logic separate from integrations

The core Fameweb application must not depend directly on Voyager implementation details.

Use:

```text
Routes
   ↓
Services
   ↓
Repositories
   ↓
Models
```

External systems are accessed through:

```text
Services
   ↓
Integrations
```

---

## 3.3 Preserve clear boundaries

The following must remain separate:

```text
Fameweb Authentication
LinkedIn Authentication / Session
Voyager Integration
GTM Research
Lead Qualification
AI Generation
Outreach
Scheduling
Frontend
```

---

## 3.4 Never make destructive architectural assumptions

Before implementing a major external integration:

1. Inspect the existing implementation.
2. Understand how it works.
3. Validate the assumptions.
4. Then extract/reuse the useful logic.

Do not blindly rewrite working LinkedIn/Voyager functionality.

---

# 4. Existing Repository Audit — Mandatory First Step

The existing GitHub implementation is an important reference for Cycle 1.

Before implementing the new LinkedIn integration, inspect the existing codebase and identify the existing LinkedIn interaction flow.

Specifically identify:

### Authentication/session

* How LinkedIn authentication is currently performed
* How the LinkedIn account/session is identified
* Whether authentication depends on browser state
* What cookies/tokens/headers are used
* How session validity is detected

### Profile identification

* How LinkedIn profile URLs are resolved
* How LinkedIn public identifiers are obtained
* What identifiers are required by Voyager requests

### Connection functionality

Identify the exact existing implementation for:

* connection request creation
* connection request payload
* required identifiers
* request headers
* response handling
* success/failure detection

### Messaging functionality

Identify:

* message creation
* conversation/thread identification
* message payload
* required identifiers
* response handling
* error handling

### Existing HTTP/Voyager logic

Determine:

* which requests are actually being made
* which endpoints are being used
* which headers are required
* which request bodies are required
* which response fields are important
* how the existing implementation determines success/failure

**Do not invent endpoint names or payloads.**

The existing repository must be inspected before the new integration contract is finalized.

---

# 5. Voyager HTTP Integration

## 5.1 Role of Voyager

**Voyager is the intended LinkedIn HTTP/API integration mechanism for Cycle 1.**

Voyager-specific communication must be isolated from the rest of Fameweb.

The application should not directly call Voyager from random routes or frontend code.

---

## 5.2 Integration architecture

The intended architecture is:

```text
Frontend
    ↓
Fameweb API
    ↓
Outreach Service
    ↓
OutreachExecutor
    ↓
Voyager LinkedIn Adapter
    ↓
Voyager HTTP/API
    ↓
LinkedIn
```

The exact names can change slightly during implementation, but the separation must remain.

---

# 6. OutreachExecutor Abstraction

All LinkedIn outreach actions must go through an executor abstraction.

Conceptually:

```python
class OutreachExecutor:

    def send_connection(...):
        ...

    def send_message(...):
        ...

    def fetch_replies(...):
        ...
```

The application-level outreach service should depend on this abstraction rather than directly depending on Voyager.

Example:

```text
Outreach Service
      ↓
OutreachExecutor
      ↓
VoyagerAdapter
```

This ensures that the product architecture does not have to change if the underlying LinkedIn execution mechanism changes later.

---

# 7. Voyager Adapter

The Voyager adapter is responsible for LinkedIn-specific HTTP communication.

Conceptually:

```text
app/
└── integrations/
    └── linkedin/
        ├── voyager_client.py
        ├── voyager_auth.py
        ├── profile.py
        └── requests.py
```

The exact structure may be adjusted after auditing the existing code.

The adapter should contain:

* HTTP request construction
* Voyager-specific headers
* Voyager-specific identifiers
* Voyager request payloads
* response parsing
* LinkedIn-specific error handling
* authentication/session handling required by the validated Voyager implementation

The rest of Fameweb must not need to know these implementation details.

---

# 8. Voyager Authentication / Session Rule

The existing prototype may contain browser-based LinkedIn session logic.

This must **not automatically become the architecture of the new SaaS system**.

Before implementation, determine exactly how the existing Voyager requests authenticate.

The implementation team must explicitly document:

```text
What authenticates the Voyager request?
How is the session obtained?
Where is it stored?
How is it refreshed?
How is it invalidated?
What happens when it expires?
```

Do not store LinkedIn passwords.

Do not blindly copy the existing Chromium profile into the new architecture.

If the existing implementation requires browser cookies/session state, this must be explicitly validated as a Cycle 1 technical dependency before building the rest of the system around it.

The integration must be isolated so that the rest of Fameweb does not depend on browser automation.

---

# 9. Existing Playwright / Chromium Code

The existing Playwright/Chromium LinkedIn automation is legacy/prototype functionality.

It must be:

```text
Audited
   ↓
Documented
   ↓
Frozen / isolated
```

It must not be expanded throughout the new application.

Use:

```text
LINKEDIN_AUTOMATION_ENABLED=false
```

or an equivalent feature flag where appropriate.

The legacy implementation may remain temporarily inside:

```text
legacy/
```

for reference and rollback.

It should not become a dependency of:

* GTM Research
* Lead Qualification
* Outreach Service
* Dashboard
* Authentication
* Database repositories

---

# 10. User Account Creation

The Fameweb account is separate from LinkedIn authentication.

Signup collects:

* Name
* Business email
* Phone number
* Password

Authentication should use:

* secure password hashing
* Argon2id
* server-side session
* secure cookies
* CSRF protection
* rate limiting

Users can log in using:

```text
Email
OR
Phone
```

Do not use LinkedIn credentials as Fameweb login credentials.

---

# 11. Business Email

Signup should prefer a business email.

The system may block common public/free email domains according to the product's configured policy.

This is a product qualification mechanism, not proof of company ownership.

Company identity must be established separately through company information and website onboarding.

---

# 12. Onboarding

New users should go through a resumable onboarding flow.

```text
Signup
   ↓
LinkedIn Connection / Profile
   ↓
Company
   ↓
ICP
   ↓
ICP Summary
   ↓
Optional Profile Optimization
   ↓
Dashboard
```

The user should be able to resume onboarding if they leave midway.

Store onboarding progress in:

```text
user_table.onboarding_step
```

---

# 13. LinkedIn Profile

Fameweb needs the user's LinkedIn profile as context for:

* profile optimization
* outreach personalization
* sender identity
* GTM context

The system should store structured profile information.

The supported profile intake approach must be determined according to the validated LinkedIn integration and product flow.

Potential sources include:

* supported LinkedIn authentication/profile data
* uploaded LinkedIn PDF/data export
* pasted profile information

The exact source must be stored using:

```text
profile_source
```

Possible values:

```text
OIDC
UPLOAD
PASTE
```

---

# 14. Company Understanding

During onboarding the user provides their company website.

Fameweb should extract useful company information such as:

* company name
* description
* what the company sells
* products/services
* industry
* company size
* revenue
* location
* rating
* other relevant details

The extracted information must be presented to the user for review/editing.

The system must respect user-edited fields.

Company extraction should not silently overwrite user corrections.

---

# 15. ICP Understanding

The user defines their Ideal Customer Profile.

The ICP should support:

* target customer
* company size
* revenue range
* target roles
* industry
* location
* keywords
* exclusions
* signals
* tone

The ICP should have a version number.

Whenever qualification-relevant ICP information changes:

```text
ICP version++
```

This allows historical lead qualification to remain understandable.

Tone-only changes do not need to invalidate qualification.

---

# 16. ICP Summary

After ICP configuration, Fameweb should generate an understandable summary/report.

Example:

```text
Target:
B2B SaaS companies

Company Size:
50–500 employees

Target Roles:
Founder
CEO
Head of Sales
VP Sales

Industries:
SaaS
AI
Technology

Signals:
Recently hiring
Growing sales team
Using outbound sales
```

The user should be able to review and edit the underlying ICP.

---

# 17. Profile Optimization

Profile Optimization is an optional onboarding step.

It uses:

```text
Saved LinkedIn Profile
+
Company Context
+
ICP
```

to generate optimization suggestions.

The user should be able to:

* accept
* reject
* edit
* skip

the optimization.

Profile Optimization must not be required for GTM Research or Outreach.

---

# 18. GTM Research

GTM Research is the core lead discovery system.

The research flow should be:

```text
User ICP
   ↓
Global Profile Database
   ↓
Deterministic Filtering
   ↓
Candidate Profiles
   ↓
Qualification
   ↓
AI Reasoning where required
   ↓
Qualified Leads
```

The system should use the global database first.

Additional permitted research sources may be introduced later.

---

# 19. Global Profile Database

`global_profiles` stores shared prospect facts.

It must not contain user-specific ICP qualification data.

Global profile information includes:

* LinkedIn public identifier
* profile URL
* name
* role
* headline
* company
* location
* industry
* company data
* source
* do-not-contact state
* recommendation count

User-specific qualification belongs in:

```text
users_profiles
```

not `global_profiles`.

---

# 20. Prospect Sources

Global profiles can originate from approved sources such as:

```text
SEED
CSV_IMPORT
USER_MANUAL
WEB
```

Do not automatically seed the global database by scraping LinkedIn.

The source must always be recorded.

---

# 21. Lead Qualification

Qualification should use a layered approach.

## Step 1 — Safety / exclusion checks

Check:

* do-not-contact
* ICP exclusions
* invalid data

before qualification.

## Step 2 — Deterministic qualification

Apply obvious hard filters:

* role
* industry
* location
* company size
* revenue
* other explicit ICP constraints

## Step 3 — Rule-based score

Calculate an initial score where possible.

## Step 4 — Gemini

Use Gemini only where additional reasoning is actually required.

This reduces unnecessary token usage and makes qualification more predictable.

---

# 22. User-Specific Lead Relationship

A global prospect becomes a user's lead through:

```text
users_profiles
```

This table stores:

* match score
* qualification reason
* lead status
* ICP version
* research source
* first seen
* last seen

The same global profile can therefore be qualified differently for different users.

---

# 23. Recommended Count

`global_profiles.recommended_no_of_times` tracks how many times the profile has been newly recommended.

It must be incremented atomically.

Do not increment it repeatedly when the same user sees the same profile again.

The unique relationship:

```text
UNIQUE(user_id, global_id)
```

prevents duplicate user/profile relationships.

---

# 24. Research Jobs

Research must be treated as a persistent job.

The system must not assume a research operation will always finish inside one HTTP request.

Research jobs support:

```text
QUEUED
RUNNING
PAUSED
COMPLETED
FAILED
CANCELLED
```

The job stores:

* research type
* ICP version
* budget
* progress
* stop reason
* results count
* error
* attempts
* heartbeat
* timestamps

Only one active research job should exist per user.

---

# 25. Research Budgets

A research job should be able to limit:

* target leads
* maximum fetches
* maximum Gemini calls
* maximum execution time

This prevents runaway research operations.

---

# 26. Research Freshness

Prospect data should have freshness awareness.

If data is stale:

```text
verify before outreach
```

may be surfaced.

Fresh imported information should not be silently overwritten by older data.

---

# 27. Lead Dashboard

The Leads section should show useful qualification information.

At minimum:

* Lead score
* Name
* Company
* Role
* Business need / reason
* LinkedIn profile
* Lead status

The user should be able to open an individual lead and begin outreach.

---

# 28. Outreach

Outreach is represented as a relationship between:

```text
User
+
Global Prospect
```

using:

```text
connect_and_message
```

There should be one outreach thread per:

```text
user_id + global_id
```

---

# 29. LinkedIn Connection Workflow

Cycle 1 connection flow:

```text
Qualified Lead
      ↓
Create Outreach Thread
      ↓
Gemini generates connection draft
      ↓
User reviews/edits
      ↓
Outreach Service
      ↓
OutreachExecutor
      ↓
Voyager Adapter
      ↓
LinkedIn
      ↓
Connection status updated
```

The generated connection message must be stored.

The user must be able to edit it before sending.

---

# 30. Connection Status

Supported states:

```text
NOT_STARTED
DRAFTED
REQUESTED
ACCEPTED
DECLINED
WITHDRAWN
```

Important timestamps include:

* connection requested
* accepted
* last activity

---

# 31. LinkedIn Message Workflow

After the connection reaches the required state:

```text
Connection Accepted
      ↓
Generate Message
      ↓
User Review/Edit
      ↓
Voyager
      ↓
LinkedIn
      ↓
Store Message
```

Messages must be generated using available context.

Context can include:

* prospect profile
* company
* ICP
* user's company
* user's LinkedIn profile
* previous messages
* previous replies

---

# 32. Conversation History

All outreach communication must be stored as an ordered conversation.

Each message should contain:

```json
{
  "id": "uuid",
  "sequence": 3,
  "sender": "USER",
  "type": "MESSAGE",
  "message": "...",
  "status": "SENT",
  "scheduled_at": null,
  "sent_at": "...",
  "sent_via": "VOYAGER",
  "generated_by": "AI",
  "model": "gemini-...",
  "error": null,
  "created_at": "..."
}
```

Possible senders:

```text
USER
LEAD
```

Possible types:

```text
CONNECTION
MESSAGE
REPLY
FOLLOW_UP
```

Possible statuses:

```text
DRAFT
APPROVED
SCHEDULED
SENT
FAILED
CANCELLED
RECEIVED
```

Messages must be appended.

Never overwrite the complete conversation.

Updates must target the message by:

```text
message.id
```

not array position.

---

# 33. Gemini Conversation Context

When generating a message or follow-up, Gemini should receive relevant conversation context.

For long conversations:

* use the most recent messages
* maintain a summary where required
* avoid sending the entire conversation unnecessarily

A practical initial context window can use approximately the latest 20 messages plus a running summary when the conversation becomes longer.

---

# 34. Follow-up System

Follow-ups should be generated based on:

```text
Prospect
+
Company
+
ICP
+
Conversation
+
Previous Messages
+
Previous Replies
```

Flow:

```text
Conversation
      ↓
Gemini
      ↓
Follow-up Draft
      ↓
User Review
      ↓
Schedule
      ↓
Due Follow-up
      ↓
Outreach Service
      ↓
Voyager
```

---

# 35. Follow-up Scheduling

The scheduler determines what is due.

The scheduler must NOT contain Voyager-specific implementation.

Architecture:

```text
Scheduler
   ↓
Due Outreach Task
   ↓
Outreach Service
   ↓
OutreachExecutor
   ↓
Voyager
```

This separation must remain.

---

# 36. Follow-up State

Supported states:

```text
NONE
SCHEDULED
PAUSED
COMPLETED
STOPPED
```

The system should support:

* pause
* resume
* stop

If a meaningful reply is received, the follow-up sequence should stop automatically unless the user explicitly continues it.

---

# 37. Voyager Send Result

Every Voyager action must return a normalized application-level result.

The rest of the application should not depend on raw Voyager response structures.

Conceptually:

```python
{
    "success": True,
    "external_id": "...",
    "status": "...",
    "error": None
}
```

The Voyager adapter translates the raw LinkedIn response into the normalized result.

---

# 38. Voyager Errors

Voyager-specific errors should be translated into application-level errors.

Examples:

```text
AUTH_EXPIRED
PROFILE_NOT_FOUND
CONNECTION_FAILED
MESSAGE_FAILED
RATE_LIMITED
NETWORK_ERROR
UNKNOWN_ERROR
```

The UI should not expose raw technical Voyager responses to users.

---

# 39. Outreach Versioning

`connect_and_message.version` should support optimistic locking.

Before modifying an outreach thread:

```text
read version
→ perform mutation
→ increment version
```

This prevents concurrent updates from silently overwriting one another.

---

# 40. Cycle 1 Dashboard

The dashboard should eventually expose:

### Overview

* outreach activity
* qualified leads
* pending actions
* follow-ups due

### GTM Research

* research jobs
* progress
* qualified prospects

### Leads

* qualified leads
* filters
* scores
* reasons

### Profile Optimization

* LinkedIn profile suggestions

### Outreach

* connections
* messages
* conversations
* follow-ups

### Research History

* previous research jobs/results

### Settings

* profile
* company
* ICP
* account settings

---

# 41. Cycle 2 — Email Outreach

Email will be introduced after Cycle 1 is stable.

Email should use the same GTM foundation:

```text
Same User
Same Company
Same ICP
Same Lead
Same Global Profile
Same Qualification
Same AI Context
Same Outreach Thread Concept
```

Only the channel execution layer changes.

Conceptually:

```text
OutreachExecutor
       │
       ├── LinkedIn / Voyager
       │
       └── Email
```

The Email channel should not require rebuilding lead qualification or research.

---

# 42. Database Architecture

The product should use exactly **8 core tables** for the current architecture.

Do not add additional tables unless a concrete requirement is discovered and documented.

---

## 42.1 `user_table`

Stores Fameweb user accounts.

Key fields:

```text
user_id
name
email_id
phone_no
password_hash
email_verified_at
onboarding_step
optimization_status
is_active
created_at
updated_at
```

---

## 42.2 `users_company_details`

Stores one user's company information.

Relationship:

```text
user_table 1 ─── 1 users_company_details
```

Stores:

```text
company_name
website_url
description
what_company_sells
products_services
industry
company_size
revenue
location
rating
other_details
scrape_status
edited_fields
scraped_at
created_at
updated_at
```

---

## 42.3 `users_icp`

Stores one user's ICP.

Relationship:

```text
user_table 1 ─── 1 users_icp
```

Stores:

```text
target_customer
company_size
revenue_range
target_jobs_roles
industry
location
keywords
exclusions
signals
tone
summary_report
version
created_at
updated_at
```

---

## 42.4 `users_linkedin_details`

Stores the user's LinkedIn profile/context.

Relationship:

```text
user_table 1 ─── 1 users_linkedin_details
```

Stores:

```text
oidc_sub
linkedin_id
profile_url
name
headline
about
current_position
location
experience
education
skills
profile_data
profile_source
profile_completeness
optimization_suggestions
auth_data_encrypted
connection_status
consent_at
last_verified_at
last_used_at
created_at
updated_at
```

Never store LinkedIn passwords.

---

## 42.5 `global_profiles`

Stores shared prospect facts.

Stores:

```text
global_id
linkedin_id
profile_url
name
role
headline
company
location
industry
company_data
source
do_not_contact
recommended_no_of_times
last_updated
created_at
```

Do not store user-specific ICP score here.

---

## 42.6 `users_profiles`

Stores the relationship between a user and a global prospect.

Stores:

```text
id
user_id
global_id
research_job_id
research_source
match_score
qualification_reason
lead_status
icp_version
first_seen_at
last_seen_at
created_at
updated_at
```

Unique:

```text
UNIQUE(user_id, global_id)
```

---

## 42.7 `research_jobs`

Stores persistent research operations.

Stores:

```text
id
user_id
status
research_type
icp_version
budget
progress
stop_reason
results_count
error_message
attempts
heartbeat_at
started_at
completed_at
created_at
updated_at
```

Only one active:

```text
QUEUED
RUNNING
PAUSED
```

research job per user.

---

## 42.8 `connect_and_message`

Stores one user's outreach relationship with one prospect.

Stores:

```text
id
user_id
global_id
connection_status
connection_message
messages
follow_up_status
next_follow_up_at
version
connection_requested_at
accepted_at
last_activity_at
created_at
updated_at
```

Unique:

```text
UNIQUE(user_id, global_id)
```

---

# 43. JSON Fields

JSON should be used where data is naturally variable or structured.

Do not unnecessarily normalize JSON fields into additional tables.

Examples:

```text
experience
education
skills
company_data
signals
summary_report
budget
progress
messages
```

However, fields that are required for filtering, uniqueness, authorization or relational integrity should remain normal database columns.

---

# 44. API Architecture

Routes should remain thin.

Example:

```text
Route
 ↓
Validate request
 ↓
Authenticate user
 ↓
Call Service
 ↓
Return response
```

Routes should not contain:

* Gemini prompts
* SQL business logic
* Voyager HTTP requests
* complex qualification logic

---

# 45. Core API Areas

## Authentication

```text
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

Additional verification/reset endpoints may be implemented.

---

## Onboarding

```text
GET  /api/onboarding/state
POST /api/onboarding/company/analyze
GET  /api/onboarding/company
PUT  /api/onboarding/company
PUT  /api/onboarding/icp
POST /api/onboarding/icp/summary
POST /api/onboarding/complete
```

---

## LinkedIn

```text
GET  /api/linkedin/connect
GET  /api/linkedin/callback
GET  /api/linkedin/status
POST /api/linkedin/disconnect

POST /api/linkedin/profile/upload
POST /api/linkedin/profile/paste
GET  /api/linkedin/profile
```

The exact LinkedIn authentication endpoints depend on the validated integration approach.

---

## Optimization

```text
POST /api/optimization/generate
GET  /api/optimization
POST /api/optimization/skip
```

---

## Research

```text
POST /api/research/jobs
GET  /api/research/jobs
GET  /api/research/jobs/<id>
POST /api/research/jobs/<id>/cancel
POST /api/research/jobs/<id>/pause
POST /api/research/jobs/<id>/resume
POST /api/research/import
```

---

## Leads

```text
GET   /api/leads
GET   /api/leads/<id>
PATCH /api/leads/<id>
POST  /api/leads/requalify
POST  /api/leads/<id>/opt-out
```

---

## Outreach

```text
POST /api/outreach/threads
GET  /api/outreach/threads
GET  /api/outreach/threads/<id>

POST /api/outreach/threads/<id>/connection/generate
POST /api/outreach/threads/<id>/connection/send
POST /api/outreach/threads/<id>/connection/mark-sent

POST /api/outreach/threads/<id>/accepted

POST /api/outreach/threads/<id>/messages/generate
PATCH /api/outreach/threads/<id>/messages/<message_id>
POST /api/outreach/threads/<id>/messages/<message_id>/send
POST /api/outreach/threads/<id>/messages/<message_id>/mark-sent

POST /api/outreach/threads/<id>/replies

POST /api/outreach/threads/<id>/pause
POST /api/outreach/threads/<id>/resume
POST /api/outreach/threads/<id>/stop

GET /api/outreach/today
```

The final endpoint naming should be aligned with the validated Voyager execution model.

---

# 46. Existing Code Reuse

Existing code should be reused where useful rather than rewritten unnecessarily.

Potential reuse:

### `analyzer.py`

Reuse for:

* company website extraction
* public company enrichment

Must add appropriate URL/security validation.

---

### `profile_extractor.py`

Existing LinkedIn browser extraction should be treated as legacy.

Reuse only non-browser/profile-structuring logic where appropriate.

New profile intake should be separated from browser automation.

---

### `profile_optimizer.py`

Reuse the optimization logic using:

```text
users_linkedin_details
+
users_icp
```

---

### `gtm_engine.py`

Reuse useful:

* qualification
* lead research
* scoring
* orchestration

Remove/disable LinkedIn scraping paths.

Wrap long-running research inside `research_jobs`.

---

### Existing database code

Replace ad-hoc database access with the final repository/model architecture.

Since the project is still in development and there is no production data to preserve, the development database can be recreated using the final schema.

---

# 47. Development Database

There is currently no production/user data that needs to be preserved.

Therefore:

```text
Development DB
    ↓
Reset
    ↓
Create final 8-table schema
```

No complex legacy data migration is required.

However, the codebase should be backed up before major architectural changes.

---

# 48. Project Structure

The project should move toward a clean modular structure.

Target structure:

```text
linkedin_lead_generator/
│
├── app.py
├── config.py
├── requirements.txt
├── .env
├── .env.example
│
├── app/
│   ├── __init__.py
│   │
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── repositories/
│   ├── integrations/
│   │   └── linkedin/
│   │       ├── voyager_client.py
│   │       ├── voyager_auth.py
│   │       ├── profile.py
│   │       └── requests.py
│   │
│   ├── jobs/
│   ├── security/
│   └── utils/
│
├── frontend/
│   ├── templates/
│   └── static/
│       ├── css/
│       ├── js/
│       │   ├── core/
│       │   ├── auth/
│       │   ├── onboarding/
│       │   ├── dashboard/
│       │   ├── research/
│       │   ├── leads/
│       │   └── outreach/
│       └── assets/
│
├── migrations/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
│
├── data/
│   └── development/
│
├── legacy/
│
└── doc/
    └── fameweb_implementation_docs/
```

This is a target architecture, not a requirement to blindly create empty folders.

Only create modules when they contain real functionality.

---

# 49. Security Requirements

The implementation must include:

* Argon2id password hashing
* secure session cookies
* CSRF protection
* authorization checks
* rate limiting for sensitive endpoints
* input validation
* URL validation
* SSRF protection for website scraping
* secure secret management
* no LinkedIn passwords
* no secrets committed to Git
* encrypted storage for sensitive OAuth/session tokens if applicable

---

# 50. Authorization

Every user-specific operation must verify ownership.

For example:

```text
User A cannot access User B's:
- company
- ICP
- LinkedIn profile
- research jobs
- leads
- outreach threads
- messages
```

Never trust a `user_id` supplied by the frontend.

Derive the authenticated user from the server-side session.

---

# 51. AI Usage

Gemini is used for reasoning/generation where deterministic logic is insufficient.

Use deterministic logic first for:

* filtering
* exclusions
* obvious ICP matching
* validation
* state transitions

Use Gemini for:

* company understanding where needed
* ICP summary
* ambiguous lead qualification
* outreach personalization
* connection messages
* LinkedIn messages
* contextual follow-ups
* profile optimization

Avoid unnecessary Gemini calls.

---

# 52. AI Output Safety

Gemini output must be validated before being stored or displayed.

Do not allow malformed model output to break:

* database state
* outreach state
* frontend rendering
* scheduling

Structured JSON should be used where practical.

---

# 53. Frontend Principles

The existing frontend should be improved incrementally.

Do not redesign unrelated screens.

Existing useful UI components should be preserved where possible.

Frontend responsibilities:

```text
Display state
Collect user input
Call API
Render results
```

Frontend must not contain:

* database logic
* Gemini API keys
* Voyager credentials
* direct Voyager requests
* business-critical qualification logic

---

# 54. Error Handling

Errors should be meaningful to users.

Instead of:

```text
HTTP 500
VoyagerError XYZ
```

show something such as:

```text
We couldn't send the connection request right now.
Please try again.
```

Detailed technical errors should be logged server-side.

---

# 55. Logging

Logs should contain enough information to debug:

* research failures
* Gemini failures
* Voyager failures
* authentication failures
* scheduling failures

Do not log:

* passwords
* raw authentication secrets
* sensitive session tokens
* unnecessary personal data

---

# 56. Testing Requirements

At minimum test:

## Authentication

* signup
* duplicate email
* duplicate phone
* login
* logout
* authorization

## Onboarding

* company extraction
* ICP creation
* ICP versioning
* onboarding resume

## Research

* deterministic qualification
* Gemini qualification
* duplicate prevention
* job state transitions
* cancellation
* pause/resume
* recommendation count

## Voyager

* authentication/session validation
* profile resolution
* connection request
* message request
* success response
* failure response
* expired session
* rate limiting/error handling

Where possible, Voyager calls should be mocked in automated tests.

---

# 57. Cycle 1 Mandatory Technical Gate

Before implementing the complete Voyager outreach flow, the team must complete a **Voyager Integration Discovery Gate**.

The gate must document:

```text
1. How authentication works
2. How session state works
3. How a LinkedIn profile is identified
4. How connection requests are sent
5. How messages are sent
6. How responses are interpreted
7. How errors are handled
8. Whether the existing mechanism is suitable for the intended development architecture
```

Only after this is understood should the Voyager adapter contract be finalized.

This prevents the project from reaching a point where the database, services and frontend are built around an incorrect LinkedIn integration assumption.

---

# 58. Cycle 1 Implementation Order

Implementation should happen in this order.

## Phase 0 — Audit

* Backup codebase
* Inspect current repository
* Inspect current LinkedIn/Voyager implementation
* Identify reusable functionality
* Identify legacy browser/session dependencies
* Validate Voyager HTTP flow
* Document findings

**Do not start major refactoring before this phase.**

---

## Phase 1 — Foundation

* Project structure
* configuration
* environment handling
* database setup
* final 8-table schema
* repositories/models
* authentication

---

## Phase 2 — Onboarding

* signup/login
* LinkedIn/profile intake
* company extraction
* company review
* ICP
* ICP summary
* onboarding state

---

## Phase 3 — Profile Optimization

* saved LinkedIn data
* ICP
* optimization generation
* review/skip
* save suggestions

---

## Phase 4 — GTM Research

* global profiles
* research jobs
* deterministic filtering
* Gemini qualification
* user/profile relationship
* lead dashboard

---

## Phase 5 — Voyager Integration

* Voyager client
* Voyager authentication/session handling
* profile resolution
* connection request
* message request
* normalized responses
* error handling
* executor integration

---

## Phase 6 — Outreach

* outreach thread
* connection generation
* connection status
* message generation
* conversation history
* replies
* follow-ups
* scheduling
* pause/resume/stop

---

## Phase 7 — Cycle 1 Validation

Validate the complete flow:

```text
Signup
 ↓
Login
 ↓
Company
 ↓
ICP
 ↓
LinkedIn Profile
 ↓
Dashboard
 ↓
GTM Research
 ↓
Qualified Prospect
 ↓
Outreach Thread
 ↓
Generate Connection
 ↓
Voyager
 ↓
LinkedIn Connection
 ↓
Generate Message
 ↓
Voyager
 ↓
Conversation
 ↓
AI Follow-up
 ↓
Schedule
```

Only after this flow is stable should Cycle 2 begin.

---

# 59. Cycle 1 Definition of Done

Cycle 1 is complete when a user can:

### Account

* create a Fameweb account
* log in
* log out securely

### Onboarding

* provide company information
* configure ICP
* provide/import LinkedIn profile information
* complete onboarding

### GTM

* run GTM Research
* receive relevant prospects
* see qualification score
* see qualification reason
* avoid duplicate user/profile relationships

### LinkedIn Outreach

* open a qualified prospect
* create an outreach thread
* generate a connection message
* edit the message
* execute the connection through the validated Voyager integration
* track connection state
* generate a personalized LinkedIn message
* execute the message through Voyager
* store conversation history
* add replies
* generate contextual follow-ups
* schedule follow-ups
* pause/resume/stop follow-ups

### Architecture

* final 8-table database exists
* research jobs persist
* outreach threads persist
* Voyager logic is isolated
* no direct frontend → Voyager communication
* no direct route → Voyager communication
* no new code depends on the legacy Chromium automation
* authorization works correctly
* tests cover critical flows

---

# 60. Cycle 2 Definition

Cycle 2 will introduce Email Outreach.

The email system should reuse:

```text
User
Company
ICP
Global Profiles
User Profiles
Research
Qualification
AI
Conversation Context
Outreach Threads
Follow-ups
```

Only the execution/channel layer should change.

Long-term:

```text
                    ┌── LinkedIn / Voyager
                    │
GTM + AI + Leads ───┼── Email
                    │
                    ├── Future channel
                    │
                    └── Future channel
```

---

# 61. What Must NOT Be Done

Do not:

* rebuild the entire UI unnecessarily
* create extra database tables without a concrete requirement
* normalize every JSON field
* scrape LinkedIn blindly
* scatter Voyager calls across the application
* put Voyager calls in frontend JavaScript
* expose Voyager/session credentials to frontend
* store LinkedIn passwords
* make GTM Research dependent on LinkedIn outreach
* make Email dependent on LinkedIn
* put scheduling logic inside Voyager
* put Gemini logic inside Voyager
* put database logic inside Voyager
* overwrite conversation history
* overwrite the original lead qualification context
* permanently replace template/context data with AI-generated output
* migrate legacy browser automation into every new service
* introduce complex infrastructure without a concrete requirement

---

# 62. Critical Architectural Boundaries

The following boundaries must remain intact:

```text
                    ┌──────────────────────┐
                    │      Fameweb UI      │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │       API Routes     │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │      Services        │
                    └─────┬─────────┬──────┘
                          ↓         ↓
                    Repository   Integrations
                          ↓         ↓
                       Database   Voyager
```

AI:

```text
Services
   ↓
Gemini Integration
```

Jobs:

```text
Research / Scheduler
   ↓
Services
```

Voyager:

```text
Outreach Service
   ↓
OutreachExecutor
   ↓
Voyager Adapter
```

This separation is one of the most important architectural requirements of the project.

---

# 63. Final Product Direction

Fameweb should evolve toward:

```text
                  FAMEWEB
                     │
        ┌────────────┴────────────┐
        │                         │
   GTM Intelligence          Outreach
        │                         │
   ┌────┴────┐             ┌─────┴─────┐
   │         │             │           │
Company    ICP          LinkedIn      Email
   │         │             │           │
   └────┬────┘             │           │
        ↓                   │           │
      Research              │           │
        ↓                   │           │
     Leads ─────────────────┘           │
        ↓                               │
 Qualification                          │
        ↓                               │
 Personalization ───────────────────────┘
        ↓
 Conversation
        ↓
 AI Follow-ups
        ↓
 Qualified Opportunity
```

The immediate objective is **not to build every channel at once**.

The immediate objective is to build a strong GTM foundation and prove **Cycle 1 — LinkedIn/Voyager Outreach** end-to-end.

Once that foundation is stable, Email becomes another execution channel rather than another independent product.

---

# 64. Final Implementation Rule

When implementation decisions are unclear, prioritize in this order:

```text
1. This PRD
2. Database Schema
3. API Specification
4. Architecture Document
5. Existing working repository behavior
6. Implementation convenience
```

If the existing repository conflicts with this architecture:

**Do not blindly copy the old implementation.**

Identify the conflict, determine whether the existing behavior is required, and preserve the new architectural boundaries.

If the Voyager implementation differs from the assumptions in this PRD:

**Stop at the integration boundary, inspect and validate the actual Voyager flow, then update the integration-specific implementation/documentation before proceeding.**

Do not allow an unverified Voyager assumption to force a redesign of the entire Fameweb architecture.

---

# 65. Product North Star

The final Fameweb experience should feel like:

```text
Tell Fameweb what your company sells
                ↓
Tell Fameweb who you want to reach
                ↓
Fameweb understands your business
                ↓
Fameweb researches the market
                ↓
Fameweb identifies relevant prospects
                ↓
Fameweb explains why they matter
                ↓
Fameweb prepares personalized outreach
                ↓
LinkedIn / Voyager executes Cycle 1 outreach
                ↓
Fameweb understands the conversation
                ↓
Fameweb prepares contextual follow-ups
                ↓
Email becomes an additional channel in Cycle 2
                ↓
Fameweb becomes the user's GTM / outbound workspace
```

**This is the overall product direction.**
**Cycle 1 is the LinkedIn/Voyager implementation of that direction.**
**Cycle 2 adds Email without rebuilding the underlying GTM system.**
