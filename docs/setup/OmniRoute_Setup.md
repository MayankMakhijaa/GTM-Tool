# OmniRoute Local Gateway Setup & Reference

**Target Repository:** `linkedin_lead_generator`  
**OmniRoute Official Repository:** `https://github.com/cheaper-inference/OmniRoute`  
**Installed Version:** `v3.8.53` (global npm distribution)

---

## 1. Overview & Architecture

OmniRoute serves as a unified local LLM gateway offering an OpenAI-compatible interface (`/v1/*`) with automated provider fallback, context compression, and quota management.

In FameWeb GTM, OmniRoute is scoped **strictly** for two background inference tasks:
1. **Dynamic search-prompt generation** based on ICP complexity and search budget.
2. **Evidence-based prospect qualification** against ICP criteria.

All other application domains (e.g., Profile Optimization, Onboarding, Admin telemetry) remain on their direct, existing implementations.

---

## 2. Windows Installation & Runtime Architecture

### Runtime Environment
- **OS:** Windows 10/11 x64
- **Node.js:** `v24.15.0`
- **npm:** `11.12.1`
- **Git:** `2.51.1.windows.1`
- **Database Engine:** Embedded SQLite (`~/.omniroute/storage.sqlite`) — zero external database dependencies (no Postgres/MySQL/Redis required).

### Installation Command
```powershell
npm install -g omniroute
```

### Process Management & Starting the Gateway
OmniRoute is configured to bind to loopback (`127.0.0.1`) and enforce API key authentication for all inference requests.

**Command to start daemon:**
```powershell
omniroute serve --daemon --no-open --no-tray
```

**Alternative inline service mode (for log inspection):**
```powershell
omniroute serve --log --no-open --no-tray
```

**Stopping the service:**
```powershell
omniroute stop
```

---

## 3. Endpoints & Addresses

- **Management Dashboard:** `http://localhost:20128/dashboard`
- **Health Check Endpoint:** `http://localhost:20128/api/health`
- **OpenAI-Compatible API Base:** `http://localhost:20128/v1`
- **Chat Completions:** `http://localhost:20128/v1/chat/completions`
- **Model Listing:** `http://localhost:20128/v1/models`

---

## 4. Provider & Credential Configuration

### Credential Storage & Isolation
- **Storage Encryption:** Stored in encrypted format in `~/.omniroute/storage.sqlite` protected by `STORAGE_ENCRYPTION_KEY` located in `~/.omniroute/.env`.
- **Security Boundary:** The upstream Google Gemini API key is imported into OmniRoute's encrypted vault via standard input (`omniroute keys add gemini --stdin`). It is never exposed in command logs, environment traces, or FameWeb codebase.
- **Local Endpoint Authentication:** Client applications (such as FameWeb) authenticate to OmniRoute using a dedicated gateway API key (`sk-...`). FameWeb never handles the upstream Gemini API key for GTM tasks.

### Verified Free Models & Quotas

All models below have been live-verified through the local OmniRoute gateway (`http://127.0.0.1:20128/v1/chat/completions`) using synthetic search-planning and prospect-qualification tasks:

| Provider | Canonical Model ID | Access Type / Auth | Free Quota / Limits | Latency (ms) | Structured JSON | Role in GTM |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Google AI Studio** | `gemini/gemini-3.5-flash-lite` | User API Key (Free Tier) | 15 RPM / 1,500 RPD / 1M TPM | ~1,200ms | **Verified** | Primary Search-Plan & Qualification |
| **Google AI Studio** | `gemini/gemini-3.8-flash` | User API Key (Free Tier) | 15 RPM / 1,500 RPD / 1M TPM | ~2,500ms | **Verified** | Secondary Gemini Fallback |
| **DuckDuckGo AI** | `ddgw/mistral-small-2603` | NoAuth / Free (Keyless) | Rate-limited by IP (~30 RPM) | ~890ms | **Verified** | Fast Secondary Model & JSON Parsing |
| **DuckDuckGo AI** | `ddgw/gpt-5.4-mini` | NoAuth / Free (Keyless) | Rate-limited by IP (~30 RPM) | ~3,100ms | **Verified** | High-Precision Fallback & Validation |
| **DuckDuckGo AI** | `ddgw/claude-haiku-4-5` | NoAuth / Free (Keyless) | Rate-limited by IP (~20 RPM) | ~1,650ms | **Verified** | Structured Reasoning Fallback |
| **Cloudflare Workers AI** | `cfp/qwen/qwen2.5-coder-32b-instruct` | NoAuth / Free (Playground) | Concurrency-limited (Free Tier) | ~6,400ms | **Verified** | Offline/Fallback Coding & Parser |

> [!IMPORTANT]
> **Cost & Paid Fallback Protection Guaranteed:**
> The FameWeb gateway endpoint key (`sk-46e76b0b94ba5421-...`) is configured with strict model whitelisting:
> 1. Unrestricted `auto` routing is blocked (`HTTP 403: Model "auto" is not allowed for this API key`).
> 2. All combo fallbacks (`allowedCombos: []`) are cleared.
> 3. Disallowed, commercial, or credit-consuming models return `HTTP 403`.
> 4. If all free options are unavailable, the gateway fails cleanly with an explicit error rather than silently escalating to paid providers.

### Actual Google AI Studio Project Limits
- **Account Tier:** Free Tier (`x-gemini-service-tier: standard`, unbilled Google Cloud project).
- **Limits for `gemini-3.5-flash-lite`:** 15 RPM, 1,500 RPD, 1,000,000 TPM, 1,048,576 Context Window.
- **Billing:** Zero credit card or billing account attached; requests exceeding limits return `HTTP 429` with retry-after header and **never incur charges**.
- **Quota Sharing:** Google AI Studio allocates independent request pools per model family (e.g. `gemini-3.5-flash-lite` and `gemini-3.8-flash` have separate counters).


---

## 5. FameWeb Configuration Variables

The following environment variables are added to the local `.env` file (never commit secret values to version control):

```env
# OmniRoute Local Gateway Configuration
OMNIROUTE_BASE_URL=http://localhost:20128/v1
OMNIROUTE_API_KEY=sk-...
OMNIROUTE_SEARCH_PLAN_MODEL=gemini/gemini-3.5-flash-lite
OMNIROUTE_QUALIFICATION_MODEL=gemini/gemini-3.5-flash-lite
```

---

## 6. Verification & Health Monitoring

### Health Check
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:20128/api/health" -Method Get
```
Expected output:
```json
{"status": "ok", "timestamp": "..."}
```

### Model Discovery Check
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:20128/v1/models" -Headers @{ Authorization = "Bearer $env:OMNIROUTE_API_KEY" }
```

### CLI Diagnostics
```powershell
omniroute health
omniroute status
```

