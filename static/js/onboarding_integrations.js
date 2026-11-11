/**
 * Onboarding Authentication & Integrations Controller
 * Manages SMTP email configuration and local FameWeb Chrome Extension LinkedIn verification.
 * Strictly adheres to zero-secret transmission and zero-cookie logging standards.
 */

document.addEventListener('DOMContentLoaded', () => {
    initIntegrations();
});

let isExtensionDetected = false;
let isLinkedInConnected = false;
let isSmtpConfigured = false;

async function initIntegrations() {
    await loadIntegrationStatuses();
    detectExtension(false);
    setupSmtpAutoDetection();
    setupExtensionMessageListeners();
}

const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

// ====================================================================
// 1. LOAD INTEGRATION STATUSES FROM POSTGRESQL
// ====================================================================

async function loadIntegrationStatuses() {
    try {
        const res = await fetch('/api/onboarding/integrations/status', {
            headers: { 'Accept': 'application/json' }
        });
        const data = await res.json();
        if (data.success) {
            renderSmtpStatus(data.smtp);
            renderLinkedInStatus(data.linkedin);
        }
    } catch (err) {
        console.error('[Integrations] Error loading statuses:', err);
    }
}

function renderSmtpStatus(smtp) {
    const badge = document.getElementById('smtp-status-badge');
    if (!badge) return;

    if (smtp && smtp.configured && smtp.connection_status === 'CONNECTED') {
        isSmtpConfigured = true;
        badge.textContent = 'CONNECTED';
        badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-tertiary-fixed text-tertiary';
        
        // Populate inputs if blank
        if (smtp.email_address && !document.getElementById('smtp-email').value) {
            document.getElementById('smtp-email').value = smtp.email_address;
        }
        if (smtp.smtp_host && !document.getElementById('smtp-host').value) {
            document.getElementById('smtp-host').value = smtp.smtp_host;
        }
        if (smtp.smtp_port && !document.getElementById('smtp-port').value) {
            document.getElementById('smtp-port').value = smtp.smtp_port;
        }
        if (smtp.smtp_username && !document.getElementById('smtp-username').value) {
            document.getElementById('smtp-username').value = smtp.smtp_username;
        }
    } else {
        isSmtpConfigured = false;
        badge.textContent = 'PENDING CONFIGURATION';
        badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-surface-container text-on-surface-variant';
    }
}

function renderLinkedInStatus(li) {
    const badge = document.getElementById('linkedin-status-badge');
    const feedbackBox = document.getElementById('linkedin-feedback-box');
    if (!badge) return;

    if (li && li.connected) {
        isLinkedInConnected = true;
        badge.textContent = 'CONNECTED & VERIFIED';
        badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-tertiary-fixed text-tertiary';

        if (feedbackBox) {
            feedbackBox.classList.remove('hidden');
            feedbackBox.className = 'p-3 rounded-lg border border-tertiary/40 bg-tertiary-fixed/30 text-xs flex flex-col gap-0.5 text-on-surface';
            feedbackBox.innerHTML = `
                <div class="flex items-center gap-1.5 font-bold text-tertiary">
                    <span class="material-symbols-outlined text-[16px]">verified</span>
                    <span>Active LinkedIn Session Verified</span>
                </div>
                <span class="text-[11px] text-on-surface-variant font-mono">Last verified: ${new Date(li.last_verified_at || Date.now()).toLocaleTimeString()}</span>
            `;
        }
    } else {
        isLinkedInConnected = false;
        badge.textContent = 'NOT CONNECTED';
        badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-surface-container text-on-surface-variant';
    }
}

// ====================================================================
// 2. SMTP EMAIL CONFIGURATION & TESTING
// ====================================================================

function setupSmtpAutoDetection() {
    const emailInput = document.getElementById('smtp-email');
    if (!emailInput) return;

    emailInput.addEventListener('blur', async () => {
        const email = emailInput.value.trim().toLowerCase();
        if (!email || !email.includes('@')) return;

        try {
            const res = await fetch('/api/bulk-email/detect-provider', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ email_address: email })
            });
            const data = await res.json();
            if (data.success && data.data) {
                const d = data.data;
                const hostInput = document.getElementById('smtp-host');
                const portInput = document.getElementById('smtp-port');
                const hint = document.getElementById('smtp-provider-hint');

                if (d.host && hostInput && !hostInput.value) {
                    hostInput.value = d.host;
                }
                if (d.port && portInput) {
                    portInput.value = d.port;
                }
                if (hint) {
                    hint.textContent = `Detected Provider: ${d.name || d.provider} (${d.host}:${d.port})`;
                    hint.classList.remove('hidden');
                }
            }
        } catch (e) {
            console.debug('[SMTP Detect] Auto detect skipped:', e);
        }
    });

    const form = document.getElementById('smtp-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveSmtpAccount();
        });
    }
}

