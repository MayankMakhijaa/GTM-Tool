document.addEventListener('DOMContentLoaded', async () => {
    let leadsData = [];
    let activeLeadId = null;
    let currentMode = 'template';
    
    const leadListContainer = document.getElementById('lead-list-container');
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    
    // UI elements
    const selectedPill = document.getElementById('selected-pill');
    const btnSelectedCount = document.getElementById('btn-selected-count');
    const selectAllCb = document.getElementById('select-all-checkbox');
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    window.showToast = function(text) {
        if (!toast) return alert(text);
        toastMessage.textContent = text;
        toast.classList.remove('translate-y-16', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
        setTimeout(() => {
            toast.classList.remove('translate-y-0', 'opacity-100');
            toast.classList.add('translate-y-16', 'opacity-0');
        }, 2500);
    };

    // Load leads
    try {
        const res = await fetch('/api/email-leads');
        const data = await res.json();
        if (data.success && data.leads) {
            leadsData = data.leads;
            renderLeads();
        }
    } catch (err) {
        console.error("Error loading leads", err);
    }
    
    function renderLeads() {
        if (!leadListContainer) return;
        leadListContainer.innerHTML = '';
        if (leadsData.length === 0) {
            leadListContainer.innerHTML = '<div class="p-4 text-center text-on-surface-variant text-sm">No email-qualified leads available. Run GTM Research first.</div>';
            return;
        }
        
        leadsData.forEach((lead, index) => {
            const div = document.createElement('div');
            div.className = `lead-item group p-space-md rounded-lg bg-surface-container-low hover:bg-surface-container transition-all cursor-pointer flex flex-col gap-space-xs ${index === 0 ? 'active-preview bg-surface-container-highest shadow-sm' : ''}`;
            div.setAttribute('data-lead-index', index);
            div.onclick = (e) => previewLead(index, e);
            
            div.innerHTML = `
                <div class="flex items-start justify-between gap-space-sm">
                  <div class="flex items-start gap-space-sm min-w-0">
                    <input type="checkbox" class="lead-checkbox mt-1 w-4 h-4 rounded text-primary accent-primary cursor-pointer" onchange="handleLeadCheckbox(event)" checked>
                    <div class="flex flex-col min-w-0">
                      <div class="flex items-center gap-space-xs">
                        <span class="font-label-md text-label-md text-on-surface font-semibold truncate">${lead.first_name || ''} ${lead.last_name || ''}</span>
                        <span class="font-body-sm text-body-sm text-on-surface-variant">·</span>
                        <span class="font-body-sm text-body-sm text-on-surface-variant truncate">${lead.company || 'Unknown Company'}</span>
                      </div>
                      <span class="font-code-sm text-code-sm text-primary">${lead.email || 'No email'}</span>
                    </div>
                  </div>
                  <span class="px-2 py-0.5 rounded-full bg-tertiary/10 text-tertiary font-label-sm text-label-sm shrink-0">
                    Fit: ${lead.overall_score || 0}%
                  </span>
                </div>
            `;
            leadListContainer.appendChild(div);
        });
        
        activeLeadId = 0;
        updateSelectionCounts();
        updatePreview();
    }

    window.previewLead = function(index, event) {
        if (event && event.target.tagName.toLowerCase() === 'input') return;
        activeLeadId = index;
        document.querySelectorAll('.lead-item').forEach(el => {
            el.classList.remove('bg-surface-container-highest', 'shadow-sm');
            el.classList.add('bg-surface-container-low');
        });
        const activeEl = document.querySelector(`[data-lead-index="${index}"]`);
        if (activeEl) {
            activeEl.classList.remove('bg-surface-container-low');
            activeEl.classList.add('bg-surface-container-highest', 'shadow-sm');
        }
        updatePreview();
    };

    window.handleLeadCheckbox = function(e) {
        e.stopPropagation();
        updateSelectionCounts();
    };

    window.toggleSelectAll = function(masterCheckbox) {
        document.querySelectorAll('.lead-checkbox').forEach(cb => cb.checked = masterCheckbox.checked);
        updateSelectionCounts();
    };

    function updateSelectionCounts() {
        const checkboxes = document.querySelectorAll('.lead-checkbox');
        const checked = Array.from(checkboxes).filter(cb => cb.checked).length;
        if (selectedPill) selectedPill.textContent = `${checked} recipient${checked === 1 ? '' : 's'} selected`;
        if (btnSelectedCount) btnSelectedCount.textContent = checked;
        
        if (selectAllCb) {
            selectAllCb.checked = checkboxes.length > 0 && checked === checkboxes.length;
            selectAllCb.indeterminate = checked > 0 && checked < checkboxes.length;
        }
    }

    window.setMode = function(mode) {
        currentMode = mode;
        const singleBtn = document.getElementById("mode-single-btn");
        const templateBtn = document.getElementById("mode-template-btn");
        
        if (!singleBtn || !templateBtn) return;
        if (mode === 'single') {
            singleBtn.className = "px-space-md py-1.5 rounded-lg font-label-md text-label-md bg-surface-container-lowest text-primary shadow-sm font-semibold transition-all";
            templateBtn.className = "px-space-md py-1.5 rounded-lg font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors";
            switchViewTab('preview');
        } else {
            templateBtn.className = "px-space-md py-1.5 rounded-lg font-label-md text-label-md bg-surface-container-lowest text-primary shadow-sm font-semibold transition-all";
            singleBtn.className = "px-space-md py-1.5 rounded-lg font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors";
            switchViewTab('compose');
        }
    };

    window.switchViewTab = function(tab) {
        const composePanel = document.getElementById('composer-mode-panel');
        const previewPanel = document.getElementById('preview-mode-panel');
        const tabCompose = document.getElementById('tab-compose');
        const tabPreview = document.getElementById('tab-preview');
        
        if (!composePanel || !previewPanel) return;
        
        if (tab === 'compose') {
            composePanel.classList.remove('hidden');
            previewPanel.classList.add('hidden');
            if (tabCompose) tabCompose.className = "px-3 py-1 rounded-lg font-label-sm text-label-sm bg-primary text-on-primary transition-all";
            if (tabPreview) tabPreview.className = "px-3 py-1 rounded-lg font-label-sm text-label-sm text-on-surface-variant hover:bg-surface-container transition-all";
        } else {
            composePanel.classList.add('hidden');
            previewPanel.classList.remove('hidden');
            if (tabPreview) tabPreview.className = "px-3 py-1 rounded-lg font-label-sm text-label-sm bg-primary text-on-primary transition-all";
            if (tabCompose) tabCompose.className = "px-3 py-1 rounded-lg font-label-sm text-label-sm text-on-surface-variant hover:bg-surface-container transition-all";
            updatePreview();
        }
    };

    window.insertToken = function(tokenName) {
        const editor = document.getElementById('email-editor');
        if (!editor) return;
        
        // We insert the raw placeholder string
        const placeholder = `{{${tokenName.toLowerCase().replace(/ /g, '_')}}}`;
        const textNode = document.createTextNode(placeholder);
        
        editor.focus();
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            range.deleteContents();
            range.insertNode(textNode);
            range.collapse(false);
        } else {
            editor.appendChild(textNode);
        }
        showToast(`Inserted token: ${placeholder}`);
        updatePreview();
    };

    function processTemplate(template, lead) {
        if (!lead) return template;
        const name = (lead.first_name || lead.name || 'there').split(' ')[0];
        const company = lead.company || 'your company';
        const role = lead.title || 'your role';
        
        return template
            .replace(/\{\{first_name\}\}/g, name)
            .replace(/\{\{full_name\}\}/g, lead.name || name)
            .replace(/\{\{company_name\}\}/g, company)
            .replace(/\{\{role\}\}/g, role)
            .replace(/\{\{business_need\}\}/g, 'sales optimization')
            .replace(/\{\{lead_score\}\}/g, lead.overall_score || '')
            .replace(/\{\{reason\}\}/g, lead.reason || '')
            .replace(/\{\{email\}\}/g, lead.email || '')
            .replace(/\{\{result_metric\}\}/g, '30%')
            .replace(/\{\{sender_name\}\}/g, 'Sarah Jenkins')
            .replace(/\{\{sender_role\}\}/g, 'Head of Growth')
            .replace(/\{\{sender_link\}\}/g, 'fameweb.ai');
    }

    function updatePreview() {
        const lead = leadsData[activeLeadId];
        if (!lead) return;
        
        const subjInp = document.getElementById('subject-tail');
        const editor = document.getElementById('email-editor');
        if (!subjInp || !editor) return;

        const rawSubj = subjInp.value || 'Quick idea for {{company_name}}';
        const rawBody = editor.innerText;
        
        const previewSubj = processTemplate(rawSubj, lead);
        const previewBody = processTemplate(rawBody, lead).replace(/\n/g, '<br>');

        document.getElementById('preview-lead-heading').textContent = `${lead.first_name || 'Prospect'} @ ${lead.company || 'Company'}`;
        document.getElementById('preview-lead-email').textContent = lead.email || 'No email';
        document.getElementById('preview-subject-text').textContent = previewSubj;
        document.getElementById('preview-body-content').innerHTML = previewBody;
    }

    window.saveDraft = function() {
        showToast("Outreach template & recipients saved.");
    };

    window.triggerMailtoCampaign = function() {
        const checkboxes = document.querySelectorAll('.lead-checkbox');
        const selectedEmails = [];
        checkboxes.forEach((cb, index) => {
            if (cb.checked && leadsData[index]) {
                selectedEmails.push(leadsData[index].email);
            }
        });

        if (selectedEmails.length === 0) {
            showToast("Please select at least one recipient lead.");
            return;
        }

        const subjInp = document.getElementById('subject-tail');
        const editor = document.getElementById('email-editor');
        const rawSubj = subjInp.value || 'Quick idea for {{company_name}}';
        const rawBody = editor.innerText;

        // Note: mailto only really works well for a single generic template or BCC.
        // We'll process it for the first lead as a fallback, but BCC gets the generic.
        const lead = leadsData[activeLeadId] || leadsData[0];
        const subject = encodeURIComponent(processTemplate(rawSubj, lead));
        const body = encodeURIComponent(processTemplate(rawBody, lead));

        const recipient = selectedEmails[0];
        const bcc = selectedEmails.slice(1).join(',');
        const mailtoUrl = `mailto:${recipient}?${bcc ? 'bcc=' + bcc + '&' : ''}subject=${subject}&body=${body}`;

        showToast(`Generating Mailto link for ${selectedEmails.length} recipients...`);
        setTimeout(() => {
            window.location.href = mailtoUrl;
        }, 500);
    };

    // Initialize with default template text on compose window
    const editor = document.getElementById('email-editor');
    if (editor && !editor.innerText.trim()) {
        editor.innerText = 
`Hi {{first_name}},

Noticed {{company_name}} has been scaling {{business_need}} lately — congrats on the growth.

Usually at that stage, teams start missing leads simply because there aren't enough hours to follow up with everyone fast enough, and speed-to-lead can make a major difference in conversions.

We build AI agents that handle this automatically — responding to inbound leads in seconds, qualifying them, and booking calls straight into your calendar, 24/7.

One client added {{result_metric}} more booked calls in their first month without hiring anyone new.

Worth a quick look at how this could work for {{company_name}}?

{{sender_name}}
{{sender_role}}
{{sender_link}}`;
    }
});
