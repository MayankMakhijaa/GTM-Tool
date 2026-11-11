document.addEventListener('DOMContentLoaded', () => {
    const btnGenerate = /** @type {HTMLButtonElement | null} */ (document.getElementById('generate-suggestions-btn'));
    const btnImport = /** @type {HTMLButtonElement | null} */ (document.getElementById('btn-import-profile'));
    const btnRecheckExt = /** @type {HTMLButtonElement | null} */ (document.getElementById('btn-recheck-ext'));
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');

    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    const showToast = function(message) {
        if (!toast || !toastMessage) return alert(message);
        toastMessage.innerText = message;
        toast.classList.remove('translate-y-20', 'opacity-0', 'pointer-events-none');
        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0', 'pointer-events-none');
        }, 3200);
    };
    window['showToast'] = showToast;

    window['copyToClipboard'] = function(elementId, btn) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const textToCopy = el.innerText.replace(/^"|"$/g, '');
        navigator.clipboard.writeText(textToCopy).then(() => {
            showToast('Copied to clipboard');
            const originalContent = btn.innerHTML;
            btn.innerHTML = '<span class="material-symbols-outlined text-[16px] text-tertiary">done</span><span>Copied</span>';
            setTimeout(() => {
                btn.innerHTML = originalContent;
            }, 2000);
        }).catch(() => {
            showToast('Failed to copy');
        });
    };

    // =========================================================================
    // EXTENSION DETECTION & PROFILE IMPORT HANDLERS
    // =========================================================================
    let isExtensionDetected = false;

    function updateExtensionStatus(detected, version = '1.0.0') {
        isExtensionDetected = detected;
        const extIcon = document.getElementById('ext-status-icon');
        const extText = document.getElementById('ext-status-text');
        if (!extIcon || !extText) return;

        if (detected) {
            extIcon.textContent = 'check_circle';
            extIcon.className = 'material-symbols-outlined text-[18px] text-tertiary';
            extText.textContent = `Extension Active (v${version})`;
            extText.className = 'text-xs font-semibold text-tertiary';
        } else {
            extIcon.textContent = 'warning';
            extIcon.className = 'material-symbols-outlined text-[18px] text-amber-500';
            extText.textContent = 'Extension Not Detected';
            extText.className = 'text-xs font-semibold text-amber-600';
        }
    }

    function pingExtension() {
        if (document.documentElement.dataset.famewebExtensionInstalled === 'true') {
            updateExtensionStatus(true);
            return;
        }
        window.postMessage({ type: 'FAMEWEB_EXT_PING', requestId: 'ping_' + Date.now() }, '*');
        setTimeout(() => {
            if (!isExtensionDetected) {
                updateExtensionStatus(false);
            }
        }, 500);
    }

    window.addEventListener('message', (event) => {
        if (event.source !== window || !event.data || typeof event.data !== 'object') return;
        const { type } = event.data;

        if (type === 'FAMEWEB_EXT_PONG' || type === 'FAMEWEB_EXTENSION_READY') {
            updateExtensionStatus(true, event.data.version || '1.0.0');
        }
    });

    if (btnRecheckExt) {
        btnRecheckExt.addEventListener('click', (e) => {
            e.preventDefault();
            pingExtension();
            showToast('Checking for FameWeb extension...');
        });
    }

    // Initial check
    pingExtension();

    function showImportFeedback(type, title, details = [], actionHtml = '') {
        const box = document.getElementById('import-feedback-box');
        if (!box) return;

        box.classList.remove('hidden', 'bg-emerald-50', 'border-emerald-200', 'text-emerald-900',
                             'bg-amber-50', 'border-amber-200', 'text-amber-900',
                             'bg-rose-50', 'border-rose-200', 'text-rose-900',
                             'bg-blue-50', 'border-blue-200', 'text-blue-900');

        let styleClasses = 'bg-surface-container border border-border-default text-on-surface';
        let iconName = 'info';
        let iconColor = 'text-outline';

        if (type === 'success') {
            styleClasses = 'bg-emerald-50 border border-emerald-300 text-emerald-950';
            iconName = 'check_circle';
            iconColor = 'text-emerald-600';
        } else if (type === 'warning') {
            styleClasses = 'bg-amber-50 border border-amber-300 text-amber-950';
            iconName = 'warning';
            iconColor = 'text-amber-600';
        } else if (type === 'error') {
            styleClasses = 'bg-rose-50 border border-rose-300 text-rose-950';
            iconName = 'error';
            iconColor = 'text-rose-600';
        } else if (type === 'info' || type === 'loading') {
            styleClasses = 'bg-blue-50 border border-blue-300 text-blue-950';
            iconName = type === 'loading' ? 'hourglass_top' : 'info';
            iconColor = 'text-blue-600';
        }

        box.className = `p-3 rounded-lg text-xs flex flex-col gap-1.5 transition-all ${styleClasses}`;

        let detailsHtml = '';
        if (details && details.length > 0) {
            detailsHtml = `<ul class="list-disc list-inside space-y-0.5 text-[11px] opacity-90">
                ${details.map(d => `<li>${d}</li>`).join('')}
            </ul>`;
        }

        box.innerHTML = `
            <div class="flex items-start gap-1.5 font-semibold">
                <span class="material-symbols-outlined text-[16px] shrink-0 mt-0.5 ${iconColor}">${iconName}</span>
                <span class="flex-1">${title}</span>
            </div>
            ${detailsHtml}
            ${actionHtml ? `<div class="mt-1">${actionHtml}</div>` : ''}
        `;
    }

    function checkActiveLinkedInTab() {
        return new Promise((resolve) => {
            const reqId = 'tab_' + Date.now();
            console.log(`[Profile Import] Request dispatched: ${reqId} (CHECK_TAB)`);
            /** @type {number | undefined} */
            let timer = undefined;

            const handler = (event) => {
                if (event.source !== window || !event.data || typeof event.data !== 'object') return;
                if (event.data.type === 'FAMEWEB_EXT_CHECK_TAB_RESPONSE' && event.data.requestId === reqId) {
                    if (timer !== undefined) clearTimeout(timer);
                    window.removeEventListener('message', handler);
                    console.log(`[Profile Import] Response received by page: ${reqId}`, {
                        success: event.data.success,
                        status: event.data.status,
                        tabId: event.data.tabId
                    });
                    console.log(`[Profile Import] Promise resolved: ${reqId}`);
                    resolve(event.data);
                }
            };

            window.addEventListener('message', handler);
            window.postMessage({ type: 'FAMEWEB_EXT_CHECK_TAB_REQUEST', requestId: reqId }, '*');

            timer = setTimeout(() => {
                window.removeEventListener('message', handler);
                console.warn(`[Profile Import] Timeout reached: ${reqId} (CHECK_TAB)`);
                resolve({ success: false, error: 'TIMEOUT', message: 'Tab check timed out.' });
            }, 6000);
        });
    }

    /**
     * @param {string | null} [targetProfileUrl]
     */
    function requestProfileExtraction(targetProfileUrl = null) {
        return new Promise((resolve) => {
            const reqId = 'import_' + Date.now();
            console.log(`[Profile Import] Request dispatched: ${reqId} (EXTRACT_PROFILE)`);
            /** @type {number | undefined} */
            let timer = undefined;

            const handler = (event) => {
                if (event.source !== window || !event.data || typeof event.data !== 'object') return;
                if (event.data.type === 'FAMEWEB_EXT_IMPORT_RESPONSE' && event.data.requestId === reqId) {
                    if (timer !== undefined) clearTimeout(timer);
                    window.removeEventListener('message', handler);
                    console.log(`[Profile Import] Response received by page: ${reqId}`, {
                        success: event.data.success,
                        hasData: !!event.data.data,
                        error: event.data.error
                    });
                    console.log(`[Profile Import] Promise resolved: ${reqId}`);
                    resolve(event.data);
                }
            };

            window.addEventListener('message', handler);
            window.postMessage({
                type: 'FAMEWEB_EXT_IMPORT_REQUEST',
                requestId: reqId,
                targetProfileUrl: targetProfileUrl || null
            }, '*');

            timer = setTimeout(() => {
                window.removeEventListener('message', handler);
                console.warn(`[Profile Import] Timeout reached: ${reqId} (EXTRACT_PROFILE)`);
                resolve({ success: false, error: 'TIMEOUT', message: 'Profile extraction timed out. Please check that your LinkedIn profile tab is open.' });
            }, 75000);
        });
    }

    if (btnImport) {
        btnImport.addEventListener('click', async () => {
            if (!isExtensionDetected) {
                showImportFeedback(
                    'error',
                    'FameWeb Chrome Extension is not active',
                    [
                        'Load the extension from linkedin_extension/ via chrome://extensions.',
                        'Enable "Developer mode" and click "Load unpacked".',
                        'Refresh this page once loaded.'
                    ]
                );
                return;
            }

            const importBtnText = document.getElementById('import-btn-text');
            const originalText = importBtnText ? importBtnText.innerText : 'Import My LinkedIn Profile';

            btnImport.disabled = true;

            try {
                // Step 1: Finding your LinkedIn session
                if (importBtnText) importBtnText.innerText = 'Finding LinkedIn...';
                showImportFeedback('loading', 'Finding your LinkedIn session...');

                const tabStatus = await checkActiveLinkedInTab();

                if (!tabStatus.success) {
                    if (tabStatus.error === 'NO_LINKEDIN_TAB' || tabStatus.error === 'NO_LINKEDIN_TABS') {
                        showImportFeedback(
                            'warning',
                            'LinkedIn is not open in your browser',
                            [
                                'Please open LinkedIn in a browser tab and make sure you are signed in.',
                                'Once LinkedIn is open, click Import My LinkedIn Profile again.'
                            ],
                            `<a href="https://www.linkedin.com" target="_blank" class="inline-flex items-center gap-1 font-semibold text-primary underline">Open LinkedIn in New Tab &rarr;</a>`
                        );
                    } else {
                        showImportFeedback(
                            'warning',
                            'Could not access LinkedIn tab',
                            [
                                tabStatus.message || 'Please ensure you have an active LinkedIn tab open and try again.'
                            ]
                        );
                    }
                    return;
                }

                // Step 2 & 3: Locating own profile & opening it
                if (importBtnText) importBtnText.innerText = 'Locating Profile...';
                showImportFeedback('loading', 'Locating your own profile...');

                // Check previously saved profile URL if available
                const savedUrlEl = document.querySelector('[data-saved-profile-url]');
                const savedProfileUrl = savedUrlEl ? (savedUrlEl.getAttribute('data-saved-profile-url') || null) : null;

                // Step 4: Automatically navigate & extract profile DOM
                if (importBtnText) importBtnText.innerText = 'Extracting Profile...';
                showImportFeedback('loading', 'Opening your LinkedIn profile and extracting visible information...');

                const extResult = await requestProfileExtraction(savedProfileUrl);

                if (!extResult.success || !extResult.data) {
                    if (extResult.error === 'NOT_LOGGED_IN' || extResult.error === 'SESSION_EXPIRED') {
                        showImportFeedback(
                            'warning',
                            'LinkedIn session expired or not signed in',
                            [
                                'Your LinkedIn account needs to be signed in.',
                                'Please open LinkedIn, log in to your account, and try again.'
                            ],
                            `<a href="https://www.linkedin.com/login" target="_blank" class="inline-flex items-center gap-1 font-semibold text-primary underline">Log in to LinkedIn &rarr;</a>`
                        );
                    } else if (extResult.error === 'CHALLENGE_DETECTED') {
                        showImportFeedback(
                            'warning',
                            'Security Verification Challenge Detected',
                            [
                                'LinkedIn has displayed a security or human verification checkpoint.',
                                'Please switch to your LinkedIn tab to complete the challenge, then click Import again.'
                            ]
                        );
                    } else {
                        showImportFeedback(
                            'error',
                            'Unable to automatically extract profile',
                            [
                                extResult.message || 'Could not identify or extract profile information from LinkedIn DOM.',
                                'Ensure your LinkedIn profile is accessible and retry.'
                            ]
                        );
                    }
                    return;
                }

                const extracted = extResult.data;

                // Step 5: Importing your profile into FameWeb
                if (importBtnText) importBtnText.innerText = 'Importing to FameWeb...';
                showImportFeedback('loading', 'Importing your profile into FameWeb...');

                const res = await fetch('/api/profile-optimization/import-extension-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        profile: extracted,
                        metadata: extResult.metadata || {}
                    })
                });

                const data = await res.json();

                if (res.ok && data.success) {
                    const sections = (data.sections_imported || []).join(', ');
                    const warnings = (data.warnings || []).concat(extracted._warnings || []);
                    const importedCount = (data.sections_imported || []).length;
                    const hasSubstantiveContent = importedCount > 1 || (data.experience_count > 0 || data.skills_count > 0 || data.data?.about);

                    // 1. Immediately update DOM profile preview without reloading
                    const nameEl = document.getElementById('profile-summary-name');
                    if (nameEl) nameEl.textContent = data.data?.name || extracted.name || 'Connected Profile';

                    const posEl = document.getElementById('profile-summary-position');
                    if (posEl) posEl.textContent = data.data?.current_position || extracted.current_position || extracted.headline || 'Position updated';

                    const locEl = document.getElementById('profile-summary-location');
                    if (locEl) locEl.textContent = data.data?.location || extracted.location || 'Location updated';

                    const hlEl = document.getElementById('profile-summary-headline');
                    if (hlEl) hlEl.textContent = data.data?.headline || extracted.headline || 'No headline available.';

                    const photoEl = /** @type {HTMLImageElement | null} */ (document.getElementById('profile-summary-photo'));
                    const newPhotoUrl = extracted.profile_photo_url || data.data?.profile_photo_url;
                    if (photoEl && newPhotoUrl) {
                        photoEl.src = newPhotoUrl;
                    }

                    // 2. Display honest in-page import confirmation
                    if (hasSubstantiveContent) {
                        showImportFeedback(
                            'success',
                            `LinkedIn profile imported successfully: ${data.data?.name || extracted.name}`,
                            [
                                `Headline: ${data.data?.headline || extracted.headline || 'Not specified'}`,
                                `Sections saved: ${sections || 'Name, Headline'}`,
                                `Experience: ${data.experience_count || 0} roles | Skills: ${data.skills_count || 0} skills | Education: ${data.education_count || 0} entries`,
                                warnings.length > 0 ? `Notes: ${warnings.join('; ')}` : 'Full profile structure imported cleanly.'
                            ],
                            `<div class="flex items-center gap-2 mt-2 pt-1 border-t border-emerald-200">
                                <span class="font-semibold text-emerald-900">Your profile data is saved in FameWeb. Click "Generate Analysis" below to run Gemini optimization.</span>
                             </div>`
                        );
                        showToast('LinkedIn profile imported successfully!');
                    } else {
                        showImportFeedback(
                            'warning',
                            `Partial Profile Import: ${data.data?.name || extracted.name}`,
                            [
                                `Only basic header information (${sections || 'Name'}) could be found on the open page.`,
                                `Experience: 0 roles | Skills: 0 skills | About: Not found`,
                                'Tip: Open your LinkedIn tab, scroll down once so LinkedIn renders your Experience & Skills sections, then click Re-import below.'
                            ],
                            `<div class="flex items-center gap-2 mt-2 pt-1 border-t border-amber-200">
                                <span class="font-semibold text-amber-900">Basic identity saved. For best GTM optimization, scroll your LinkedIn tab and re-import.</span>
                             </div>`
                        );
                        showToast('Profile header saved (partial import)');
                    }

                    // Update button status
                    if (importBtnText) importBtnText.innerText = 'Re-import LinkedIn Profile';
                } else {
                    showImportFeedback(
                        'error',
                        'Server failed to save imported profile',
                        [
                            data.message || data.error || 'Invalid profile payload.'
                        ]
                    );
                }
            } catch (err) {
                const errorMsg = err instanceof Error ? err.message : String(err);
                console.error('[Profile Import] Error:', err);
                showImportFeedback('error', 'Error during profile import', [errorMsg]);
            } finally {
                btnImport.disabled = false;
                if (importBtnText) importBtnText.innerText = originalText;
            }
        });
    }

    function showSessionExpiredNotice(message) {
        let reconnectContainer = document.getElementById('session-reconnect-container');
        if (!reconnectContainer && btnGenerate && btnGenerate.parentNode) {
            reconnectContainer = document.createElement('div');
            reconnectContainer.id = 'session-reconnect-container';
            btnGenerate.parentNode.insertBefore(reconnectContainer, btnGenerate);
        }
        if (!reconnectContainer) return;

        reconnectContainer.className = 'flex flex-col gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm mb-2';
        reconnectContainer.innerHTML = `
            <div class="flex items-start gap-2 text-amber-900">
                <span class="material-symbols-outlined text-[18px] shrink-0 mt-0.5 text-amber-700">warning</span>
                <div class="flex-1 font-medium leading-snug">
                    ${message || 'LinkedIn profile data missing. Please import your profile using the button above.'}
                </div>
            </div>
            <button id="reconnect-linkedin-btn" type="button" class="mt-1 w-full flex items-center justify-center gap-2 px-3 py-2 bg-[#0a66c2] hover:bg-[#004182] text-white rounded-md text-xs font-semibold transition-all shadow-sm cursor-pointer">
                <span class="material-symbols-outlined text-[16px]">download_for_offline</span>
                <span id="reconnect-btn-text">Import Profile Now</span>
            </button>
        `;
        reconnectContainer.classList.remove('hidden');

        const reconnectBtn = document.getElementById('reconnect-linkedin-btn');
        if (reconnectBtn) {
            reconnectBtn.addEventListener('click', () => {
                if (btnImport) btnImport.click();
            });
        }
    }

    if (btnGenerate) {
        btnGenerate.addEventListener('click', async () => {
            const original = btnGenerate.innerHTML;
            btnGenerate.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span><span>Analyzing your profile with Gemini...</span>';
            btnGenerate.disabled = true;

            // Hide any previous reconnect notice while retrying
            const existingNotice = document.getElementById('session-reconnect-container');
            if (existingNotice) existingNotice.classList.add('hidden');

            try {
                const res = await fetch('/api/optimize-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({}) // Backend pulls data from DB
                });

                const data = await res.json();
                if (data.success) {
                    showToast('Analysis complete');
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else if (data.error === 'PROFILE_DATA_EMPTY' || data.error === 'NO_LINKEDIN_CREDENTIALS') {
                    showImportFeedback(
                        'warning',
                        'Profile Data Required',
                        [
                            'No profile content found in FameWeb yet.',
                            'Open your LinkedIn profile tab and click "Import My LinkedIn Profile" above.'
                        ]
                    );
                    btnGenerate.disabled = false;
                    btnGenerate.innerHTML = original;
                } else if (data.error === 'SESSION_EXPIRED' || data.error === 'SESSION_INVALID') {
                    showSessionExpiredNotice(data.message || 'LinkedIn session expired. Please import your profile.');
                    btnGenerate.disabled = false;
                    btnGenerate.innerHTML = original;
                } else {
                    const errMsg = data.message || data.error || 'Failed to analyze profile';
                    alert('Unable to analyze profile: ' + errMsg);
                    btnGenerate.disabled = false;
                    btnGenerate.innerHTML = original;
                }
            } catch (err) {
                const errorMsg = err instanceof Error ? err.message : String(err);
                alert('Unable to analyze profile: ' + errorMsg);
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = original;
            }
        });
    }

    const exportBtn = document.getElementById('export-summary-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            showToast('Generating executive brief summary...');
        });
    }
});
