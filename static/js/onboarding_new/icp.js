document.addEventListener('DOMContentLoaded', async () => {
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const btnSubmit = document.getElementById('btn-submit-icp');
    const btnProceed = document.getElementById('btn-proceed-from-preview');
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

    const submitICP = async () => {
        // 1. Target Customer
        const targetCustomer = getChipsText('target-customer-container');
        
        // 2. Revenue
        let rev = "";
        if (revSelect.value === 'custom') {
            rev = JSON.stringify({
                label: "Custom",
                range: customRevInput.value.trim()
            });
        } else {
            rev = revSelect.value;
        }

        // 3. Headcount (Read existing pills)
        const sizeContainer = document.getElementById('headcount-container');
        const activeSizePills = sizeContainer ? Array.from(sizeContainer.querySelectorAll('.size-pill.active')).map(p => p.textContent.trim().replace('check', '').trim()) : [];
        const size = activeSizePills.join(', ');

        // 4. Industry
        const ind = getChipsText('industry-container');
        
        // 5. Geo
        const loc = getChipsText('location-container');
        
        // 6. Roles
        const roles = getChipsText('roles-container');
        
        // 7. Keywords
        const keywords = getChipsText('keywords-container');
        
        // 8. Exclusions
        const exclusions = getChipsText('exclusions-container');
        
        // 9. Signals
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

        // 10. Tone
        const activeTone = document.querySelector('input[name="tone"]:checked');
        const tone = activeTone ? activeTone.value : 'FORMAL';

        const payload = {
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
        
        const originalText = btnSubmit.innerHTML;
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Generating Report...</span>';
        
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
            
            // Show preview
            document.getElementById('questionnaire-view')?.classList.add('hidden');
            document.getElementById('preview-view')?.classList.remove('hidden');
            
        } catch (err) {
            alert(err.message);
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = originalText;
        }
    };

    if (btnSubmit) {
        btnSubmit.addEventListener('click', submitICP);
    }
    
    if (btnProceed) {
        btnProceed.addEventListener('click', () => {
            window.location.href = '/dashboard';
        });
    }
    
    if (btnEdit) {
        btnEdit.addEventListener('click', () => {
            document.getElementById('preview-view')?.classList.add('hidden');
            document.getElementById('questionnaire-view')?.classList.remove('hidden');
        });
    }
});
