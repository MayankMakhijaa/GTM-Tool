document.addEventListener('DOMContentLoaded', async () => {
    const btnContinue = document.getElementById('btn-continue');
    const btnSaveDraft = document.getElementById('btn-save-draft');
    const fetchButton = document.getElementById('fetch-button');
    const urlInput = document.getElementById('company-url-input');
    const fetchBanner = document.getElementById('fetch-banner');
    const fetchBannerIcon = document.getElementById('fetch-banner-icon');
    const fetchBannerMessage = document.getElementById('fetch-banner-message');
    const confirmationBanner = document.getElementById('confirmation-banner');
    const proposedCompanyName = document.getElementById('proposed-company-name');
    const proposedWebsiteLink = document.getElementById('proposed-website-link');
    const btnConfirmScrape = document.getElementById('btn-confirm-scrape');
    const btnCancelConfirmation = document.getElementById('btn-cancel-confirmation');
    const scrapeStatusBadge = document.getElementById('scrape-status-badge');

    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    let isScrapingActive = false;
    let userHasEdited = false;

    // Track manual edits on form fields
    const formEl = document.getElementById('company-form');
    if (formEl) {
        formEl.addEventListener('input', () => {
            userHasEdited = true;
        });
        formEl.addEventListener('change', () => {
            userHasEdited = true;
        });
    }

    const showBanner = (message, type = 'info') => {
        if (!fetchBanner || !fetchBannerMessage) return;
        fetchBanner.style.display = 'flex';
        fetchBannerMessage.innerHTML = message;
        if (fetchBannerIcon) {
            if (type === 'error') {
                fetchBannerIcon.textContent = 'error';
                fetchBannerIcon.className = 'material-symbols-outlined text-error text-[20px] shrink-0';
            } else if (type === 'warning') {
                fetchBannerIcon.textContent = 'warning';
                fetchBannerIcon.className = 'material-symbols-outlined text-amber-600 text-[20px] shrink-0';
            } else {
                fetchBannerIcon.textContent = 'verified';
                fetchBannerIcon.className = 'material-symbols-outlined text-primary text-[20px] shrink-0';
            }
        }
    };

    const setSelectValue = (selectEl, val) => {
        if (!selectEl || !val) return;
        const target = String(val).trim();
        if (!target) return;

        const normTarget = target.toLowerCase().replace(/[–—]/g, '-').replace(/\s+/g, ' ');
        let found = false;
        for (let opt of selectEl.options) {
            const optVal = opt.value.trim().toLowerCase().replace(/[–—]/g, '-').replace(/\s+/g, ' ');
            const optText = opt.text.trim().toLowerCase().replace(/[–—]/g, '-').replace(/\s+/g, ' ');
            if (optVal === normTarget || optText === normTarget || optVal.includes(normTarget) || normTarget.includes(optVal)) {
                opt.selected = true;
                found = true;
                break;
            }
        }
        if (!found) {
            const newOpt = document.createElement('option');
            newOpt.value = target;
            newOpt.textContent = target;
            newOpt.selected = true;
            selectEl.appendChild(newOpt);
        }
    };

    const populateForm = (data, forceOverwrite = false) => {
        if (!data) return;

        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (forceOverwrite || !userHasEdited || !el.value || el.value.trim() === '') {
                el.value = val || '';
            }
        };

        setVal('comp-name', data.company_name);
        setVal('comp-web', data.website_url);
        if (urlInput && (forceOverwrite || !urlInput.value || urlInput.value.trim() === '')) {
            urlInput.value = data.website_url || '';
        }
        setVal('comp-desc', data.description);
        setVal('comp-sells', data.what_company_sells);

        let psVal = data.products_services || '';
        if (Array.isArray(psVal)) {
            psVal = psVal.filter(Boolean).join(', ');
        }
        setVal('comp-products', psVal);

        setSelectValue(document.getElementById('comp-ind'), data.industry);
        setSelectValue(document.getElementById('comp-size'), data.company_size);
        setSelectValue(document.getElementById('comp-rev'), data.revenue);

        setVal('comp-loc', data.location);
        setVal('comp-rating', data.rating);
        setVal('comp-notes', data.other_details);

        if (scrapeStatusBadge) {
            if (data.scrape_status) {
                scrapeStatusBadge.textContent = data.scrape_status;
            } else {
                scrapeStatusBadge.textContent = 'PARSED & SYNCED';
            }
        }
    };

    const triggerScrape = async (websiteUrl, identificationStatus = 'CONFIRMED', confirmedByUser = true) => {
        if (isScrapingActive) return;
        isScrapingActive = true;

        const originalBtnContent = fetchButton ? fetchButton.innerHTML : '';
        if (fetchButton) {
            fetchButton.disabled = true;
            fetchButton.innerHTML = `
                <span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                <span>Extracting Signals...</span>
            `;
        }

        try {
            const res = await fetch('/api/onboarding/company/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    website_url: websiteUrl,
                    identification_status: identificationStatus,
                    confirmed_by_user: confirmedByUser
                })
            });

            const result = await res.json();
            if (res.ok && result.success && result.scraped_data) {
                populateForm(result.scraped_data, true);
                showBanner('<strong>Success:</strong> Company website scraped and enriched! Review and edit details below.', 'info');
                if (fetchButton) {
                    fetchButton.innerHTML = `
                        <span class="material-symbols-outlined text-[18px]">check</span>
                        <span>Signals Extracted!</span>
                    `;
                    setTimeout(() => {
                        fetchButton.innerHTML = originalBtnContent;
                        fetchButton.disabled = false;
                    }, 2500);
                }
            } else {
                showBanner(`<strong>Extraction warning:</strong> ${result.message || 'Unable to extract full details automatically. Please review and fill in missing fields.'}`, 'warning');
                if (fetchButton) {
                    fetchButton.disabled = false;
                    fetchButton.innerHTML = originalBtnContent;
                }
            }
        } catch (err) {
            console.error('Scraping error:', err);
            showBanner('<strong>Error:</strong> Failed to extract company details. You can enter details manually.', 'error');
            if (fetchButton) {
                fetchButton.disabled = false;
                fetchButton.innerHTML = originalBtnContent;
            }
        } finally {
            isScrapingActive = false;
        }
    };

    // 1. Check existing saved company details
    try {
        const res = await fetch('/api/onboarding/company');
        if (res.ok) {
            const result = await res.json();
            if (result.success && result.data && (result.data.company_name || result.data.website_url)) {
                // Saved data exists - load it and do NOT trigger auto-scrape
                populateForm(result.data, true);
                showBanner('<strong>Loaded Profile:</strong> Saved company details loaded. Review and edit below.', 'info');
                return;
            }
        }
    } catch (err) {
        console.error('Error fetching existing company details:', err);
    }

    // 2. No saved data found -> Auto-discovery and extraction flow
    showBanner('<strong>Auto-Discovery:</strong> Identifying company profile from your business email...', 'info');

    try {
        const idRes = await fetch('/api/onboarding/company/identify');
        if (idRes.ok) {
            const idResult = await idRes.json();
            if (idResult.success && idResult.identification_status === 'CONFIRMED') {
                const website = idResult.official_website;
                const companyName = idResult.company_name;

                if (document.getElementById('comp-name')) document.getElementById('comp-name').value = companyName || '';
                if (document.getElementById('comp-web')) document.getElementById('comp-web').value = website || '';
                if (urlInput) urlInput.value = website || '';

                showBanner(`<strong>Company Identified:</strong> Sourced ${companyName || 'company'} (${website}). Extracting website details...`, 'info');
                await triggerScrape(website, 'CONFIRMED', true);
            } else if (idResult.success && idResult.identification_status === 'NEEDS_CONFIRMATION') {
                // Confirmation required
                if (confirmationBanner && proposedCompanyName && proposedWebsiteLink) {
                    proposedCompanyName.textContent = idResult.company_name || 'your company';
                    proposedWebsiteLink.textContent = idResult.official_website || 'official website';
                    proposedWebsiteLink.href = idResult.official_website || '#';
                    confirmationBanner.classList.remove('hidden');
                    confirmationBanner.classList.add('flex');
                    if (fetchBanner) fetchBanner.style.display = 'none';

                    if (document.getElementById('comp-name')) document.getElementById('comp-name').value = idResult.company_name || '';
                    if (document.getElementById('comp-web')) document.getElementById('comp-web').value = idResult.official_website || '';
                    if (urlInput) urlInput.value = idResult.official_website || '';

                    if (btnConfirmScrape) {
                        btnConfirmScrape.onclick = async () => {
                            confirmationBanner.classList.add('hidden');
                            confirmationBanner.classList.remove('flex');
                            showBanner(`<strong>Confirmed:</strong> Extracting details for ${idResult.company_name}...`, 'info');
                            await triggerScrape(idResult.official_website, 'CONFIRMED', true);
                        };
                    }
                    if (btnCancelConfirmation) {
                        btnCancelConfirmation.onclick = () => {
                            confirmationBanner.classList.add('hidden');
                            confirmationBanner.classList.remove('flex');
                            showBanner('Please verify or enter your company website URL below.', 'warning');
                        };
                    }
                }
            } else {
                showBanner(`<strong>Identification:</strong> ${idResult.message || 'No automatic website match found for your email. Please enter your website URL below.'}`, 'warning');
            }
        }
    } catch (idErr) {
        console.error('Company identification error:', idErr);
        showBanner('Unable to auto-identify company. Please enter your website details manually.', 'warning');
    }

    // 3. Manual Fetch / Refresh Button Handler
    if (fetchButton) {
        fetchButton.addEventListener('click', async () => {
            const enteredUrl = urlInput?.value?.trim() || document.getElementById('comp-web')?.value?.trim();
            if (!enteredUrl) {
                alert('Please enter a company website URL to fetch information.');
                return;
            }
            if (confirmationBanner) {
                confirmationBanner.classList.add('hidden');
                confirmationBanner.classList.remove('flex');
            }
            showBanner(`<strong>Extracting Signals:</strong> Sourcing company profile for ${enteredUrl}...`, 'info');
            await triggerScrape(enteredUrl, 'CONFIRMED', true);
        });
    }

    // 4. Save and Continue / Draft Handlers
    const saveCompanyForm = async (redirectToIcp = true, isDraft = false) => {
        const getVal = (id) => document.getElementById(id)?.value?.trim() || '';

        const payload = {
            company_name: getVal('comp-name'),
            website_url: getVal('comp-web') || getVal('company-url-input'),
            description: getVal('comp-desc'),
            what_company_sells: getVal('comp-sells'),
            products_services: getVal('comp-products'),
            industry: getVal('comp-ind'),
            company_size: getVal('comp-size'),
            revenue: getVal('comp-rev'),
            location: getVal('comp-loc'),
            rating: getVal('comp-rating'),
            other_details: getVal('comp-notes'),
            is_draft: isDraft
        };

        if (!isDraft && !payload.website_url) {
            throw new Error('Website URL is required to continue.');
        }

        const res = await fetch('/api/onboarding/company', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Unable to save company details.');
        }

        if (redirectToIcp) {
            window.location.href = '/icp';
        }
        return data;
    };

    if (btnContinue) {
        btnContinue.addEventListener('click', async (e) => {
            e.preventDefault();
            const originalText = btnContinue.innerHTML;
            btnContinue.style.pointerEvents = 'none';
            btnContinue.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Saving...</span>';

            try {
                await saveCompanyForm(true, false);
            } catch (err) {
                alert(err.message);
                btnContinue.style.pointerEvents = 'auto';
                btnContinue.innerHTML = originalText;
            }
        });
    }

    if (btnSaveDraft) {
        btnSaveDraft.addEventListener('click', async (e) => {
            e.preventDefault();
            const originalText = btnSaveDraft.innerHTML;
            btnSaveDraft.disabled = true;
            btnSaveDraft.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Saving Draft...</span>';

            try {
                await saveCompanyForm(false, true);
                btnSaveDraft.innerHTML = '<span>Saved!</span>';
                setTimeout(() => {
                    btnSaveDraft.innerHTML = originalText;
                    btnSaveDraft.disabled = false;
                }, 2000);
            } catch (err) {
                alert(err.message);
                btnSaveDraft.disabled = false;
                btnSaveDraft.innerHTML = originalText;
            }
        });
    }

    // Attach click listeners to all Exit & Save Draft and Back to Setup links targeting dashboard
    const dashboardNavLinks = document.querySelectorAll('a[data-path="dashboard"]');
    dashboardNavLinks.forEach(link => {
        link.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                await saveCompanyForm(false, true);
            } catch (err) {
                console.warn('Draft save notice:', err);
            } finally {
                window.location.href = '/dashboard';
            }
        });
    });
});

