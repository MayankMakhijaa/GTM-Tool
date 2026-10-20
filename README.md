# Fameweb — LinkedIn Lead Generator & GTM Discovery Engine

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Flask-black.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![Scraping](https://img.shields.io/badge/scraping-Playwright%20Chromium-orange.svg)](https://playwright.dev/python/)
[![LLM Engine](https://img.shields.io/badge/ai-Google%20Gemini%202.5%20Flash-blueviolet.svg)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/tests-pytest%20(fameweb__test)-success.svg)](https://docs.pytest.org/)

---

## 1. Executive Summary & Architecture Overview

Fameweb LinkedIn Lead Generator is an AI-orchestrated B2B lead generation, Ideal Customer Profile (ICP) extraction, GTM prospect discovery, and LinkedIn profile optimization platform. 

The application is structured as a Flask backend with server-rendered Jinja2 templates and vanilla JavaScript frontend components. It coordinates multiple external services:
1. **Google Gemini Flash (LLM)** — powers company intelligence extraction, structured ICP generation, and LinkedIn profile audit recommendations.
2. **Playwright Chromium** — manages automated company website scraping, interactive LinkedIn user authentication, and persistent browser contexts.
3. **LinkedIn Voyager API Client** — performs high-throughput discovery searches for qualified B2B decision-makers matching generated ICP parameters.
4. **Google Places API** — serves as rating and review fallback enrichment when lead profiles or company profiles require trust scoring.
5. **PostgreSQL** — persistent storage partitioned strictly between development (`fameweb`) and testing (`fameweb_test`).

### 1.1 End-to-End System Architecture

```mermaid
flowchart TD
    subgraph Client [Browser Client]
        UI[Jinja2 + Vanilla JS UI]
    end

    subgraph Backend [Flask Application Core]
        Auth[Auth & Session Engine\nbcrypt + Fernet]
        Wiz[Onboarding & Company Scraper]
        ICP[ICP Builder & Geo Autocomplete]
        GTM[GTM Background Job Runner]
        PO[Profile Optimization Engine]
    end

    subgraph Data [PostgreSQL Database]
        DevDB[(fameweb - Development)]
        TestDB[(fameweb_test - Pytest Safe)]
    end

    subgraph Ext [External Services & Browser Engines]
        Gemini[Google Gemini 2.5 Flash]
        Playwright[Playwright Chromium Profile]
        Voyager[LinkedIn Voyager API]
        GPlaces[Google Places API]
    end

    UI <-->|HTTP / JSON Session| Backend
    Backend <-->|SQLAlchemy ORM| DevDB
    Wiz <-->|DOM Extraction| Playwright
    Wiz <-->|Structured Prompting| Gemini
    ICP <-->|Validation & Correction| Gemini
    GTM <-->|Decrypted Cookies| Voyager
    GTM <-->|Rating Fallback| GPlaces
    PO <-->|Audit & Rewrite| Gemini
```

### 1.2 User Onboarding & GTM Discovery Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant App as Fameweb App
    participant DB as PostgreSQL (fameweb)
    participant PW as Playwright / Chromium
    participant Gemini as Gemini 2.5 Flash
    participant Voyager as LinkedIn Voyager API

    User->>App: Sign up (/signup)
    App->>DB: Create User + Generate 6-Digit OTP
    App-->>User: Redirect to /verify-otp
    User->>App: Submit OTP
    App->>DB: Set is_verified=True, issue session cookie

    User->>App: Submit Company URL (/company/scrape)
    App->>PW: Scrape target website text
    PW-->>App: Raw HTML / Text
    App->>Gemini: Extract products, target audience, value prop
    Gemini-->>App: Structured Company Profile JSON
    App->>DB: Store in company_profiles

    User->>App: Define ICP & Select Target Country (/icp)
    App->>App: Autocomplete & spelling correction (/api/spelling/suggest)
    App->>DB: Persist in icp_targets

    User->>App: Connect LinkedIn (/linkedin/connect)
    App->>PW: Launch Chromium persistent session
    User->>PW: Interactively complete LinkedIn login + 2FA
    PW->>App: Harvest li_at & JSESSIONID cookies
    App->>DB: Encrypt with Fernet -> Store in linkedin_sessions

    User->>App: Launch Lead Discovery (/api/gtm/jobs/start)
    App->>App: Spawn background discovery thread
    App->>DB: Create gtm_jobs record (status=RUNNING)
    App-->>User: Return job_id for polling
    App->>DB: Retrieve and decrypt li_at & JSESSIONID
    Note over App,Voyager: Discovery Execution (Subject to Session Reuse Verification)
    App->>Voyager: Query decision makers (titles, geo, company size)
    Voyager-->>App: Prospect batch
    App->>DB: Insert qualified records into gtm_opportunities
    User->>App: Download results (/api/download-excel)
```

---

## 2. Component & Implementation Status Matrix

| Component | Status | Key Modules / Files | Primary Dependencies | Notes |
|:---|:---:|:---|:---|:---|
| **User Authentication & OTP** | **Production Ready** | `app/routes/auth_routes.py`<br>`app/models/user.py`<br>`app/utils/otp.py` | Flask-Login, bcrypt, psycopg2 | 6-digit database-backed OTP, expiration window, bcrypt password hashing. |
| **Onboarding Wizard** | **Production Ready** | `app/routes/onboarding_routes.py`<br>`templates/onboarding/` | Jinja2, Vanilla JS | Multi-step state tracking across company profile, ICP, and account connection. |
| **Company Website Scraping** | **Operational** | `app/services/company_scraper.py`<br>`app/routes/company_routes.py` | Playwright, BeautifulSoup4, Gemini API | Headless browser extraction of target website metadata, hero text, and meta tags. |
| **ICP Extraction & Builder** | **Production Ready** | `app/services/icp_service.py`<br>`app/routes/icp_routes.py` | Google GenAI SDK, Pydantic | Enforces strict JSON schema: target titles, industries, company headcounts, pain points. |
| **Country Autocomplete & Spelling** | **Production Ready** | `app/services/country_service.py`<br>`app/routes/country_routes.py` | Python standard library | Fuzzy matching against standardized ISO 3166-1 country list. |
| **LinkedIn Session Encryption** | **Production Ready** | `app/integrations/linkedin/session_manager.py`<br>`app/models/linkedin_session.py` | `cryptography` (Fernet) | Zero-cleartext cookie storage in PostgreSQL; Fernet key derived from `SECRET_KEY`. |
| **LinkedIn Profile Reconnect Modal** | **Production Ready** | `app/routes/linkedin_routes.py`<br>`templates/components/reconnect_modal.html` | Playwright persistent profile | Prompts user to launch Chromium session when cookies expire or flag invalid. |
| **GTM Job Runner & Polling** | **Operational** | `app/services/gtm_runner.py`<br>`app/routes/gtm_routes.py` | Python `threading`, SQLAlchemy | Non-blocking background thread worker with status polling (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`). |
| **LinkedIn Voyager Discovery** | **Blocked on Live Auth** | `app/integrations/linkedin/voyager_client.py`<br>`app/services/discovery_pipeline.py` | Requests, Playwright | Clean local decryption; standalone HTTP requests rejected by LinkedIn without browser context (see Section 5). |
| **Google Places Rating Fallback** | **Operational** | `app/services/rating_fallback.py` | Google Places API, Requests | Enriches business records lacking direct reviews or trust signals. |
| **Profile Optimization Analysis** | **Production Ready** | `app/routes/profile_optimization_routes.py`<br>`app/services/profile_optimizer.py` | Gemini 2.5 Flash, Jinja2 | Multi-section audit: Headline, About, Experience, Skills, CTA suggestions. |
| **Export Engine (CSV / Excel)** | **Production Ready** | `app/routes/export_routes.py`<br>`app/utils/excel_exporter.py` | `pandas`, `openpyxl` | Generates formatted Excel/CSV exports of discovered GTM opportunities. |
| **Database Isolation Guard** | **Hardened** | `tests/conftest.py` | pytest, SQLAlchemy | `assert_safe_test_db()` halts execution if test database is not named `fameweb_test`. |

---

## 3. Repository Directory Structure

```text
linkedin_lead_generator/
├── app/
│   ├── __init__.py                  # Flask app factory, extension registration
│   ├── config.py                    # Base, Development, Testing, Production configurations
│   ├── integrations/
│   │   └── linkedin/
│   │       ├── __init__.py
│   │       ├── session_manager.py   # Fernet encryption & cookie retrieval
│   │       └── voyager_client.py    # LinkedIn Voyager API endpoints & query builder
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                  # User, OTP credentials, verification flags
│   │   ├── company_profile.py       # Scraped and synthesized company metadata
│   │   ├── icp_target.py            # Target buyer personas, industries, geography
│   │   ├── linkedin_session.py      # Encrypted li_at & JSESSIONID storage
│   │   ├── gtm_job.py               # Background job state, progress, error logs
│   │   └── gtm_opportunity.py       # Discovered leads, prospect metadata, status
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth_routes.py           # /signup, /login, /verify-otp, /resend-otp, /logout
│   │   ├── onboarding_routes.py     # /onboarding/step-one, onboarding progress
│   │   ├── company_routes.py        # /company, /company/scrape
│   │   ├── icp_routes.py            # /icp, /icp/save, /api/spelling/suggest
│   │   ├── country_routes.py        # /countries autocomplete
│   │   ├── linkedin_routes.py       # /linkedin/status, /linkedin/reconnect, /linkedin/connect
│   │   ├── gtm_routes.py            # /api/gtm/jobs/start, /api/gtm/jobs/<id>/status, /api/gtm-opportunities
│   │   ├── profile_optimization_routes.py # /profileoptimization, /api/optimize-profile
│   │   └── export_routes.py         # /api/download-excel, /api/download-csv
│   ├── services/
│   │   ├── company_scraper.py       # Playwright DOM scraper + Gemini synthesis
│   │   ├── icp_service.py           # ICP normalization, validation, and Gemini structuring
│   │   ├── country_service.py       # Standardized ISO country lexicon & search
│   │   ├── discovery_pipeline.py    # GTM candidate orchestrator
│   │   ├── gtm_runner.py            # Threaded job queue and executor
│   │   ├── rating_fallback.py       # Google Places API enrichment
│   │   └── profile_optimizer.py     # Multi-vector Gemini prompt orchestrator
│   └── utils/
│       ├── encryption.py            # Fernet symmetric encryption helpers
│       ├── excel_exporter.py        # Openpyxl dataframe-to-spreadsheet generator
│       └── otp.py                   # Secure 6-digit numeric OTP generator
├── browser_profiles/                # [GIT-IGNORED] Persistent Chromium user data directories
├── migrations/                      # Database migration scripts
├── static/
│   ├── css/                         # Custom design system (vanilla CSS tokens)
│   └── js/                          # Interactive client-side controllers
├── templates/
│   ├── base.html                    # Root Jinja2 shell layout
│   ├── auth/                        # Login, signup, OTP templates
│   ├── onboarding/                  # Multi-step wizard views
│   ├── gtm/                         # Discovery dashboard & results tables
│   ├── profile_optimization/        # Profile audit inputs & suggestion cards
│   └── components/                  # Reconnect modals, alerts, navbars
├── tests/
│   ├── conftest.py                  # Pytest fixtures, test database assertion guards
│   ├── unit/                        # Isolated logic tests (OTP, models, encryption)
│   ├── integration/                 # Multi-component tests (ICP, Onboarding, GTM runner)
│   └── e2e/                         # End-to-end workflow validations
├── collections.json                 # Postman / API collection for Fameweb endpoints
├── requirements.txt                 # Python package dependencies
├── run.py                           # Local development entry point
└── README.md                        # Project documentation & developer handover
```

---

## 4. Local Setup & Execution Guide

### 4.1 Prerequisites
- **Operating System:** Windows 10/11, macOS, or Linux.
- **Python:** Python 3.10 or higher.
- **PostgreSQL:** Version 14 or higher running locally on port `5432`.
- **Browser Runtime:** Playwright Chromium binaries installed.

### 4.2 Step-by-Step Installation (Windows PowerShell)

```powershell
# 1. Clone the repository and switch to the project directory
cd D:\Programming\FameWebs_Internship\linkedin_lead_generator

# 2. Create and activate a Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Upgrade pip and install package dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Install Playwright browser binaries (Chromium only)
playwright install chromium

# 5. Create the development and test databases in PostgreSQL
psql -U postgres -h localhost -c "CREATE DATABASE fameweb;"
psql -U postgres -h localhost -c "CREATE DATABASE fameweb_test;"

# 6. Configure your environment variables
Copy-Item .env.example .env
# Edit .env with your PostgreSQL credentials and Gemini API Key
```

### 4.3 Running the Development Server

```powershell
# Start the Flask development server
python run.py
```
The server will bind to `http://localhost:5000`.

---

## 5. Critical Handover: LinkedIn Session Persistence & Voyager API Issue

> [!CAUTION]
> **READ CAREFULLY BEFORE ATTEMPTING LINKEDIN SCRAPING OR AUTOMATION.**
> 
> A common misconception when working with this codebase is that successful local decryption of stored session cookies indicates a working LinkedIn API connection. **It does not.** Stored cookie decryption and remote LinkedIn session validity are completely separate concerns.

### 5.1 The Observed Failure Mode
The application implements persistent browser authentication through Playwright:
1. The user logs in interactively via an automated Chromium window.
2. Playwright extracts the `li_at` and `JSESSIONID` cookies upon successful navigation to `https://www.linkedin.com/feed/`.
3. The cookies are encrypted using Fernet symmetric encryption and stored in PostgreSQL (`linkedin_sessions` table).
4. `session_manager.py` successfully retrieves and decrypts these cookies in subsequent application cycles.

**The Problem:**
When a headless Voyager client or standalone Python `requests.Session` attempts to query LinkedIn endpoints (e.g., `https://www.linkedin.com/voyager/api/graphql` or `/feed/`) using these extracted cookies:
- LinkedIn responds with an immediate **`HTTP 302 Found` redirecting to `https://www.linkedin.com/login`**.
- LinkedIn sends response headers containing `Set-Cookie: li_at=deleted; expires=Thu, 01 Jan 1970 00:00:00 GMT` and `Clear-Site-Data: "cookies", "storage"`.
- Subsequent calls fail with **`HTTP 403 Forbidden` / CSRF validation error** (`ajax:9999999999` mismatch).
- Even when launching Playwright with a persistent profile directory (`browser_profiles/<user_id>/`), closing and reopening the browser frequently causes LinkedIn to invalidate the stored session.

### 5.2 Diagnostic Facts vs. Hypotheses

| Known Facts (Verified by Tests & Logs) | Unresolved Hypotheses (Requiring Investigation) |
|:---|:---|
| Fernet storage, encryption, and decryption functions correctly without byte corruption. | **Device / TLS Fingerprinting:** LinkedIn detects Python `requests` (JA3/TLS fingerprint mismatch) and revokes the session. |
| Decrypted cookie values match the exact strings extracted during the initial Playwright login. | **IP / Device Binding:** LinkedIn ties `li_at` to the specific client IP and ephemeral Chromium instance identifier. |
| In-browser navigation works while the Playwright session remains continuously open. | **CSRF Token Invalidation:** The `JSESSIONID` cookie value must strictly match the `csrf-token` header, which LinkedIn may rotate upon browser close. |
| Attempting headless queries after browser shutdown yields `302 -> /login`. | **Headless Profile Flags:** Chromium profile closing triggers LinkedIn's server-side session termination beacon (`unload` hooks). |

### 5.3 Diagnostic Architecture

```mermaid
graph TD
    A[Interactive Playwright Login] -->|Success| B[Harvest li_at & JSESSIONID]
    B -->|Fernet Encrypt| C[(PostgreSQL: linkedin_sessions)]
    C -->|Fernet Decrypt| D[Python Decrypted Cookies]
    
    subgraph Working Layer
        A
        B
        C
        D
    end

    subgraph Failing Layer [Unresolved Live Layer]
        D -->|Pass Cookies to requests.Session| E[Voyager API Request]
        E -->|LinkedIn Response| F[HTTP 302 Redirect to /login]
        F --> G[Set-Cookie: li_at=deleted]
        F --> H[HTTP 403 CSRF Failure]
    end

    style WorkingLayer fill:#e6ffed,stroke:#2ea44f
    style FailingLayer fill:#ffeef0,stroke:#cb2431
```

### 5.4 Actionable Next Steps for Developer Mayank
To resolve the live prospect discovery engine, follow this prioritized checklist:

1. **Verify Session Lifespan in Headful Mode:**
   - Launch Playwright with `headless=False` using the persistent profile in `browser_profiles/<user_id>/`.
   - Test whether navigating to `https://www.linkedin.com/feed/` retains login state across browser restarts without Python `requests`.
2. **Implement In-Browser Proxy Fetching:**
   - Instead of extracting cookies and executing requests via Python `requests`, execute the Voyager API queries directly inside the active Playwright page context using `page.evaluate("fetch(...)")`.
   - This ensures all browser-level headers, HTTP/2 multiplexing, TLS fingerprints, and internal CSRF state remain 100% authentic.
3. **Inspect Cookie Scope and Formatting:**
   - Verify whether `JSESSIONID` has double-quotes (e.g., `"ajax:123456789"` vs `ajax:123456789`). Voyager requires the `csrf-token` request header to match the unquoted value.
4. **Evaluate Headless Detection Evasion:**
   - If Playwright must run headlessly, integrate `playwright-stealth` or configure standard evasion arguments (`--disable-blink-features=AutomationControlled`).

---

## 6. Environment Variables Reference

Create a `.env` file in the root directory. Below are the required and optional configuration keys:

| Variable Name | Required | Default / Example | Purpose |
|:---|:---:|:---|:---|
| `FLASK_APP` | Yes | `run.py` | Flask application entry point. |
| `FLASK_ENV` | Yes | `development` | Runtime environment (`development` or `production`). |
| `SECRET_KEY` | Yes | *64-character random hex string* | Session signing and Fernet encryption key derivation. |
| `DATABASE_URL` | Yes | `postgresql://postgres:password@localhost:5432/fameweb` | Primary application database connection string. |
| `TEST_DATABASE_URL` | Yes | `postgresql://postgres:password@localhost:5432/fameweb_test` | Dedicated isolated testing database connection string. |
| `GEMINI_API_KEY` | Yes | `AIzaSy...` | API key for Google Gemini 2.5 Flash used in ICP and Profile Optimization. |
| `GOOGLE_PLACES_API_KEY` | Optional | `AIzaSy...` | API key for Google Places ratings and reviews fallback. |
| `PLAYWRIGHT_HEADLESS` | Optional | `False` | Run Chromium headlessly (`True`) or with GUI (`False`). |
| `LINKEDIN_BROWSER_DIR` | Optional | `./browser_profiles` | Root storage path for Chromium persistent user-data profiles. |
| `OTP_EXPIRY_MINUTES` | Optional | `10` | Lifetime in minutes for 6-digit signup verification codes. |

---

## 7. Database Architecture & Models

The application uses SQLAlchemy ORM with a normalized PostgreSQL relational schema.

```mermaid
erDiagram
    USERS ||--o{ COMPANY_PROFILES : owns
    USERS ||--o{ ICP_TARGETS : defines
    USERS ||--o| LINKEDIN_SESSIONS : maintains
    USERS ||--o{ GTM_JOBS : triggers
    GTM_JOBS ||--o{ GTM_OPPORTUNITIES : generates

    USERS {
        int id PK
        string email UK
        string password_hash
        boolean is_verified
        string otp_code
        timestamp otp_expires_at
        timestamp created_at
    }

    COMPANY_PROFILES {
        int id PK
        int user_id FK
        string company_name
        string website_url
        text raw_scraped_text
        jsonb products_services
        jsonb target_audience
        jsonb value_proposition
        timestamp created_at
    }

    ICP_TARGETS {
        int id PK
        int user_id FK
        string target_country
        jsonb target_roles
        jsonb target_industries
        jsonb company_sizes
        text pain_points
        timestamp updated_at
    }

    LINKEDIN_SESSIONS {
        int id PK
        int user_id FK
        text encrypted_li_at
        text encrypted_jsessionid
        boolean is_valid
        timestamp last_verified_at
    }

    GTM_JOBS {
        int id PK
        int user_id FK
        string status
        int total_leads
        int processed_leads
        text error_message
        timestamp started_at
        timestamp completed_at
    }

    GTM_OPPORTUNITIES {
        int id PK
        int job_id FK
        string full_name
        string linkedin_url
        string job_title
        string company_name
        string country
        float rating
        int reviews_count
        string qualification_status
        timestamp created_at
    }
```

---

## 8. API & Route Reference

### 8.1 Authentication & Profile Management
- `POST /signup` — Register a new user account and dispatch 6-digit verification OTP.
- `POST /verify-otp` — Verify email OTP and establish authenticated session.
- `POST /resend-otp` — Regenerate and resend active OTP.
- `POST /login` — Authenticate existing user with email and password.
- `GET /logout` — Invalidate user session and clear client cookies.
- `GET /me` — Return authenticated user identity and onboarding status.

### 8.2 Onboarding & Company Scraping
- `GET /onboarding/step-one` — Render company domain input wizard.
- `POST /company/scrape` — Trigger Playwright website scrape and Gemini summarization.
  - *Payload:* `{"website_url": "https://example.com"}`
- `GET /company` — Retrieve synthesized company profile.

### 8.3 ICP Definition & Geolocation
- `GET /icp` — Render ICP configuration form.
- `POST /icp/save` — Save target buyer personas, industry filters, and country selections.
- `GET /countries?q=<query>` — Autocomplete ISO standardized country names.
- `POST /api/spelling/suggest` — Fuzzy spell-check and auto-correct user search terms.

### 8.4 LinkedIn Integration & GTM Lead Discovery
- `GET /linkedin/status` — Return active session status (`connected`, `expired`, `disconnected`).
- `POST /linkedin/connect` — Spawn Playwright Chromium session for interactive authentication.
- `POST /linkedin/reconnect` — Trigger re-authentication modal workflow.
- `POST /api/gtm/jobs/start` — Launch asynchronous GTM prospect discovery worker.
  - *Payload:* `{"icp_id": 1, "max_leads": 50}`
  - *Response:* `{"job_id": "abc-123", "status": "RUNNING"}`
- `GET /api/gtm/jobs/<id>/status` — Poll background job progress.
- `GET /api/gtm-opportunities` — Fetch table of discovered lead opportunities.
- `GET /api/download-excel` — Download generated leads as formatted Excel spreadsheet (`.xlsx`).
- `GET /api/download-csv` — Download generated leads as standard CSV file.

### 8.5 LinkedIn Profile Optimization
- `GET /profileoptimization` — Render profile audit workspace.
- `POST /api/extract-profile` — Scrape target user profile sections via Playwright.
- `POST /api/optimize-profile` — Execute Gemini multi-vector audit (Headline, About, Experience) with rewrite recommendations.

---

## 9. Testing & Quality Assurance Protocol

### 9.1 Database Isolation & Safety Safeguards
Automated testing interacts strictly with the isolated test database `fameweb_test`. 
In `tests/conftest.py`, the `assert_safe_test_db()` fixture enforces safety:

```python
def assert_safe_test_db(engine):
    """Halts execution if tests attempt to connect to production or development databases."""
    db_name = engine.url.database
    if db_name != "fameweb_test":
        raise RuntimeError(
            f"SAFETY VIOLATION: Tests must execute against 'fameweb_test'. "
            f"Attempted connection to: '{db_name}'."
        )
```

### 9.2 Running Automated Tests

```powershell
# Run the complete core integration test suite
.\venv\Scripts\pytest.exe tests/integration/test_gtm_pipeline.py tests/integration/test_icp_builder.py tests/integration/test_profile_optimization_dataflow.py tests/integration/test_linkedin_reconnect_persistence.py

# Run with verbose output and test execution timings
.\venv\Scripts\pytest.exe -v --durations=10 tests/integration/
```

### 9.3 Test Suite Status (Current Master)
- **Focused Integration Suites:** **92 Passed / 92 Total (100%)**
  - `test_gtm_pipeline.py`: 34 passed
  - `test_icp_builder.py`: 29 passed
  - `test_profile_optimization_dataflow.py`: 15 passed
  - `test_linkedin_reconnect_persistence.py`: 14 passed
- **Full Suite Overview:** **292 Passed, 6 Failed**
  - *Note on Failures:* The 6 failures in `tests/integration/test_google_places_rating_fallback.py` are caused by a mock signature discrepancy (`lookup_google_places_rating` signature update) and do not reflect broken core application logic.

> [!NOTE]
> Tests in `tests/integration/` utilize mock adapters for external API calls (Gemini, LinkedIn Voyager, and Google Places). **Passing test suites verify application logic, state transitions, and database transactions; they do not imply that LinkedIn's live API accepts headless session queries.**

---

## 10. Prioritized Development Roadmap

1. **Resolve Voyager API Session Reuse (High Priority):**
   - Implement in-page `evaluate` fetch inside active Playwright context to bypass TLS and CSRF fingerprint rejections.
2. **Harmonize Google Places Mock Signatures (Quick Win):**
   - Align mock parameters in `tests/integration/test_google_places_rating_fallback.py` to restore 100% full-suite pass rate.
3. **Asynchronous Task Queue (Celery / Redis):**
   - Transition the background job runner from Python `threading.Thread` to Celery with Redis for job persistence across app restarts.
4. **CRM Sync Integrations:**
   - Add webhook and direct API sync connectors (HubSpot, Salesforce, Pipedrive) for discovered GTM opportunities.
5. **Team Workspaces & Role-Based Access Control (RBAC):**
   - Expand database schema to support organizations, team seats, and shared lead collections.
6. **Automated Connection Requests & Message Sequences:**
   - Integrate personalized outreach messaging based on Gemini-synthesized prospect profile insights.

---

## 11. Git & Deployment Hygiene

### 11.1 Sensitive Directories & Untracked Files
The following files and directories exist in the local workspace and **must never be committed or pushed to public remotes**:
- `browser_profiles/` — Contains live Chromium user-data profiles, local SQLite cookie databases, cache partitions, and active session tokens.
- `collections.json` — Local Postman collection containing development URLs and route tests.
- `.env` — Contains local database credentials and private API keys.

Ensure `.gitignore` contains:
```gitignore
.env
venv/
__pycache__/
*.pyc
browser_profiles/
browser_profile/
*.dump
*.log
```

---

*Handover document authored and verified on `master` (commit `77b5fe6`). Ready for developer Mayank.*
