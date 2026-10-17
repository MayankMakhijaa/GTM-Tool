document.addEventListener('DOMContentLoaded', async () => {
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const btnSubmit = document.getElementById('btn-submit-icp');
    const btnAccept = document.getElementById('btn-accept-parameters');
    const btnFinalize = document.getElementById('btn-finalize-parameters') || document.getElementById('btn-proceed-from-preview');
    const btnEdit = document.getElementById('btn-edit-questionnaire');

    const urlParams = new URLSearchParams(window.location.search);
    const rawReturnUrl = urlParams.get('return_url');
    const returnUrl = (rawReturnUrl && rawReturnUrl.startsWith('/') && !rawReturnUrl.startsWith('//')) ? rawReturnUrl : null;

    // Canonical Countries dataset for offline & instant autocomplete
    const CANONICAL_COUNTRIES = [
        "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
        "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas",
        "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize",
        "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil",
        "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
        "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China",
        "Colombia", "Comoros", "Congo (Congo-Brazzaville)", "Costa Rica", "Croatia",
        "Cuba", "Cyprus", "Czech Republic", "Democratic Republic of the Congo",
        "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt",
        "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia",
        "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana",
        "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti",
        "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland",
        "Israel", "Italy", "Ivory Coast", "Jamaica", "Japan", "Jordan", "Kazakhstan",
        "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon",
        "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg",
        "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta",
        "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova",
        "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
        "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
        "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau",
        "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines",
        "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda",
        "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines",
        "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal",
        "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
        "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan",
        "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria",
        "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga",
        "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda",
        "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay",
        "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen",
        "Zambia", "Zimbabwe"
    ];

    const COUNTRY_MAP = {};
    CANONICAL_COUNTRIES.forEach(c => { COUNTRY_MAP[c.toLowerCase()] = c; });

    const COUNTRY_ALIASES = {
        "usa": "United States", "us": "United States", "u.s.": "United States", "u.s.a.": "United States", "united states of america": "United States",
        "uk": "United Kingdom", "u.k.": "United Kingdom", "great britain": "United Kingdom", "britain": "United Kingdom",
        "uae": "United Arab Emirates", "u.a.e.": "United Arab Emirates", "emirates": "United Arab Emirates",
        "south korea": "South Korea", "korea, republic of": "South Korea", "republic of korea": "South Korea",
        "north korea": "North Korea", "russia": "Russia", "russian federation": "Russia",
        "vietnam": "Vietnam", "czechia": "Czech Republic", "czech republic": "Czech Republic",
        "taiwan": "Taiwan", "holland": "Netherlands", "the netherlands": "Netherlands",
        "ivory coast": "Ivory Coast", "cote d'ivoire": "Ivory Coast", "côte d'ivoire": "Ivory Coast"
    };

    const LEGITIMATE_REGIONS = {
        "north america (us & canada)": "North America (US & Canada)",
        "north america (us and canada)": "North America (US & Canada)",
        "north america": "North America",
        "na": "North America",
        "western europe": "Western Europe",
        "eastern europe": "Eastern Europe",
        "central & eastern europe": "Central & Eastern Europe",
        "europe": "Europe",
        "european union": "European Union",
        "eu": "European Union",
        "apac": "APAC",
        "asia-pacific": "Asia-Pacific",
        "asia pacific": "Asia-Pacific",
        "emea": "EMEA",
        "latam": "LATAM",
        "latin america": "Latin America",
        "dach": "DACH",
        "nordics": "Nordics",
        "scandinavia": "Scandinavia",
        "benelux": "Benelux",
        "mena": "MENA",
        "middle east": "Middle East",
        "gcc": "GCC",
        "asean": "ASEAN",
        "southeast asia": "Southeast Asia",
        "anz": "ANZ",
        "uk & ireland": "UK & Ireland",
        "united kingdom & ireland": "UK & Ireland",
        "south america": "South America",
        "global": "Global",
        "worldwide": "Worldwide"
    };

    const NON_COUNTRY_GEOGRAPHIES = {
        "bengaluru": { type: "city", rec: "India" },
        "bangalore": { type: "city", rec: "India" },
        "mumbai": { type: "city", rec: "India" },
        "delhi": { type: "city", rec: "India" },
        "new delhi": { type: "city", rec: "India" },
        "hyderabad": { type: "city", rec: "India" },
        "chennai": { type: "city", rec: "India" },
        "pune": { type: "city", rec: "India" },
        "london": { type: "city", rec: "United Kingdom" },
        "manchester": { type: "city", rec: "United Kingdom" },
        "new york": { type: "city", rec: "United States" },
        "nyc": { type: "city", rec: "United States" },
        "san francisco": { type: "city", rec: "United States" },
        "sf": { type: "city", rec: "United States" },
        "los angeles": { type: "city", rec: "United States" },
        "chicago": { type: "city", rec: "United States" },
        "seattle": { type: "city", rec: "United States" },
        "austin": { type: "city", rec: "United States" },
        "boston": { type: "city", rec: "United States" },
        "toronto": { type: "city", rec: "Canada" },
        "vancouver": { type: "city", rec: "Canada" },
        "sydney": { type: "city", rec: "Australia" },
        "melbourne": { type: "city", rec: "Australia" },
        "berlin": { type: "city", rec: "Germany" },
        "paris": { type: "city", rec: "France" },
        "tokyo": { type: "city", rec: "Japan" },
        "dubai": { type: "city", rec: "United Arab Emirates" },
        "california": { type: "state", rec: "United States" },
        "texas": { type: "state", rec: "United States" },
        "florida": { type: "state", rec: "United States" },
        "ontario": { type: "province", rec: "Canada" },
        "karnataka": { type: "state", rec: "India" },
        "maharashtra": { type: "state", rec: "India" },
        "bavaria": { type: "state", rec: "Germany" }
    };

    // Domain Acronyms and Business Terminology for Advisory Spelling
    const BUSINESS_SPELLING_MAP = {
        "saas": "SaaS", "b2b": "B2B", "b2c": "B2C", "revops": "RevOps", "devops": "DevOps",
        "fintech": "FinTech", "devtools": "DevTools", "crm": "CRM", "tam": "TAM",
        "arr": "ARR", "mrr": "MRR", "acv": "ACV", "sdr": "SDR", "sdrs": "SDRs", "bdr": "BDR", "bdrs": "BDRs",
        "ae": "AE", "aes": "AEs", "gtm": "GTM", "icp": "ICP", "ceo": "CEO", "cto": "CTO",
        "vp": "VP", "smb": "SMB", "ai": "AI", "ml": "ML", "api": "API", "apis": "APIs",
        "paas": "PaaS", "iaas": "IaaS", "plg": "PLG", "cac": "CAC", "ltv": "LTV", "roi": "ROI",
        "enterpise": "enterprise", "enterpirse": "enterprise", "enteprise": "enterprise",
        "midmarket": "Mid-Market", "mid-market": "Mid-Market", "stratgy": "strategy",
        "automatn": "automation", "automtion": "automation", "enricment": "enrichment"
    };

    const getSpellingSuggestion = (text) => {
        if (!text || typeof text !== 'string') return null;
        const words = text.trim().split(/\b/);
        let changed = false;
        const mapped = words.map(word => {
            const lower = word.toLowerCase();
            if (BUSINESS_SPELLING_MAP[lower] && word !== BUSINESS_SPELLING_MAP[lower]) {
                changed = true;
                return BUSINESS_SPELLING_MAP[lower];
            }
            return word;
        });
        return changed ? mapped.join('') : null;
    };

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

    // Advisory spelling hint renderer
    const showSpellingAdvisory = (container, chipElement, originalText, suggestedText) => {
        let advisoryBox = container.parentNode.querySelector('.spelling-advisory-box');
        if (!advisoryBox) {
            advisoryBox = document.createElement('div');
            advisoryBox.className = 'spelling-advisory-box flex items-center gap-2 mt-1.5 px-2.5 py-1 bg-primary-fixed/20 border border-primary/20 rounded text-xs text-primary';
            container.parentNode.appendChild(advisoryBox);
        }

        advisoryBox.innerHTML = `
            <span class="material-symbols-outlined text-[15px] shrink-0 text-primary">lightbulb</span>
            <span class="flex-1">Suggestion for "<strong>${originalText}</strong>": Did you mean <strong>${suggestedText}</strong>?</span>
            <button type="button" class="apply-spelling-btn underline font-semibold hover:text-secondary px-1 cursor-pointer">Apply</button>
            <button type="button" class="dismiss-spelling-btn text-outline hover:text-on-surface px-1 cursor-pointer">Dismiss</button>
        `;

        const applyBtn = advisoryBox.querySelector('.apply-spelling-btn');
        const dismissBtn = advisoryBox.querySelector('.dismiss-spelling-btn');

        applyBtn.addEventListener('click', () => {
            const textEl = chipElement.querySelector('.chip-text');
            if (textEl) textEl.textContent = suggestedText;
            advisoryBox.remove();
        });

        dismissBtn.addEventListener('click', () => {
            advisoryBox.remove();
        });
    };

    // -----------------------------------------------------------------------
    // Smart Autocomplete Knowledge Bases for ICP Fields
    // -----------------------------------------------------------------------
    const SUGGESTIONS_MAP = {
        target_customer: [
            "B2B SaaS Companies",
            "Enterprise Software",
            "Mid-Market Companies",
            "High-Growth Startups",
            "SMBs",
            "Early-Stage Startups",
            "Growth Scale Startups",
            "Mid-Market Growth Teams",
            "Global Enterprises",
            "Scale-Up Companies",
            "B2B Marketplaces",
            "Cloud Infrastructure Providers",
            "Professional Services Firms",
            "Digital Agencies"
        ],
        industry: [
            "FinTech",
            "HealthTech",
            "DevTools",
            "Cybersecurity",
            "HRTech",
            "EdTech",
            "E-commerce",
            "B2B SaaS",
            "InsurTech",
            "PropTech",
            "MarTech",
            "LegalTech",
            "CleanTech & Climate",
            "BioTech & Life Sciences",
            "Supply Chain & Logistics",
            "DevTools & Infrastructure",
            "Enterprise Automation",
            "Data & Analytics",
            "Artificial Intelligence & Machine Learning"
        ],
        roles: [
            "VP of Sales",
            "Chief Revenue Officer",
            "Chief Commercial Officer",
            "Head of Revenue Operations",
            "CTO",
            "Head of HR",
            "Growth Lead",
            "Chief Executive Officer",
            "Chief Operating Officer",
            "VP of Marketing",
            "VP of Engineering",
            "Head of Sales",
            "Head of Business Development",
            "Director of Sales",
            "Director of Demand Generation",
            "Director of Revenue Operations",
            "Head of People",
            "Chief People Officer"
        ],
        keywords: [
            "lead enrichment",
            "outbound automation",
            "sales capacity",
            "inbound response time",
            "CRM",
            "sales intelligence",
            "prospecting automation",
            "contact data enrichment",
            "intent data",
            "pipeline generation",
            "account based marketing",
            "cold email sequencing",
            "revenue intelligence",
            "deal velocity",
            "cadence management",
            "conversation intelligence",
            "buyer intent signals",
            "multichannel outreach"
        ],
        exclusions: [
            "B2C / Consumer",
            "Agency / Freelance",
            "Below Minimum ARR",
            "< $1M ARR",
            "Early Stage / Pre-revenue",
            "Non-Profit Organizations",
            "Government & Public Sector",
            "Hardware / Manufacturing",
            "Brick & Mortar Retail",
            "Consulting Sole Proprietorships",
            "Individual Contractors",
            "Students / Academic"
        ]
    };

    // Keyword topic semantic associations: if query matches or is closely related, suggest related concepts
    const KEYWORD_ASSOCIATIONS = {
        "enrichment": ["CRM", "sales intelligence", "prospecting automation", "contact data enrichment"],
        "lead": ["CRM", "sales intelligence", "prospecting automation", "contact data enrichment"],
        "prospecting": ["sales intelligence", "contact data enrichment", "outbound automation", "buyer intent signals"],
        "crm": ["lead enrichment", "sales capacity", "revenue intelligence", "pipeline generation"],
        "sales": ["sales capacity", "deal velocity", "sales intelligence", "outbound automation"],
        "automation": ["outbound automation", "prospecting automation", "cadence management"],
        "intent": ["buyer intent signals", "intent data", "account based marketing"],
        "outbound": ["outbound automation", "cadence management", "multichannel outreach"],
        "pipeline": ["pipeline generation", "deal velocity", "revenue intelligence"]
    };

    // Field-specific aliases / normalizations
    const FIELD_ALIASES = {
        target_customer: {
            "smb": "SMBs",
            "smbs": "SMBs",
            "enterprise": "Enterprise Software",
            "enterprises": "Global Enterprises",
            "mid market": "Mid-Market Companies",
            "midmarket": "Mid-Market Companies",
            "startups": "High-Growth Startups",
            "saas": "B2B SaaS Companies"
        },
        industry: {
            "fintech": "FinTech",
            "healthtech": "HealthTech",
            "devtools": "DevTools",
            "cybersecurity": "Cybersecurity",
            "cyber security": "Cybersecurity",
            "hrtech": "HRTech",
            "edtech": "EdTech",
            "ecommerce": "E-commerce",
            "e-commerce": "E-commerce",
            "b2b saas": "B2B SaaS",
            "martech": "MarTech",
            "insurtech": "InsurTech",
            "proptech": "PropTech",
            "legaltech": "LegalTech",
            "ai": "Artificial Intelligence & Machine Learning",
            "ml": "Artificial Intelligence & Machine Learning"
        },
        roles: {
            "cro": "Chief Revenue Officer",
            "cco": "Chief Commercial Officer",
            "cto": "CTO",
            "ceo": "Chief Executive Officer",
            "coo": "Chief Operating Officer",
            "cpo": "Chief People Officer",
            "head of revops": "Head of Revenue Operations",
            "revops lead": "Head of Revenue Operations",
            "vp sales": "VP of Sales",
            "vp marketing": "VP of Marketing",
            "vp engineering": "VP of Engineering",
            "head of hr": "Head of HR",
            "head hr": "Head of HR"
        },
        exclusions: {
            "b2c": "B2C / Consumer",
            "consumer": "B2C / Consumer",
            "agency": "Agency / Freelance",
            "freelance": "Agency / Freelance",
            "freelancer": "Agency / Freelance",
            "low arr": "Below Minimum ARR",
            "< $1m": "< $1M ARR",
            "pre-revenue": "Early Stage / Pre-revenue"
        }
    };

    const getFieldSuggestions = (fieldKey, query) => {
        const pool = SUGGESTIONS_MAP[fieldKey] || [];
        const q = (query || "").trim().toLowerCase();

        if (!q) {
            // Return top default suggestions for this field
            return pool.slice(0, 6);
        }

        const exactAlias = (FIELD_ALIASES[fieldKey] && FIELD_ALIASES[fieldKey][q]);

        // Prefix matches
        const prefix = pool.filter(item => item.toLowerCase().startsWith(q));
        // Substring matches
        const contains = pool.filter(item => item.toLowerCase().includes(q) && !item.toLowerCase().startsWith(q));

        let combined = prefix.concat(contains);

        // Keywords semantic associations
        if (fieldKey === 'keywords') {
            Object.keys(KEYWORD_ASSOCIATIONS).forEach(trigger => {
                if (q.includes(trigger)) {
                    KEYWORD_ASSOCIATIONS[trigger].forEach(assoc => {
                        if (!combined.some(c => c.toLowerCase() === assoc.toLowerCase())) {
                            combined.push(assoc);
                        }
                    });
                }
            });
        }

        // If an exact alias exists, ensure it is at the front
        if (exactAlias && !combined.some(c => c.toLowerCase() === exactAlias.toLowerCase())) {
            combined.unshift(exactAlias);
        }

        // Typo suggestions if no direct matches found
        if (combined.length === 0 && q.length >= 3) {
            const close = pool.find(item => {
                const il = item.toLowerCase();
                if (Math.abs(il.length - q.length) > 3) return false;
                let diff = 0;
                for (let i = 0; i < Math.min(il.length, q.length); i++) {
                    if (il[i] !== q[i]) diff++;
                }
                return diff <= 2;
            });

            if (close) {
                return [{
                    type: 'typo_suggestion',
                    value: close,
                    message: `Did you mean '${close}'?`
                }];
            }
        }

        return combined.slice(0, 8);
    };

    const setupSmartTagInput = (inputId, btnId, containerId, dropdownId, typeClass, iconHtml = '') => {
        const input = document.getElementById(inputId);
        const btn = document.getElementById(btnId);
        const container = document.getElementById(containerId);
        const dropdown = dropdownId ? document.getElementById(dropdownId) : null;
        let selectedIndex = -1;

        if (!input || !container) return;

        const hideDropdown = () => {
            if (dropdown) dropdown.classList.add('hidden');
            selectedIndex = -1;
        };

        const renderDropdown = (items) => {
            if (!dropdown) return;
            selectedIndex = -1;
            dropdown.innerHTML = '';

            const currentVal = input.value.trim();

            if (items.length === 0) {
                if (currentVal) {
                    dropdown.innerHTML = `
                        <div class="px-3 py-2 text-outline text-xs flex items-center justify-between">
                            <span>No exact suggestion. Press <strong>Enter</strong> to add "<strong>${currentVal}</strong>" as custom tag.</span>
                        </div>
                    `;
                    dropdown.classList.remove('hidden');
                } else {
                    hideDropdown();
                }
                return;
            }

            items.forEach((item, idx) => {
                const div = document.createElement('div');
                div.className = 'px-3 py-2 hover:bg-surface-container cursor-pointer transition-colors flex items-center justify-between text-on-surface text-sm';
                div.setAttribute('data-index', idx);

                if (typeof item === 'object' && item.type === 'typo_suggestion') {
                    div.innerHTML = `
                        <div class="flex items-center gap-1.5 text-primary">
                            <span class="material-symbols-outlined text-[16px]">lightbulb</span>
                            <span>${item.message}</span>
                        </div>
                    `;
                    div.setAttribute('data-value', item.value);
                } else {
                    const strVal = typeof item === 'string' ? item : item.value;
                    let icon = 'tag';
                    if (typeClass === 'roles') icon = 'badge';
                    else if (typeClass === 'industry') icon = 'domain';
                    else if (typeClass === 'keywords') icon = 'bolt';
                    else if (typeClass === 'exclusions') icon = 'block';

                    div.innerHTML = `
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-[16px] text-outline">${icon}</span>
                            <span>${strVal}</span>
                        </div>
                    `;
                    div.setAttribute('data-value', strVal);
                }

                div.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    const val = div.getAttribute('data-value');
                    if (val) addChip(val);
                });

                dropdown.appendChild(div);
            });

            dropdown.classList.remove('hidden');
        };

        const addChip = (rawVal) => {
            const val = rawVal.trim();
            if (!val) return;

            // Check aliases
            const alias = FIELD_ALIASES[typeClass] && FIELD_ALIASES[typeClass][val.toLowerCase()];
            const resolvedVal = alias || val;

            // Check duplicates
            const existing = Array.from(container.querySelectorAll('.chip-text')).map(el => el.textContent.trim().toLowerCase());
            if (existing.includes(resolvedVal.toLowerCase())) {
                input.value = '';
                hideDropdown();
                return;
            }

            const newChip = createChipElement(resolvedVal, typeClass, iconHtml);
            container.insertBefore(newChip, input);
            input.value = '';
            hideDropdown();

            // Non-blocking advisory check for business casing/acronyms
            const suggestion = getSpellingSuggestion(resolvedVal);
            if (suggestion && suggestion.toLowerCase() !== resolvedVal.toLowerCase()) {
                showSpellingAdvisory(container, newChip, resolvedVal, suggestion);
            }
        };

        if (btn) {
            btn.addEventListener('click', () => {
                input.classList.remove('hidden');
                input.focus();
                renderDropdown(getFieldSuggestions(typeClass, ''));
            });
        }

        input.addEventListener('focus', () => {
            renderDropdown(getFieldSuggestions(typeClass, input.value));
        });

        input.addEventListener('input', () => {
            renderDropdown(getFieldSuggestions(typeClass, input.value));
        });

        input.addEventListener('keydown', (e) => {
            const items = dropdown ? dropdown.querySelectorAll('[data-value]') : [];

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (items.length === 0) return;
                selectedIndex = (selectedIndex + 1) % items.length;
                items.forEach((it, i) => it.classList.toggle('bg-surface-container', i === selectedIndex));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (items.length === 0) return;
                selectedIndex = (selectedIndex - 1 + items.length) % items.length;
                items.forEach((it, i) => it.classList.toggle('bg-surface-container', i === selectedIndex));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && items[selectedIndex]) {
                    const val = items[selectedIndex].getAttribute('data-value');
                    if (val) {
                        addChip(val);
                        return;
                    }
                }

                // If nothing highlighted in dropdown, add whatever custom text is entered
                const val = input.value.trim();
                if (val) {
                    addChip(val);
                }
            } else if (e.key === 'Escape') {
                hideDropdown();
            }
        });

        document.addEventListener('click', (e) => {
            if (!container.contains(e.target) && (!dropdown || !dropdown.contains(e.target)) && (!btn || !btn.contains(e.target))) {
                hideDropdown();
            }
        });

        attachRemoveListeners(containerId);
    };

    // Setup smart tag inputs with rich autocomplete and suggestions
    setupSmartTagInput('target-customer-input', null, 'target-customer-container', 'target-customer-dropdown', 'target_customer');
    setupSmartTagInput('industry-input', 'add-industry-btn', 'industry-container', 'industry-dropdown', 'industry');
    setupSmartTagInput('roles-input', 'add-role-btn', 'roles-container', 'roles-dropdown', 'roles');
    setupSmartTagInput('keywords-input', 'add-keyword-btn', 'keywords-container', 'keywords-dropdown', 'keywords');
    setupSmartTagInput('exclusions-input', 'add-exclusion-btn', 'exclusions-container', 'exclusions-dropdown', 'exclusions');

    // -----------------------------------------------------------------------
    // Dedicated Country-Only Autocomplete & Location Controller
    // -----------------------------------------------------------------------
    const setupLocationAutocomplete = () => {
        const locInput = document.getElementById('location-input');
        const locBtn = document.getElementById('add-location-btn');
        const locContainer = document.getElementById('location-container');
        const dropdown = document.getElementById('location-dropdown');
        const validationMsg = document.getElementById('location-validation-msg');
        let selectedIndex = -1;

        if (!locInput || !locContainer) return;

        const showValidation = (msg) => {
            if (validationMsg) {
                validationMsg.textContent = msg;
                validationMsg.classList.remove('hidden');
            }
        };

        const clearValidation = () => {
            if (validationMsg) {
                validationMsg.textContent = '';
                validationMsg.classList.add('hidden');
            }
        };

        const resolveLocationName = (query) => {
            const clean = query.trim().toLowerCase();
            if (COUNTRY_MAP[clean]) return COUNTRY_MAP[clean];
            if (COUNTRY_ALIASES[clean]) return COUNTRY_ALIASES[clean];
            if (LEGITIMATE_REGIONS[clean]) return LEGITIMATE_REGIONS[clean];
            return null;
        };

        const getSuggestions = (query) => {
            const q = query.trim().toLowerCase();
            const regionalTargets = Object.values(LEGITIMATE_REGIONS);
            const combinedTargets = Array.from(new Set(CANONICAL_COUNTRIES.concat(regionalTargets)));

            if (!q) {
                return [
                    "United States", "United Kingdom", "India", "Singapore", "Germany",
                    "North America (US & Canada)", "Western Europe", "EMEA", "APAC", "Canada"
                ];
            }

            const prefix = combinedTargets.filter(c => c.toLowerCase().startsWith(q));
            const contains = combinedTargets.filter(c => c.toLowerCase().includes(q) && !c.toLowerCase().startsWith(q));
            let results = prefix.concat(contains);

            // Typo check if no direct match
            if (results.length === 0 && q.length >= 3) {
                // Check non-country entity
                if (NON_COUNTRY_GEOGRAPHIES[q]) {
                    const geo = NON_COUNTRY_GEOGRAPHIES[q];
                    return [{
                        type: 'entity_warning',
                        message: `'${query.trim()}' is a ${geo.type}, not a country or regional market. Select ${geo.rec} instead.`,
                        country: geo.rec.split(',')[0].trim()
                    }];
                }

                // Check simple typo distance against countries & regions
                const close = combinedTargets.find(c => {
                    const cl = c.toLowerCase();
                    if (Math.abs(cl.length - q.length) > 2) return false;
                    let diff = 0;
                    for (let i = 0; i < Math.min(cl.length, q.length); i++) {
                        if (cl[i] !== q[i]) diff++;
                    }
                    return diff <= 2;
                });
                if (close) {
                    return [{
                        type: 'typo_suggestion',
                        country: close,
                        message: `Did you mean '${close}'?`
                    }];
                }
            }

            return results.slice(0, 10);
        };

        const renderDropdown = (items) => {
            if (!dropdown) return;
            selectedIndex = -1;
            dropdown.innerHTML = '';

            if (items.length === 0) {
                dropdown.innerHTML = `<div class="px-3 py-2 text-outline text-xs italic">No matching country or market found. Recognized countries and regional markets are accepted.</div>`;
                dropdown.classList.remove('hidden');
                return;
            }

            items.forEach((item, idx) => {
                const div = document.createElement('div');
                div.className = 'px-3 py-2 hover:bg-surface-container cursor-pointer transition-colors flex items-center justify-between text-on-surface text-sm';
                div.setAttribute('data-index', idx);

                if (typeof item === 'object') {
                    if (item.type === 'entity_warning') {
                        div.innerHTML = `
                            <div class="flex items-center gap-1.5 text-error">
                                <span class="material-symbols-outlined text-[16px]">info</span>
                                <span>${item.message}</span>
                            </div>
                        `;
                        div.setAttribute('data-country', item.country);
                    } else if (item.type === 'typo_suggestion') {
                        div.innerHTML = `
                            <div class="flex items-center gap-1.5 text-primary">
                                <span class="material-symbols-outlined text-[16px]">lightbulb</span>
                                <span>${item.message}</span>
                            </div>
                        `;
                        div.setAttribute('data-country', item.country);
                    }
                } else {
                    div.innerHTML = `
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-[16px] text-outline">public</span>
                            <span>${item}</span>
                        </div>
                    `;
                    div.setAttribute('data-country', item);
                }

                div.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    const country = div.getAttribute('data-country');
                    if (country) addCountryChip(country);
                });

                dropdown.appendChild(div);
            });

            dropdown.classList.remove('hidden');
        };

        const hideDropdown = () => {
            if (dropdown) dropdown.classList.add('hidden');
            selectedIndex = -1;
        };

        const addCountryChip = (country) => {
            clearValidation();
            const existing = Array.from(locContainer.querySelectorAll('.chip-text')).map(el => el.textContent.trim().toLowerCase());
            if (existing.includes(country.toLowerCase())) {
                locInput.value = '';
                hideDropdown();
                return;
            }

            const newChip = createChipElement(country, 'location', '<span class="material-symbols-outlined text-[14px]">public</span>');
            locContainer.insertBefore(newChip, locInput);
            locInput.value = '';
            hideDropdown();
        };

        if (locBtn) {
            locBtn.addEventListener('click', () => {
                locInput.classList.remove('hidden');
                locInput.focus();
                renderDropdown(getSuggestions(''));
            });
        }

        locInput.addEventListener('focus', () => {
            renderDropdown(getSuggestions(locInput.value));
        });

        locInput.addEventListener('input', () => {
            clearValidation();
            renderDropdown(getSuggestions(locInput.value));
        });

        locInput.addEventListener('keydown', (e) => {
            const items = dropdown ? dropdown.querySelectorAll('[data-country]') : [];

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (items.length === 0) return;
                selectedIndex = (selectedIndex + 1) % items.length;
                items.forEach((it, i) => it.classList.toggle('bg-surface-container', i === selectedIndex));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (items.length === 0) return;
                selectedIndex = (selectedIndex - 1 + items.length) % items.length;
                items.forEach((it, i) => it.classList.toggle('bg-surface-container', i === selectedIndex));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && items[selectedIndex]) {
                    const country = items[selectedIndex].getAttribute('data-country');
                    if (country) addCountryChip(country);
                    return;
                }

                const rawVal = locInput.value.trim();
                if (!rawVal) return;

                const canonical = resolveLocationName(rawVal);
                if (canonical) {
                    addCountryChip(canonical);
                } else {
                    const lower = rawVal.toLowerCase();
                    if (NON_COUNTRY_GEOGRAPHIES[lower]) {
                        const geo = NON_COUNTRY_GEOGRAPHIES[lower];
                        showValidation(`'${rawVal}' is a ${geo.type}, not a country or regional market. Please select a recognized country (e.g., ${geo.rec}) or regional target market.`);
                    } else {
                        // Check typo against combined pool
                        const combinedTargets = CANONICAL_COUNTRIES.concat(Object.values(LEGITIMATE_REGIONS));
                        const typo = combinedTargets.find(c => {
                            const cl = c.toLowerCase();
                            return Math.abs(cl.length - lower.length) <= 2 &&
                                   combinedTargets.filter(x => x.toLowerCase().startsWith(lower.slice(0, 3))).length > 0;
                        });
                        if (typo) {
                            showValidation(`Invalid location '${rawVal}'. Did you mean '${typo}'?`);
                        } else {
                            showValidation(`Invalid location '${rawVal}'. Only recognized sovereign countries and legitimate regional target markets are accepted.`);
                        }
                    }
                }
            } else if (e.key === 'Escape') {
                hideDropdown();
            }
        });

        document.addEventListener('click', (e) => {
            if (!locContainer.contains(e.target) && !dropdown.contains(e.target) && (locBtn && !locBtn.contains(e.target))) {
                hideDropdown();
            }
        });

        attachRemoveListeners('location-container');
    };

    setupLocationAutocomplete();

    // -----------------------------------------------------------------------
    // Revenue, Tone, and Buying Signals Setup
    // -----------------------------------------------------------------------
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
            toneItems.forEach(t => {
                t.classList.remove('border-primary');
                t.classList.add('border-transparent');
                t.querySelector('.tone-icon').textContent = 'radio_button_unchecked';
                t.querySelector('.tone-icon').classList.remove('text-primary');
                t.querySelector('.tone-icon').classList.add('text-outline');
                t.querySelector('input').checked = false;
            });
            item.classList.add('border-primary');
            item.classList.remove('border-transparent');
            item.querySelector('.tone-icon').textContent = 'radio_button_checked';
            item.querySelector('.tone-icon').classList.add('text-primary');
            item.querySelector('.tone-icon').classList.remove('text-outline');
            item.querySelector('input').checked = true;
        });
    });

    // Reactive Buying Signals count updater
    const updateSignalsBadge = (count) => {
        const badge = document.getElementById('signals-active-count');
        if (badge) {
            badge.textContent = `${count} Active Trigger${count === 1 ? '' : 's'}`;
        }
    };

    const signalItems = document.querySelectorAll('.signal-item');
    signalItems.forEach(item => {
        const checkbox = item.querySelector('.signal-checkbox');
        if (checkbox) {
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    item.classList.remove('opacity-75');
                } else {
                    item.classList.add('opacity-75');
                }
                const active = document.querySelectorAll('.signal-checkbox:checked').length;
                updateSignalsBadge(active);
            });
        }
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
                window.location.href = returnUrl || '/dashboard';
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
        const effectiveTarget = (returnUrl && redirectTarget === '/dashboard') ? returnUrl : redirectTarget;
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
            if (effectiveTarget) {
                window.location.href = effectiveTarget;
            }
            return data;
        } catch (err) {
            console.error('Error saving ICP draft:', err);
            if (effectiveTarget) {
                window.location.href = effectiveTarget;
            }
        }
    };

    // -----------------------------------------------------------------------
    // Load and Restore Saved ICP Data
    // -----------------------------------------------------------------------
    const loadICPData = async () => {
        try {
            const res = await fetch('/api/onboarding/icp');
            if (!res.ok) return;
            const result = await res.json();
            if (!result.success || !result.data) return;

            const data = result.data;
            const hasSavedData = Object.keys(data).length > 0 && (data.target_customer !== undefined || data.version !== undefined);

            const clearChips = (containerId) => {
                const container = document.getElementById(containerId);
                if (!container) return;
                const chips = container.querySelectorAll('.chip-item');
                chips.forEach(chip => chip.remove());
            };

            const splitLocationTokens = (val) => {
                if (!val) return [];
                const matches = String(val).match(/(?:[^,(]+|\([^)]*\))+/g);
                return matches ? matches.map(s => s.trim()).filter(Boolean) : [];
            };

            const populateChips = (containerId, textVal, typeClass, iconHtml = '') => {
                const container = document.getElementById(containerId);
                if (!container || !textVal) return;
                const items = (typeClass === 'location')
                    ? splitLocationTokens(textVal)
                    : String(textVal).split(',').map(s => s.trim()).filter(Boolean);
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

            if (hasSavedData) {
                clearChips('target-customer-container');
                clearChips('industry-container');
                clearChips('location-container');
                clearChips('roles-container');
                clearChips('keywords-container');
                clearChips('exclusions-container');
            }

            populateChips('target-customer-container', data.target_customer, 'target_customer');
            populateChips('industry-container', data.industry, 'industry');
            populateChips('location-container', data.location, 'location', '<span class="material-symbols-outlined text-[14px]">public</span>');
            populateChips('roles-container', data.target_jobs_roles, 'roles');
            populateChips('keywords-container', data.keywords, 'keywords');
            populateChips('exclusions-container', data.exclusions, 'exclusions');

            if (data.company_size !== undefined && data.company_size !== null) {
                const sizeArr = String(data.company_size).split(',').map(s => s.trim()).filter(Boolean);
                const sizePills = document.querySelectorAll('.size-pill');
                sizePills.forEach(pill => {
                    const label = pill.textContent.trim().replace('check', '').trim();
                    const shouldBeActive = sizeArr.includes(label);
                    const isActive = pill.classList.contains('active');
                    if (shouldBeActive && !isActive) {
                        pill.click();
                    } else if (!shouldBeActive && isActive) {
                        pill.click();
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
                    } else if (parsed && parsed.range) {
                        let matched = false;
                        Array.from(revSelect.options).forEach(opt => {
                            if (opt.value === data.revenue_range || opt.value.includes(parsed.range)) {
                                revSelect.value = opt.value;
                                matched = true;
                            }
                        });
                        if (!matched) {
                            revSelect.value = data.revenue_range;
                        }
                    } else {
                        revSelect.value = data.revenue_range;
                    }
                } catch (e) {
                    revSelect.value = data.revenue_range;
                }
            }

            // Restore saved buying signals properly
            if (data.signals !== undefined && data.signals !== null) {
                let activeCount = 0;
                signalItems.forEach(item => {
                    const key = item.getAttribute('data-signal-key');
                    const checkbox = item.querySelector('.signal-checkbox');
                    if (!checkbox || !key) return;

                    let isEnabled = false;
                    let metaVal = null;
                    if (Array.isArray(data.signals)) {
                        isEnabled = data.signals.includes(key);
                    } else if (typeof data.signals === 'object') {
                        const sig = data.signals[key];
                        if (sig === true) {
                            isEnabled = true;
                        } else if (sig && typeof sig === 'object') {
                            isEnabled = sig.enabled !== false;
                            const metaEl = item.querySelector('.signal-meta');
                            const metaKey = metaEl ? metaEl.getAttribute('data-meta-key') : null;
                            if (metaKey && sig[metaKey] !== undefined) {
                                metaVal = sig[metaKey];
                            }
                        } else if (sig) {
                            isEnabled = true;
                        }
                    }

                    checkbox.checked = isEnabled;
                    if (isEnabled) {
                        item.classList.remove('opacity-75');
                        activeCount++;
                    } else {
                        item.classList.add('opacity-75');
                    }

                    if (metaVal !== null) {
                        const metaEl = item.querySelector('.signal-meta');
                        if (metaEl) {
                            metaEl.textContent = metaVal;
                        }
                    }
                });
                updateSignalsBadge(activeCount);
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

    if (returnUrl) {
        // Edit mode adjustments
        const exitLink = document.querySelector('header a[data-path="dashboard"]');
        if (exitLink) {
            const labelSpan = exitLink.querySelector('span:last-child');
            if (labelSpan) {
                labelSpan.textContent = 'Back to Profile Optimization';
            }
        }

        if (btnFinalize) {
            const spanText = btnFinalize.querySelector('span:first-child');
            if (spanText) {
                spanText.textContent = 'Save & Return to Profile';
            }
        }

        const btnSaveReturnDirect = document.getElementById('btn-save-return-direct');
        if (btnSaveReturnDirect) {
            btnSaveReturnDirect.classList.remove('hidden');
            btnSaveReturnDirect.addEventListener('click', async (e) => {
                e.preventDefault();
                await submitICP({ button: btnSaveReturnDirect, finalize: true });
            });
        }
    }
});