async function testSmtpConnection() {
    const btn = document.getElementById('btn-test-smtp');
    const resultBox = document.getElementById('smtp-test-result');
    const email = document.getElementById('smtp-email').value.trim();
    const host = document.getElementById('smtp-host').value.trim();
    const port = parseInt(document.getElementById('smtp-port').value.trim(), 10) || 587;
    const username = document.getElementById('smtp-username').value.trim() || email;
    const password = document.getElementById('smtp-password').value;
    const useTls = document.getElementById('smtp-tls').checked;
    const useSsl = document.getElementById('smtp-ssl').checked;

    if (!email || !host || !password) {
        alert('Please fill in Email, Host, and Password to test connection.');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span><span>Testing...</span>';
    resultBox.classList.remove('hidden');
    resultBox.className = 'p-space-md rounded-lg text-xs bg-surface-container text-on-surface border border-border-default';
    resultBox.innerHTML = 'Connecting to SMTP server and validating credentials...';

    try {
        const res = await fetch('/api/bulk-email/accounts/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                email_address: email,
                smtp_host: host,
                smtp_port: port,
                smtp_username: username,
                smtp_password: password,
                use_tls: useTls,
                use_ssl: useSsl
            })
        });

        const data = await res.json();
        if (data.success) {
            resultBox.className = 'p-space-md rounded-lg text-xs bg-tertiary-fixed/30 text-tertiary border border-tertiary/40 font-medium';
            resultBox.innerHTML = `<div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[16px]">check_circle</span><span>${data.message || 'SMTP Authentication Verified!'}</span></div>`;
        } else {
            resultBox.className = 'p-space-md rounded-lg text-xs bg-error-container/40 text-error border border-error/40';
            resultBox.innerHTML = `<div class="flex items-center gap-1.5 font-bold"><span class="material-symbols-outlined text-[16px]">error</span><span>Connection Test Failed:</span></div><div class="mt-1">${data.error || 'Authentication rejected.'}</div>`;
        }
    } catch (err) {
        resultBox.className = 'p-space-md rounded-lg text-xs bg-error-container/40 text-error border border-error/40';
        resultBox.innerHTML = `Network error: ${err.message}`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">network_check</span><span>Test Connection</span>';
    }
}

async function saveSmtpAccount() {
    const btn = document.getElementById('btn-save-smtp');
    const resultBox = document.getElementById('smtp-test-result');
    const email = document.getElementById('smtp-email').value.trim();
    const host = document.getElementById('smtp-host').value.trim();
    const port = parseInt(document.getElementById('smtp-port').value.trim(), 10) || 587;
    const username = document.getElementById('smtp-username').value.trim() || email;
    const password = document.getElementById('smtp-password').value;
    const useTls = document.getElementById('smtp-tls').checked;
    const useSsl = document.getElementById('smtp-ssl').checked;

    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span><span>Encrypting & Saving...</span>';

    try {
        const res = await fetch('/api/bulk-email/accounts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                email_address: email,
                sender_name: email.split('@')[0],
                smtp_host: host,
                smtp_port: port,
                smtp_username: username,
                smtp_password: password,
                use_tls: useTls,
                use_ssl: useSsl,
                is_primary: true
            })
        });

        const data = await res.json();
        if (data.success) {
            isSmtpConfigured = true;
            renderSmtpStatus({ configured: true, connection_status: 'CONNECTED', email_address: email, smtp_host: host });
            resultBox.classList.remove('hidden');
            resultBox.className = 'p-space-md rounded-lg text-xs bg-tertiary-fixed/30 text-tertiary border border-tertiary/40 font-semibold';
            resultBox.innerHTML = 'Account encrypted with AES-256-GCM and saved successfully!';
            document.getElementById('smtp-password').value = '';
        } else {
            resultBox.classList.remove('hidden');
            resultBox.className = 'p-space-md rounded-lg text-xs bg-error-container/40 text-error border border-error/40';
            resultBox.innerHTML = `Save failed: ${data.error || 'Check credentials'}`;
        }
    } catch (err) {
        resultBox.classList.remove('hidden');
        resultBox.className = 'p-space-md rounded-lg text-xs bg-error-container/40 text-error border border-error/40';
        resultBox.innerHTML = `Network error: ${err.message}`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">save</span><span>Save & Connect SMTP</span>';
    }
}


// ====================================================================
// 3. CHROME EXTENSION DETECTION & HANDSHAKE
// ====================================================================

function setupExtensionMessageListeners() {
    window.addEventListener('message', (event) => {
        if (event.source !== window || !event.data || typeof event.data !== 'object') return;

        const { type } = event.data;

        if (type === 'FAMEWEB_EXT_PONG' || type === 'FAMEWEB_EXTENSION_READY') {
            handleExtensionFound(event.data.version || '1.0.0');
        }

        if (type === 'FAMEWEB_EXT_VERIFY_RESPONSE') {
            handleExtensionVerificationResponse(event.data);
        }
    });
}

