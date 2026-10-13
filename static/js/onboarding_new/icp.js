document.addEventListener('DOMContentLoaded', async () => {
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const btnSubmit = document.getElementById('btn-submit-icp');
    const btnAccept = document.getElementById('btn-accept-parameters');
    const btnFinalize = document.getElementById('btn-finalize-parameters') || document.getElementById('btn-proceed-from-preview');
    const btnEdit = document.getElementById('btn-edit-questionnaire');

    // Helper to get text from chips
    const getChipsText = (containerId) => {
        const container = document.getElementById(containerId);
        if (!container) return "";
        const chips = Array.from(container.querySelectorAll('.chip-text')).map(el => el.textContent.trim());
        return chips.join(', ');
    };

    // Helper to handle chip removal
    const attachRemoveListeners = (containerId) => {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.remove-chip');
            if (removeBtn) {
                removeBtn.closest('.chip-item').remove();
            }
        });
    };

    // Helper to add new chip
    const createChipElement = (text, typeClass, iconHtml = '') => {
        // Different styling based on type
        // This maps exactly to the UI styling in icp.html
        let classes = "";
        let dot = "";
        
        if (typeClass === 'target_customer' || typeClass === 'industry') {
            classes = "chip-item inline-flex items-center gap-1 px-space-sm py-1 bg-surface-container-lowest text-primary rounded font-label-sm text-label-sm shadow-sm";
        } else if (typeClass === 'location') {
            classes = "chip-item inline-flex items-center gap-1 px-space-sm py-1 bg-surface-container-lowest text-primary rounded font-label-sm text-label-sm shadow-sm";
        } else if (typeClass === 'roles') {
            classes = "chip-item inline-flex items-center gap-1.5 px-space-md py-1.5 bg-surface-container-lowest text-on-surface font-label-md text-label-md rounded shadow-sm";
            dot = '<span class="w-2 h-2 rounded-full bg-primary"></span>';
        } else if (typeClass === 'keywords') {
            classes = "chip-item inline-flex items-center gap-1 px-2.5 py-1 bg-tertiary-fixed text-on-tertiary-fixed rounded font-code-sm text-code-sm";
        } else if (typeClass === 'exclusions') {
            classes = "chip-item inline-flex items-center gap-1 px-2.5 py-1 bg-error-container text-on-error-container rounded font-label-sm text-label-sm";
            iconHtml = '<span class="material-symbols-outlined text-[14px]">block</span>';
        }

        const span = document.createElement('span');
        span.className = classes;
        span.innerHTML = `
            ${dot}
            ${iconHtml}
            <span class="chip-text">${text}</span>
            <button class="remove-chip material-symbols-outlined text-[16px] text-outline hover:text-error" type="button">close</button>
        `;
        return span;
    };

    const setupTagInput = (inputId, btnId, containerId, typeClass, iconHtml = '') => {
        const input = document.getElementById(inputId);
        const btn = document.getElementById(btnId);
        const container = document.getElementById(containerId);
        
        if (btn && input) {
            btn.addEventListener('click', () => {
                input.classList.remove('hidden');
                input.focus();
            });
        }
        
        if (input && container) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const val = input.value.trim();
                    if (!val) return;
                    
                    // check duplicates
                    const existing = Array.from(container.querySelectorAll('.chip-text')).map(el => el.textContent.trim().toLowerCase());
                    if (existing.includes(val.toLowerCase())) {
                        input.value = '';
                        return;
                    }
                    
                    const newChip = createChipElement(val, typeClass, iconHtml);
                    // Insert before the input
                    container.insertBefore(newChip, input);
                    input.value = '';
                }
            });
        }
        
        attachRemoveListeners(containerId);
    };

    // Setup interactions
    setupTagInput('target-customer-input', null, 'target-customer-container', 'target_customer');
    setupTagInput('industry-input', 'add-industry-btn', 'industry-container', 'industry');
    setupTagInput('location-input', 'add-location-btn', 'location-container', 'location', '<span class="material-symbols-outlined text-[14px]">public</span>');
    setupTagInput('roles-input', 'add-role-btn', 'roles-container', 'roles');
    setupTagInput('keywords-input', 'add-keyword-btn', 'keywords-container', 'keywords');
    setupTagInput('exclusions-input', 'add-exclusion-btn', 'exclusions-container', 'exclusions');

    // Revenue custom range handling
    const revSelect = document.getElementById('icp-revenue');
    const customRevContainer = document.getElementById('custom-revenue-container');
    const customRevInput = document.getElementById('custom-revenue-input');
    
    if (revSelect) {
        revSelect.addEventListener('change', () => {
            if (revSelect.value === 'custom') {
                customRevContainer.classList.remove('hidden');
                customRevInput.focus();
            } else {
                customRevContainer.classList.add('hidden');
            }
        });
    }

    // Tone selection
    const toneItems = document.querySelectorAll('.tone-item');
    toneItems.forEach(item => {
        item.addEventListener('click', () => {
            // Uncheck all
            toneItems.forEach(t => {
                t.classList.remove('border-primary');
                t.classList.add('border-transparent');
                t.querySelector('.tone-icon').textContent = 'radio_button_unchecked';
                t.querySelector('.tone-icon').classList.remove('text-primary');
                t.querySelector('.tone-icon').classList.add('text-outline');
                t.querySelector('input').checked = false;
            });
            // Check clicked
            item.classList.add('border-primary');
            item.classList.remove('border-transparent');
            item.querySelector('.tone-icon').textContent = 'radio_button_checked';
            item.querySelector('.tone-icon').classList.add('text-primary');
            item.querySelector('.tone-icon').classList.remove('text-outline');
            item.querySelector('input').checked = true;
        });
    });

    const collectPayload = () => {
            const targetCustomer = getChipsText('target-customer-container');
            
            let rev = "";
            if (revSelect && revSelect.value === 'custom') {
                rev = JSON.stringify({
                    label: "Custom",
                    range: customRevInput ? customRevInput.value.trim() : ""
                });
            } else if (revSelect) {
                rev = revSelect.value;
            }

            const sizeContainer = document.getElementById('headcount-container');
            const activeSizePills = sizeContainer ? Array.from(sizeContainer.querySelectorAll('.size-pill.active')).map(p => p.textContent.trim().replace('check', '').trim()) : [];
            const size = activeSizePills.join(', ');

            const ind = getChipsText('industry-container');
            const loc = getChipsText('location-container');
            const roles = getChipsText('roles-container');
            const keywords = getChipsText('keywords-container');
            const exclusions = getChipsText('exclusions-container');
            
            const signals = {};
            const signalItems = document.querySelectorAll('.signal-item');
            signalItems.forEach(item => {
                const checkbox = item.querySelector('.signal-checkbox');
                if (checkbox && checkbox.checked) {
                    const key = item.getAttribute('data-signal-key');
                    const metaEl = item.querySelector('.signal-meta');
                    const metaKey = metaEl ? metaEl.getAttribute('data-meta-key') : 'value';
                    const metaVal = metaEl ? metaEl.textContent.trim() : true;
                    
                    signals[key] = {
                        enabled: true,
                        [metaKey]: metaVal
                    };
                }
            });

            const activeTone = document.querySelector('input[name="tone"]:checked');
            const tone = activeTone ? activeTone.value : 'FORMAL';

            return {
                target_customer: targetCustomer,
                company_size: size,
                revenue_range: rev,
                target_jobs_roles: roles,
                industry: ind,
                location: loc,
                keywords: keywords,
                exclusions: exclusions,
                signals: signals,
                tone: tone
            };
        };

        const submitICP = async (options = {}) => {
            const payload = collectPayload();
            const activeBtn = options.button || btnSubmit;
            const originalText = activeBtn ? activeBtn.innerHTML : '';
            
            if (activeBtn) {
                activeBtn.disabled = true;
                const loadingText = options.finalize ? 'Finalizing...' : (options.isAccept ? 'Saving...' : 'Generating Report...');
                activeBtn.innerHTML = `<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>${loadingText}</span>`;
            }
            
            try {
                const res = await fetch('/api/onboarding/icp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify(payload)
                });
                
                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || 'Unable to save ICP details.');
                }

                if (options.finalize) {
                    window.location.href = '/dashboard';
                    return;
                }
                
                if (options.isAccept) {
                    if (btnAccept) {
                        btnAccept.innerHTML = '<span class="material-symbols-outlined text-[18px] text-tertiary">check_circle</span><span>Parameters Accepted</span>';
                    }
                    return;
                }
                
                // Show preview
                document.getElementById('questionnaire-view')?.classList.add('hidden');
                document.getElementById('preview-view')?.classList.remove('hidden');
                const btnQuestionnaire = document.getElementById('btn-questionnaire');
                const btnPreview = document.getElementById('btn-preview');
                if (btnQuestionnaire && btnPreview) {
                    btnPreview.classList.add('bg-surface-container-lowest', 'text-primary', 'shadow-sm');
                    btnPreview.classList.remove('text-on-surface-variant');
                    btnQuestionnaire.classList.remove('bg-surface-container-lowest', 'text-primary', 'shadow-sm');
                    btnQuestionnaire.classList.add('text-on-surface-variant');
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
                
            } catch (err) {
                alert(err.message);
            } finally {
                if (activeBtn && !options.finalize) {
                    activeBtn.disabled = false;
                    if (!options.isAccept) {
                        activeBtn.innerHTML = originalText;
                    }
                }
            }
        };

        const saveIcpDraft = async (redirectTarget = null) => {
            const payload = collectPayload();
            try {
                const res = await fetch('/api/onboarding/icp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (redirectTarget) {
                    window.location.href = redirectTarget;
                }
                return data;
            } catch (err) {
                console.error('Error saving ICP draft:', err);
                if (redirectTarget) {
                    window.location.href = redirectTarget;
                }
            }
        };

        // Load existing ICP data from API
        const loadICPData = async () => {
            try {
                const res = await fetch('/api/onboarding/icp');
                if (!res.ok) return;
                const result = await res.json();
                if (!result.success || !result.data) return;

                const data = result.data;
                const populateChips = (containerId, textVal, typeClass, iconHtml = '') => {
                    const container = document.getElementById(containerId);
                    if (!container || !textVal) return;
                    const items = String(textVal).split(',').map(s => s.trim()).filter(Boolean);
                    items.forEach(val => {
                        const existing = Array.from(container.querySelectorAll('.chip-text')).map(el => el.textContent.trim().toLowerCase());
                        if (!existing.includes(val.toLowerCase())) {
                            const newChip = createChipElement(val, typeClass, iconHtml);
                            const input = container.querySelector('input');
                            if (input) {
                                container.insertBefore(newChip, input);
                            } else {
                                container.appendChild(newChip);
                            }
                        }
                    });
                };

                populateChips('target-customer-container', data.target_customer, 'target_customer');
                populateChips('industry-container', data.industry, 'industry');
                populateChips('location-container', data.location, 'location', '<span class="material-symbols-outlined text-[14px]">public</span>');
                populateChips('roles-container', data.target_jobs_roles, 'roles');
                populateChips('keywords-container', data.keywords, 'keywords');
                populateChips('exclusions-container', data.exclusions, 'exclusions');

                if (data.company_size) {
                    const sizeArr = String(data.company_size).split(',').map(s => s.trim());
                    const sizePills = document.querySelectorAll('.size-pill');
                    sizePills.forEach(pill => {
                        const label = pill.textContent.trim().replace('check', '').trim();
                        if (sizeArr.includes(label)) {
                            if (!pill.classList.contains('active')) {
                                pill.click();
                            }
                        }
                    });
                }

                if (data.revenue_range && revSelect) {
                    try {
                        const parsed = JSON.parse(data.revenue_range);
                        if (parsed && parsed.label === 'Custom') {
                            revSelect.value = 'custom';
                            if (customRevContainer) customRevContainer.classList.remove('hidden');
                            if (customRevInput) customRevInput.value = parsed.range || '';
                        }
                    } catch (e) {
                        revSelect.value = data.revenue_range;
                    }
                }

                if (data.tone) {
                    const targetTone = String(data.tone).toUpperCase();
                    toneItems.forEach(item => {
                        const input = item.querySelector('input');
                        if (input && input.value.toUpperCase() === targetTone) {
                            item.click();
                        }
                    });
                }
            } catch (err) {
                console.error('Failed loading ICP data:', err);
            }
        };

        loadICPData();

        if (btnSubmit) {
            btnSubmit.addEventListener('click', (e) => {
                e.preventDefault();
                submitICP({ button: btnSubmit });
            });
        }
        
        if (btnAccept) {
            btnAccept.addEventListener('click', (e) => {
                e.preventDefault();
                submitICP({ button: btnAccept, isAccept: true });
            });
        }

        if (btnFinalize) {
            btnFinalize.addEventListener('click', (e) => {
                e.preventDefault();
                submitICP({ button: btnFinalize, finalize: true });
            });
        }
        
        if (btnEdit) {
            btnEdit.addEventListener('click', () => {
                document.getElementById('preview-view')?.classList.add('hidden');
                document.getElementById('questionnaire-view')?.classList.remove('hidden');
                const btnQuestionnaire = document.getElementById('btn-questionnaire');
                const btnPreview = document.getElementById('btn-preview');
                if (btnQuestionnaire && btnPreview) {
                    btnQuestionnaire.classList.add('bg-surface-container-lowest', 'text-primary', 'shadow-sm');
                    btnQuestionnaire.classList.remove('text-on-surface-variant');
                    btnPreview.classList.remove('bg-surface-container-lowest', 'text-primary', 'shadow-sm');
                    btnPreview.classList.add('text-on-surface-variant');
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }

        // Attach listeners for Exit & Save Draft and Back navigation
        const dashboardLinks = document.querySelectorAll('a[data-path="dashboard"]');
        dashboardLinks.forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                await saveIcpDraft('/dashboard');
            });
        });

        const companyLinks = document.querySelectorAll('a[data-path="company-details"]');
        companyLinks.forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                await saveIcpDraft('/company');
            });
        });
});

