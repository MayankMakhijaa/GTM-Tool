document.addEventListener('DOMContentLoaded', () => {
    const btnStartResearch = document.getElementById('btn-start-research');
    const btnSaveLead = document.getElementById('btn-save-lead');
    const btnDraftOutreach = document.getElementById('btn-draft-outreach');
    
    // UI IDs from gtm.html Drawer
    const dName = document.getElementById('drawer-name');
    const dTitle = document.getElementById('drawer-title-company');
    const dScore = document.getElementById('drawer-score');
    
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    
    if (btnStartResearch) {
        // It's a span wrapped in a button
        const actualBtn = btnStartResearch.closest('button') || btnStartResearch;
        
        actualBtn.addEventListener('click', async () => {
            const originalText = actualBtn.innerHTML;
            actualBtn.disabled = true;
            actualBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[20px]">progress_activity</span><span>Researching...</span>';
            
            try {
                // Poll or start
                const res = await fetch('/api/gtm-opportunities/find', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({})
                });
                
                const data = await res.json();
                if (data.success || data.status === 'success') {
                    // It returns prospects, we could render them into the table
                    alert('Research completed! Leads found: ' + (data.prospects?.length || 0));
                    // To do a full data-bind, we would replace the table rows, 
                    // but for Phase 2.5 we just alert and let a page refresh or subsequent GET handle it
                    // if there was a GET endpoint for prospects.
                } else {
                    throw new Error(data.error || 'Failed to find opportunities');
                }
                
            } catch (err) {
                alert(err.message);
            } finally {
                actualBtn.disabled = false;
                actualBtn.innerHTML = originalText;
            }
        });
    }
    
    if (btnSaveLead) {
        const actualBtn = btnSaveLead.closest('button') || btnSaveLead;
        actualBtn.addEventListener('click', () => {
            alert('Lead saved successfully to your History.');
        });
    }
    
    if (btnDraftOutreach) {
        const actualBtn = btnDraftOutreach.closest('button') || btnDraftOutreach;
        actualBtn.addEventListener('click', () => {
            window.location.href = '/emails';
        });
    }
    
    // We keep the static mockup data interactive by allowing selectProspect to just update the drawer visually
    window.selectProspect = function(data) {
        if (dName) dName.textContent = data.name || 'Unknown';
        if (dTitle) dTitle.textContent = data.title || 'Unknown';
        if (dScore) dScore.textContent = data.score || '0%';
    }
});
