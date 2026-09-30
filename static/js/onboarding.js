
document.addEventListener('DOMContentLoaded', () => {
    // CSRF token
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    
    // --- COMPANY SETUP ---
    const formCompany = document.getElementById('form-onboarding-company');
    const modalCompany = document.getElementById('modal-onboarding-company');
    const modalIcp = document.getElementById('modal-onboarding-icp');
    const errCompany = document.getElementById('ob-company-error');
    
    if (formCompany) {
        formCompany.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('ob-company-save-btn');
            btn.disabled = true;
            if(errCompany) errCompany.classList.add('hidden');
            
            const payload = {
                company_name: document.getElementById('ob-company-name')?.value || '',
                website_url: document.getElementById('ob-company-website')?.value || '',
                description: document.getElementById('ob-company-desc')?.value || '',
                what_company_sells: document.getElementById('ob-company-sells')?.value || '',
                products_services: document.getElementById('ob-company-products')?.value || '',
                industry: document.getElementById('ob-company-industry')?.value || '',
                company_size: document.getElementById('ob-company-size')?.value || '',
                revenue: document.getElementById('ob-company-revenue')?.value || '',
                location: document.getElementById('ob-company-location')?.value || ''
            };
            
            try {
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
                    throw new Error(data.message || 'Unable to save company details. Please try again.');
                }
                
                // Hide company modal, show ICP modal
                if(modalCompany) modalCompany.classList.add('hidden');
                if(modalIcp) modalIcp.classList.remove('hidden');
                
            } catch (err) {
                if(errCompany) {
                    errCompany.textContent = err.message;
                    errCompany.classList.remove('hidden');
                } else {
                    alert(err.message);
                }
            } finally {
                btn.disabled = false;
            }
        });
    }

    // --- ICP SETUP ---
    const formIcp = document.getElementById('form-onboarding-icp');
    const errIcp = document.getElementById('ob-icp-error');
    
    if (formIcp) {
        formIcp.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('ob-icp-save-btn');
            btn.disabled = true;
            if(errIcp) errIcp.classList.add('hidden');
            
            const payload = {
                target_customer: document.getElementById('ob-icp-target')?.value || '',
                company_size: document.getElementById('ob-icp-size')?.value || '',
                revenue_range: document.getElementById('ob-icp-revenue')?.value || '',
                target_jobs_roles: document.getElementById('ob-icp-roles')?.value || '',
                industry: document.getElementById('ob-icp-industry')?.value || '',
                location: document.getElementById('ob-icp-location')?.value || '',
                tone: document.getElementById('ob-icp-tone')?.value || 'FORMAL'
            };
            
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
                    throw new Error(data.message || 'Unable to save ICP details. Please try again.');
                }
                
                // Done onboarding -> reload or switch tab
                window.location.reload();
                
            } catch (err) {
                if(errIcp) {
                    errIcp.textContent = err.message;
                    errIcp.classList.remove('hidden');
                } else {
                    alert(err.message);
                }
            } finally {
                btn.disabled = false;
            }
        });
    }
});