function detectExtension(isManualTrigger = false) {
    const icon = document.getElementById('ext-status-icon');
    const text = document.getElementById('ext-status-text');
    const guide = document.getElementById('ext-install-guide');

    // 1. Check DOM flag set by content script
    if (document.documentElement.dataset.famewebExtensionInstalled === 'true') {
        handleExtensionFound('1.0.0');
        return;
    }

    // 2. Dispatch ping handshake to content_fameweb.js
    const pingId = 'ping_' + Date.now();
    window.postMessage({ type: 'FAMEWEB_EXT_PING', requestId: pingId }, '*');

    // Timeout check
    setTimeout(() => {
        if (!isExtensionDetected) {
            icon.textContent = 'warning';
            icon.className = 'material-symbols-outlined text-warning text-[20px]';
            text.textContent = 'Extension not detected in this browser window';
            text.className = 'text-[11px] text-warning font-mono font-semibold';
            if (guide) guide.classList.remove('hidden');
            if (isManualTrigger) {
                alert('FameWeb Extension not detected. Please follow the instructions to load the unpacked extension in chrome://extensions.');
            }
        }
    }, 400);
}

function handleExtensionFound(version) {
    isExtensionDetected = true;
    const icon = document.getElementById('ext-status-icon');
    const text = document.getElementById('ext-status-text');
    const guide = document.getElementById('ext-install-guide');

    if (icon) {
        icon.textContent = 'check_circle';
        icon.className = 'material-symbols-outlined text-tertiary text-[20px]';
    }
    if (text) {
        text.textContent = `Extension Active (v${version}) & Ready`;
        text.className = 'text-[11px] text-tertiary font-mono font-semibold';
    }
    if (guide) {
        guide.classList.add('hidden');
    }
}

function openLinkedInTab() {
    window.open('https://www.linkedin.com', '_blank');
}

function requestExtensionVerification() {
    if (!isExtensionDetected) {
        detectExtension(true);
        return;
    }

    const btn = document.getElementById('btn-verify-linkedin');
    const feedbackBox = document.getElementById('linkedin-feedback-box');

    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span><span>Verifying...</span>';

    feedbackBox.classList.remove('hidden');
    feedbackBox.className = 'p-3 rounded-lg border border-border-default bg-surface-container-low text-xs text-on-surface';
    feedbackBox.textContent = 'Querying extension for active LinkedIn session...';

    // Send verification request via bridge
    const reqId = 'ver_' + Date.now();
    window.postMessage({ type: 'FAMEWEB_EXT_VERIFY_REQUEST', requestId: reqId }, '*');

    // Guard timeout
    setTimeout(() => {
        if (btn.disabled) {
            btn.disabled = false;
            btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">verified</span><span>2. Verify Session</span>';
        }
    }, 6000);
}

async function handleExtensionVerificationResponse(data) {
    const btn = document.getElementById('btn-verify-linkedin');
    const feedbackBox = document.getElementById('linkedin-feedback-box');

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">verified</span><span>2. Verify Session</span>';
    }

    if (data.status === 'CONNECTED' && data.authenticated) {
        // Send verified status signal to backend (ZERO raw cookies transmitted)
        try {
            const res = await fetch('/api/onboarding/linkedin/verify-extension-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    status: 'CONNECTED',
                    authenticated: true
                })
            });
            const backData = await res.json();
            if (backData.success) {
                renderLinkedInStatus({ connected: true, last_verified_at: backData.last_verified_at });
            } else {
                feedbackBox.className = 'p-3 rounded-lg border border-error/40 bg-error-container/30 text-xs text-error font-medium';
                feedbackBox.textContent = `Backend update error: ${backData.message}`;
            }
        } catch (e) {
            feedbackBox.className = 'p-3 rounded-lg border border-error/40 bg-error-container/30 text-xs text-error';
            feedbackBox.textContent = `Network error: ${e.message}`;
        }
    } else {
        renderLinkedInStatus({ connected: false });
        feedbackBox.className = 'p-3 rounded-lg border border-warning/40 bg-warning-container/30 text-xs text-warning-content font-medium';
        feedbackBox.innerHTML = `
            <div class="font-bold">LinkedIn Session Inactive</div>
            <div class="mt-0.5">Please click "Open LinkedIn" in step 1, log into your account, and then click "Verify Session" again.</div>
        `;
    }
}


// ====================================================================
// 4. STEP CONTINUATION
// ====================================================================

function continueToNextStep() {
    // Both or either can proceed to dashboard/company step
    window.location.href = '/dashboard';
}

