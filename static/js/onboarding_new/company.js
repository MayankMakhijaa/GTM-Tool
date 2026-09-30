document.addEventListener('DOMContentLoaded', async () => {
    const btnContinue = document.getElementById('btn-continue');
    const fetchButton = document.getElementById('fetch-button');
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    
    // Fetch existing company details
    try {
        const res = await fetch('/api/onboarding/company');
        if (res.ok) {
            const result = await res.json();
            if (result.success && result.data && Object.keys(result.data).length > 0) {
                const data = result.data;
                const el = (id) => document.getElementById(id);
                if (el('comp-name')) el('comp-name').value = data.company_name || '';
                if (el('comp-web')) el('comp-web').value = data.website_url || '';
                if (el('comp-desc')) el('comp-desc').value = data.description || '';
                if (el('comp-sells')) el('comp-sells').value = data.what_company_sells || '';
                if (el('comp-ind')) el('comp-ind').value = data.industry || '';
                if (el('comp-size')) el('comp-size').value = data.company_size || '';
                if (el('comp-rev')) el('comp-rev').value = data.revenue || '';
                if (el('comp-loc')) el('comp-loc').value = data.location || '';
                
                // If website_url exists, populate the top input
                if (el('company-url-input')) el('company-url-input').value = data.website_url || '';
            }
        }
    } catch (err) {
        console.error('Error fetching company details', err);
    }

    if (fetchButton) {
        fetchButton.addEventListener('click', () => {
            alert("Automated company scraping is currently in development. Please enter details manually.");
        });
    }

    if (btnContinue) {
        btnContinue.addEventListener('click', async (e) => {
            e.preventDefault();
            const originalText = btnContinue.innerHTML;
            btnContinue.style.pointerEvents = 'none';
            btnContinue.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Saving...</span>';
            
            const payload = {
                company_name: document.getElementById('comp-name')?.value || '',
                website_url: document.getElementById('comp-web')?.value || document.getElementById('company-url-input')?.value || '',
                description: document.getElementById('comp-desc')?.value || '',
                what_company_sells: document.getElementById('comp-sells')?.value || '',
                industry: document.getElementById('comp-ind')?.value || '',
                company_size: document.getElementById('comp-size')?.value || '',
                revenue: document.getElementById('comp-rev')?.value || '',
                location: document.getElementById('comp-loc')?.value || ''
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
                    throw new Error(data.message || 'Unable to save company details.');
                }
                
                // Continue to ICP
                window.location.href = '/icp';
            } catch (err) {
                alert(err.message);
                btnContinue.style.pointerEvents = 'auto';
                btnContinue.innerHTML = originalText;
            }
        });
    }
});
