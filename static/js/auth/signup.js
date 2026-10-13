document.addEventListener('DOMContentLoaded', () => {
    const signupForm = document.getElementById('signup-form');
    const nameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('businessEmail');
    const phoneInput = document.getElementById('phoneNumber');
    const passwordInput = document.getElementById('passwordField');
    const selectedCode = document.getElementById('selectedCode');
    const countryDropdownBtn = document.getElementById('countryDropdownBtn');
    const countryMenu = document.getElementById('countryMenu');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const togglePasswordIcon = document.getElementById('togglePasswordIcon');

    // Submit button
    const submitBtn = document.getElementById('signupSubmitBtn') || (signupForm ? signupForm.querySelector('button[type="submit"]') : null);

    // Email feedback elements
    const emailMsgContainer = document.getElementById('email-feedback-msg');
    const emailIcon = document.getElementById('email-feedback-icon');
    const emailText = document.getElementById('email-feedback-text');

    // CSRF token
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    // Disallowed personal/free email provider domains
    const DISALLOWED_PERSONAL_EMAIL_DOMAINS = new Set([
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.ca", "yahoo.com.br",
        "outlook.com", "hotmail.com", "live.com", "msn.com", "passport.com",
        "icloud.com", "me.com", "mac.com",
        "aol.com", "aim.com",
        "proton.me", "protonmail.com", "protonmail.ch",
        "zoho.com", "zohomail.com",
        "mail.com", "gmx.com", "gmx.net",
        "yandex.com", "yandex.ru", "mail.ru",
        "comcast.net", "sbcglobal.net", "verizon.net", "cox.net", "rediffmail.com"
    ]);

    // Toggle country menu
    if (countryDropdownBtn && countryMenu) {
        countryDropdownBtn.addEventListener('click', () => {
            countryMenu.classList.toggle('hidden');
        });

        // Hide on click outside
        document.addEventListener('click', (e) => {
            if (!countryDropdownBtn.contains(e.target) && !countryMenu.contains(e.target)) {
                countryMenu.classList.add('hidden');
            }
        });
    }

    // Show/Hide password
    if (togglePasswordBtn && passwordInput && togglePasswordIcon) {
        togglePasswordBtn.addEventListener('click', () => {
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                togglePasswordIcon.textContent = 'visibility_off';
            } else {
                passwordInput.type = 'password';
                togglePasswordIcon.textContent = 'visibility';
            }
        });
    }

    // Password Strength & Real-Time Requirements Checklist
    const strengthBars = [
        document.getElementById('strength-bar-1'),
        document.getElementById('strength-bar-2'),
        document.getElementById('strength-bar-3'),
        document.getElementById('strength-bar-4')
    ];
    const strengthText = document.getElementById('strength-text');
    const strengthBadge = document.getElementById('strength-status-badge');

    const rules = {
        length: { el: document.getElementById('req-length'), icon: document.getElementById('req-length-icon'), test: (v) => v.length >= 9 },
        uppercase: { el: document.getElementById('req-uppercase'), icon: document.getElementById('req-uppercase-icon'), test: (v) => /[A-Z]/.test(v) },
        lowercase: { el: document.getElementById('req-lowercase'), icon: document.getElementById('req-lowercase-icon'), test: (v) => /[a-z]/.test(v) },
        number: { el: document.getElementById('req-number'), icon: document.getElementById('req-number-icon'), test: (v) => /[0-9]/.test(v) },
        special: { el: document.getElementById('req-special'), icon: document.getElementById('req-special-icon'), test: (v) => /[^A-Za-z0-9]/.test(v) }
    };

    let isPasswordValid = false;
    let isEmailValid = false;

    const updatePasswordChecklist = (val) => {
        let metCount = 0;

        Object.keys(rules).forEach((key) => {
            const rule = rules[key];
            if (!rule.el || !rule.icon) return;

            const isMet = val ? rule.test(val) : false;
            if (isMet) {
                metCount++;
                rule.el.className = 'flex items-center gap-1 transition-colors text-tertiary font-medium';
                rule.icon.textContent = 'check_circle';
            } else {
                rule.el.className = 'flex items-center gap-1 transition-colors text-outline';
                rule.icon.textContent = 'radio_button_unchecked';
            }
        });

        if (strengthBadge) {
            strengthBadge.textContent = `${metCount} / 5 Rules`;
            strengthBadge.className = metCount === 5 ? 'font-code-sm text-code-sm text-tertiary font-bold' : 'font-code-sm text-code-sm text-outline';
        }

        let activeBars = 0;
        let barColor = 'bg-surface-container-high';
        let msg = 'Strength: Enter password';

        if (!val) {
            activeBars = 0;
            msg = 'Strength: Enter password';
        } else if (metCount <= 2) {
            activeBars = 1;
            barColor = 'bg-error';
            msg = 'Strength: Weak';
        } else if (metCount === 3) {
            activeBars = 2;
            barColor = 'bg-amber-500';
            msg = 'Strength: Fair';
        } else if (metCount === 4) {
            activeBars = 3;
            barColor = 'bg-secondary';
            msg = 'Strength: Good';
        } else if (metCount === 5) {
            activeBars = 4;
            barColor = 'bg-tertiary';
            msg = 'Strength: Valid (All requirements met)';
        }

        strengthBars.forEach((bar, index) => {
            if (!bar) return;
            bar.classList.remove('bg-surface-container-high', 'bg-error', 'bg-amber-500', 'bg-secondary', 'bg-tertiary');
            if (index < activeBars) {
                bar.classList.add(barColor);
            } else {
                bar.classList.add('bg-surface-container-high');
            }
        });

        if (strengthText) {
            strengthText.textContent = msg;
        }

        isPasswordValid = metCount === 5;
        return isPasswordValid;
    };

    // Real-Time Business Email Validation
    const validateEmailInput = () => {
        if (!emailInput) return false;

        const rawVal = emailInput.value || '';
        const email = rawVal.trim().toLowerCase();

        // Default neutral state
        if (!email) {
            if (emailText) emailText.textContent = 'Please use your work email domain for organization verification.';
            if (emailIcon) {
                emailIcon.classList.add('hidden');
                emailIcon.textContent = 'error';
                emailIcon.className = 'material-symbols-outlined text-[14px] hidden';
            }
            if (emailMsgContainer) {
                emailMsgContainer.className = 'font-body-sm text-body-sm text-on-surface-variant/80 pl-1 flex items-center gap-1 transition-colors';
            }
            emailInput.classList.remove('border-error', 'border-tertiary', 'border');
            isEmailValid = false;
            return false;
        }

        // Email format check regex
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            if (emailText) emailText.textContent = 'Please enter a valid email address (e.g. alex@company.com).';
            if (emailIcon) {
                emailIcon.classList.remove('hidden');
                emailIcon.textContent = 'error';
                emailIcon.className = 'material-symbols-outlined text-[14px] text-error';
            }
            if (emailMsgContainer) {
                emailMsgContainer.className = 'font-body-sm text-body-sm text-error pl-1 flex items-center gap-1 transition-colors';
            }
            emailInput.classList.remove('border-tertiary');
            emailInput.classList.add('border', 'border-error');
            isEmailValid = false;
            return false;
        }

        // Extract domain and check blocklist
        const domain = email.split('@').pop().toLowerCase();
        if (DISALLOWED_PERSONAL_EMAIL_DOMAINS.has(domain)) {
            if (emailText) emailText.textContent = `Personal email providers (${domain}) are not allowed. Please use your business email.`;
            if (emailIcon) {
                emailIcon.classList.remove('hidden');
                emailIcon.textContent = 'error';
                emailIcon.className = 'material-symbols-outlined text-[14px] text-error';
            }
            if (emailMsgContainer) {
                emailMsgContainer.className = 'font-body-sm text-body-sm text-error pl-1 flex items-center gap-1 transition-colors';
            }
            emailInput.classList.remove('border-tertiary');
            emailInput.classList.add('border', 'border-error');
            isEmailValid = false;
            return false;
        }

        // Valid business email
        if (emailText) emailText.textContent = 'Business email domain verified.';
        if (emailIcon) {
            emailIcon.classList.remove('hidden');
            emailIcon.textContent = 'check_circle';
            emailIcon.className = 'material-symbols-outlined text-[14px] text-tertiary';
        }
        if (emailMsgContainer) {
            emailMsgContainer.className = 'font-body-sm text-body-sm text-tertiary font-medium pl-1 flex items-center gap-1 transition-colors';
        }
        emailInput.classList.remove('border-error');
        emailInput.classList.add('border', 'border-tertiary');
        isEmailValid = true;
        return true;
    };

    // Update Create Account Submit Button state
    const updateSubmitButtonState = () => {
        if (!submitBtn) return;
        const isNameFilled = nameInput ? Boolean(nameInput.value.trim()) : false;
        const isPhoneFilled = phoneInput ? Boolean(phoneInput.value.trim()) : false;

        const canSubmit = isEmailValid && isPasswordValid && isNameFilled && isPhoneFilled;
        submitBtn.disabled = !canSubmit;
    };

    // Event listeners for Email with 250ms Debounce
    let emailDebounceTimer = null;
    if (emailInput) {
        emailInput.addEventListener('input', () => {
            clearTimeout(emailDebounceTimer);
            emailDebounceTimer = setTimeout(() => {
                validateEmailInput();
                updateSubmitButtonState();
            }, 250);
        });

        emailInput.addEventListener('blur', () => {
            clearTimeout(emailDebounceTimer);
            validateEmailInput();
            updateSubmitButtonState();
        });
    }

    if (passwordInput) {
        passwordInput.addEventListener('input', () => {
            updatePasswordChecklist(passwordInput.value);
            updateSubmitButtonState();
        });
    }

    if (nameInput) {
        nameInput.addEventListener('input', () => {
            updateSubmitButtonState();
        });
    }

    if (phoneInput) {
        phoneInput.addEventListener('input', () => {
            updateSubmitButtonState();
        });
    }

    // Initial check on load
    if (passwordInput) updatePasswordChecklist(passwordInput.value);
    validateEmailInput();
    updateSubmitButtonState();

    if (signupForm) {
        signupForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Revalidate everything on submit
            const emailOk = validateEmailInput();
            const passwordOk = updatePasswordChecklist(passwordInput?.value || '');
            const nameVal = nameInput?.value.trim() || '';
            const phoneVal = phoneInput?.value.trim() || '';

            if (!emailOk || !passwordOk || !nameVal || !phoneVal) {
                updateSubmitButtonState();
                return;
            }

            const code = selectedCode?.textContent || '+91';
            const phone = code + phoneVal.replace(/[^0-9]/g, '');
            const password = passwordInput?.value || '';

            // Loading state
            let originalBtnText = 'Create Account';
            if (submitBtn) {
                originalBtnText = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Creating account...</span>';
            }

            try {
                const res = await fetch('/api/auth/signup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ name: nameVal, email: emailInput.value.trim().toLowerCase(), phone, password })
                });

                let data;
                const contentType = res.headers.get("content-type");
                if (contentType && contentType.includes("application/json")) {
                    data = await res.json();
                } else {
                    const text = await res.text();
                    console.error("Non-JSON Auth API error:", res.status, text);
                    throw new Error(`Unexpected server response (${res.status})`);
                }

                if (res.ok && data.success) {
                    if (data.requires_verification) {
                        const emailForVerify = data.email || emailInput.value.trim().toLowerCase();
                        sessionStorage.setItem('fameweb_pending_verification_email', emailForVerify);
                        window.location.href = `/verify-email?email=${encodeURIComponent(emailForVerify)}`;
                        return;
                    }
                    window.location.href = '/dashboard';
                } else {
                    throw new Error(data.message || 'Error signing up');
                }
            } catch (err) {
                alert(err.message || 'A network error occurred. Please try again.');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;
                    updateSubmitButtonState();
                }
            }
        });
    }
});
