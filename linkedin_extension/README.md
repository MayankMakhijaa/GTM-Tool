# FameWeb LinkedIn Integrator Chrome Extension

Locally developed Google Chrome Extension (Manifest V3) for FameWebpair programming and local testing.

## Local Installation Steps (Chrome)

1. Open Google Chrome.
2. Navigate to `chrome://extensions`.
3. In the upper-right corner of the Extensions page, toggle **Developer mode** to ON.
4. Click the **Load unpacked** button in the top-left toolbar.
5. In the file picker, select this directory:
   `D:\Programming\FameWebs_Internship\linkedin_lead_generator\linkedin_extension`
6. The extension **FameWeb LinkedIn Integrator** (v1.0.0) is now loaded and active.
7. Return to FameWeb at `http://localhost:5000/onboarding/integrations`.

---

## Security Architecture & Guarantees

- **Zero-Secret Standard**: The extension **never** reads, logs, stores, or transmits your LinkedIn password, authentication cookies (`li_at`), or JSESSIONID.
- **Minimal Status Signal**: Only reports boolean session presence (`CONNECTED`, `NOT_LOGGED_IN`, `VERIFICATION_FAILED`) across the content bridge to the FameWeb onboarding dashboard.
- **Scoped Permissions**: Restricts messaging to `http://localhost/*` and `http://127.0.0.1/*`.

