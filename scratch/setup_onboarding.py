import os
import re

# 1. Patch icp.html
with open('templates/icp.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Revenue Select
html = html.replace(
    '<select class="w-full bg-surface-container-low text-on-surface font-body-md text-body-md rounded-lg p-space-md appearance-none focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow">',
    '<select id="icp-revenue" class="w-full bg-surface-container-low text-on-surface font-body-md text-body-md rounded-lg p-space-md appearance-none focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow">'
)

# Tone Select
html = html.replace(
    '<select class="w-full bg-surface-container-low text-on-surface font-body-md text-body-md rounded-lg p-space-md appearance-none focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow">\n<option selected="">FORMAL',
    '<select id="icp-tone" class="w-full bg-surface-container-low text-on-surface font-body-md text-body-md rounded-lg p-space-md appearance-none focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow">\n<option selected="">FORMAL'
)

# Location Input (Look for the placeholder "e.g., North America (NAM), EMEA...")
html = html.replace(
    '<input class="w-full bg-surface-container-low text-on-surface font-body-md text-body-md rounded-lg px-space-md py-3 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow" placeholder="e.g., North America (NAM), EMEA, or specific cities/states" type="text"/>',
    '<input id="icp-location" class="w-full bg-surface-container-low text-on-surface font-body-md text-body-md rounded-lg px-space-md py-3 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow" placeholder="e.g., North America (NAM), EMEA, or specific cities/states" type="text"/>'
)

# And make sure it is injected with scripts
if '</body>' in html and 'static/js/onboarding_new/icp.js' not in html:
    html = html.replace('</body>', '<script src="/static/js/onboarding_new/icp.js"></script>\n</body>')

with open('templates/icp.html', 'w', encoding='utf-8') as f:
    f.write(html)


# 2. Patch companydetails.html
with open('templates/companydetails.html', 'r', encoding='utf-8') as f:
    html = f.read()

if '</body>' in html and 'static/js/onboarding_new/company.js' not in html:
    html = html.replace('</body>', '<script src="/static/js/onboarding_new/company.js"></script>\n</body>')
    
with open('templates/companydetails.html', 'w', encoding='utf-8') as f:
    f.write(html)


# 3. Create company.js
company_js = """document.addEventListener('DOMContentLoaded', () => {
    const btnContinue = document.getElementById('btn-continue');
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    
    if (btnContinue) {
        btnContinue.addEventListener('click', async (e) => {
            e.preventDefault();
            btnContinue.style.pointerEvents = 'none';
            btnContinue.style.opacity = '0.7';
            
            const payload = {
                company_name: document.getElementById('comp-name')?.value || '',
                website_url: document.getElementById('comp-web')?.value || '',
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
                btnContinue.style.opacity = '1';
            }
        });
    }
});
"""

# 4. Create icp.js
icp_js = """document.addEventListener('DOMContentLoaded', () => {
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const btnSubmit = document.getElementById('btn-submit-icp');
    const btnProceed = document.getElementById('btn-proceed-from-preview');

    const submitICP = async () => {
        // Extract values using basic DOM queries since stitch UI doesn't have inputs for everything
        const targetCustomer = "B2B SaaS Companies, Mid-Market Growth Teams"; // Dummy or parsed
        const size = "11-50, 51-200"; // Dummy
        const rev = document.getElementById('icp-revenue')?.value || '';
        const roles = "VP Sales, CRO";
        const ind = "FinTech, SaaS";
        const loc = document.getElementById('icp-location')?.value || '';
        const tone = document.getElementById('icp-tone')?.value || 'FORMAL';

        const payload = {
            target_customer: targetCustomer,
            company_size: size,
            revenue_range: rev,
            target_jobs_roles: roles,
            industry: ind,
            location: loc,
            tone: tone
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
                throw new Error(data.message || 'Unable to save ICP details.');
            }
            
            // For now, since stitch has a review step in icp.html, we just show it or proceed
            document.getElementById('questionnaire-view')?.classList.add('hidden');
            document.getElementById('preview-view')?.classList.remove('hidden');
            
        } catch (err) {
            alert(err.message);
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
});
"""

os.makedirs('static/js/onboarding_new', exist_ok=True)
with open('static/js/onboarding_new/company.js', 'w', encoding='utf-8') as f:
    f.write(company_js)
    
with open('static/js/onboarding_new/icp.js', 'w', encoding='utf-8') as f:
    f.write(icp_js)

print("Created onboarding scripts and patched templates.")
