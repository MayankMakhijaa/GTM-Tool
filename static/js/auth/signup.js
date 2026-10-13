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
    
    // Determine submit button (it might not have an id, but it's the only submit button in form)
    const submitBtn = signupForm ? signupForm.querySelector('button[type="submit"]') : null;

    // CSRF token
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

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

    // Password Strength Indicator
    const strengthBars = [
        document.getElementById('strength-bar-1'),
        document.getElementById('strength-bar-2'),
        document.getElementById('strength-bar-3'),
        document.getElementById('strength-bar-4')
    ];
    const strengthText = document.getElementById('strength-text');
    
    if (passwordInput && strengthBars[0] && strengthText) {
        passwordInput.addEventListener('input', () => {
            const val = passwordInput.value;
            let activeBars = 0;
            let barColor = 'bg-surface-container-high';
            let msg = 'Strength: Needs 8+ chars';
            
            if (val.length > 0 && val.length < 8) {
                activeBars = 2; // Show something so they know it's working
                barColor = 'bg-error'; // Red
                msg = 'Strength: Too short';
            } else if (val.length >= 8) {
                activeBars = 4; // All met
                barColor = 'bg-tertiary'; // Green
                msg = 'Strength: Valid (8+ chars)';
            }
            
            strengthBars.forEach((bar, index) => {
                if (!bar) return;
                // Reset classes
                bar.classList.remove('bg-surface-container-high', 'bg-error', 'bg-tertiary');
                if (index < activeBars) {
                    bar.classList.add(barColor);
                } else {
                    bar.classList.add('bg-surface-container-high');
                }
            });
            strengthText.textContent = msg;
        });
    }

    const connectLinkedinBtn = document.getElementById('connect-linkedin-btn');
    const linkedinStatusText = document.getElementById('linkedin-status-text');

    const updateSubmitState = () => {
        const name = nameInput?.value?.trim() || '';
        const email = emailInput?.value?.trim() || '';
        const password = passwordInput?.value || '';
        const isValid = name.length > 0 && email.length > 0 && password.length >= 8;

        if (submitBtn) {
            submitBtn.disabled = !isValid;
            if (isValid) {
                submitBtn.className = 'w-full mt-2 py-3 px-space-md bg-primary-container hover:bg-secondary text-on-primary font-label-md text-label-md font-semibold rounded-lg shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 group cursor-pointer';
            } else {
                submitBtn.className = 'w-full mt-2 py-3 px-space-md bg-surface-container-high text-outline font-label-md text-label-md font-semibold rounded-lg transition-all flex items-center justify-center gap-2 cursor-not-allowed';
            }
        }
    };

    nameInput?.addEventListener('input', updateSubmitState);
    emailInput?.addEventListener('input', updateSubmitState);
    passwordInput?.addEventListener('input', updateSubmitState);

    if (connectLinkedinBtn) {
        connectLinkedinBtn.addEventListener('click', () => {
            alert('Your LinkedIn account will be securely connected during onboarding right after creating your account.');
        });
    }

    if (signupForm) {
        signupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = nameInput?.value || '';
            const email = emailInput?.value || '';
            const phoneVal = phoneInput?.value || '';
            const code = selectedCode?.textContent || '+1';
            const phone = code + phoneVal.replace(/[^0-9]/g, '');
            const password = passwordInput?.value || '';

            if (!name || !email || !password || password.length < 8) return;

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
                    body: JSON.stringify({ name, email, phone, password })
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
                    window.location.href = '/connect-linkedin';
                } else {
                    throw new Error(data.message || 'Error signing up');
                }
            } catch (err) {
                alert(err.message || 'A network error occurred. Please try again.');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;
                }
            }
        });
    }
});
