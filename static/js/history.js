document.addEventListener('DOMContentLoaded', async () => {
    const tbody = document.getElementById('history-table-body');
    const rangeText = document.getElementById('pagination-range');
    const totalText = document.getElementById('pagination-total');
    const controls = document.getElementById('pagination-controls');

    async function loadHistory() {
        if (!tbody) return;
        
        try {
            const res = await fetch('/api/history-leads');
            const data = await res.json();
            
            if (data.success && data.history) {
                renderTable(data.history);
            } else {
                renderEmpty();
            }
        } catch (err) {
            console.error("Error fetching history", err);
            renderEmpty();
        }
    }

    function renderEmpty() {
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="9" class="py-space-xl text-center text-on-surface-variant">No historical records found.</td></tr>';
        }
        if (rangeText) rangeText.textContent = '0 to 0';
        if (totalText) totalText.textContent = 'of 0 historical prospects';
        if (controls) {
            controls.innerHTML = `
                <button class="p-1 rounded text-outline disabled:opacity-40" disabled><span class="material-symbols-outlined text-[20px]">chevron_left</span></button>
                <button class="w-8 h-8 rounded-lg bg-primary text-on-primary font-label-md text-label-md font-semibold flex items-center justify-center shadow-sm">1</button>
                <button class="p-1 rounded text-outline disabled:opacity-40" disabled><span class="material-symbols-outlined text-[20px]">chevron_right</span></button>
            `;
        }
    }

    function renderTable(history) {
        if (!tbody) return;
        
        if (!history || history.length === 0) {
            return renderEmpty();
        }
        
        tbody.innerHTML = '';
        
        history.forEach((lead) => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-container-low/60 transition-colors group';
            
            const dateObj = lead.created_at ? new Date(lead.created_at) : new Date();
            const dateStr = dateObj.toLocaleDateString();
            const timeStr = dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            const score = lead.overall_score || 0;
            const initials = (lead.first_name?.[0] || '') + (lead.last_name?.[0] || '');
            
            tr.innerHTML = `
                <td class="py-space-md pl-space-lg pr-space-sm whitespace-nowrap">
                  <div class="flex flex-col">
                    <span class="font-label-md text-label-md text-on-surface">${dateStr}</span>
                    <span class="font-code-sm text-code-sm text-on-surface-variant">${timeStr}</span>
                  </div>
                </td>
                <td class="py-space-md px-space-md whitespace-nowrap">
                  <div class="flex items-center gap-space-sm">
                    <div class="w-8 h-8 rounded-full bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center font-label-md text-label-md font-bold">
                      ${initials || '??'}
                    </div>
                    <div class="flex flex-col min-w-0">
                      <span class="font-label-md text-label-md text-on-surface font-semibold group-hover:text-primary transition-colors">${lead.first_name || ''} ${lead.last_name || ''}</span>
                      <span class="font-body-sm text-body-sm text-on-surface-variant truncate">${lead.email || 'No email'}</span>
                    </div>
                  </div>
                </td>
                <td class="py-space-md px-space-md whitespace-nowrap">
                  <div class="flex items-center gap-space-xs">
                    <span class="w-2 h-2 rounded-full bg-primary"></span>
                    <span class="text-on-surface font-medium">${lead.company || 'Unknown'}</span>
                  </div>
                </td>
                <td class="py-space-md px-space-md whitespace-nowrap text-on-surface-variant">
                  ${lead.title || 'Unknown Role'}
                </td>
                <td class="py-space-md px-space-md whitespace-nowrap text-center">
                  <span class="inline-flex items-center gap-1 px-space-sm py-0.5 rounded-full ${score > 80 ? 'bg-primary-fixed text-on-primary-fixed' : 'bg-surface-container-highest text-on-surface'} font-code-sm text-code-sm font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full ${score > 80 ? 'bg-primary' : 'bg-outline'}"></span>
                    ${score}%
                  </span>
                </td>
                <td class="py-space-md px-space-md whitespace-nowrap">
                  <span class="inline-flex items-center gap-1 font-label-sm text-label-sm text-on-surface font-medium">
                    <span class="material-symbols-outlined text-[16px] text-tertiary">bolt</span>
                    ${lead.intent_signal || 'General'}
                  </span>
                </td>
                <td class="py-space-md px-space-md whitespace-nowrap">
                  <span class="inline-flex items-center px-space-sm py-0.5 rounded-md ${lead.is_contacted ? 'bg-secondary/10 text-secondary' : 'bg-tertiary/10 text-tertiary'} font-label-sm text-label-sm font-medium">
                    ${lead.is_contacted ? 'Contacted' : 'Outreach Ready'}
                  </span>
                </td>
                <td class="py-space-md px-space-md whitespace-nowrap">
                  <span class="font-code-sm text-code-sm text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">
                    ${lead.source || 'Search'}
                  </span>
                </td>
                <td class="py-space-md pr-space-lg pl-space-md whitespace-nowrap text-right">
                  <div class="inline-flex items-center gap-space-xs justify-end">
                    <button class="px-space-sm py-1 rounded bg-primary text-on-primary hover:bg-secondary font-label-sm text-label-sm transition-colors" onclick="window.location.href='/emails'">
                      Draft
                    </button>
                  </div>
                </td>
            `;
            tbody.appendChild(tr);
        });

        if (rangeText) rangeText.textContent = `1 to ${history.length}`;
        if (totalText) totalText.textContent = `of ${history.length} historical prospects`;
        
        if (controls) {
            controls.innerHTML = `
                <button class="p-1 rounded text-outline hover:text-on-surface hover:bg-surface-container transition-colors disabled:opacity-40" disabled><span class="material-symbols-outlined text-[20px]">chevron_left</span></button>
                <button class="w-8 h-8 rounded-lg bg-primary text-on-primary font-label-md text-label-md font-semibold flex items-center justify-center shadow-sm">1</button>
                <button class="p-1 rounded text-outline hover:text-on-surface hover:bg-surface-container transition-colors disabled:opacity-40" disabled><span class="material-symbols-outlined text-[20px]">chevron_right</span></button>
            `;
        }
    }

    loadHistory();
});
