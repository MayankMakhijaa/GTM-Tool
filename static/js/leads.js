    // Render Dashboard table (current run)
    function renderDashboardTable(leads) {
      dashboardTableBody.innerHTML = '';
      if (leads && leads.length > 0) {
        leads.slice(0, 10).forEach(lead => {
          const row = document.createElement('tr');
          row.className = 'hover:bg-surface-canvas/60 transition-colors group';

          const initials = lead.name ? lead.name.substring(0, 2).toUpperCase() : '??';
          const name = lead.name || 'Unknown';
          const company = lead.company || '-';
          const role = lead.role || '-';
          const need = lead.business_need || '-';
          const intent = lead.intent || '-';
          const score = lead.lead_score || 0;

          const profileUrl = lead.profile_url || '';
          const profileHtml = profileUrl ? 
            `<a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-primary-container hover:underline font-label-sm text-label-sm">
               <span>View Profile</span>
               <span class="material-symbols-outlined text-[14px]">open_in_new</span>
             </a>` : '<span class="text-text-muted text-label-sm">-</span>';

          row.innerHTML = `
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center px-2 py-0.5 rounded-md font-label-md text-label-sm bg-status-score-high-bg text-status-score-high-text font-mono font-semibold">
                ${score}/100
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-label-md text-[11px] shrink-0 font-medium">
                  ${initials}
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="font-label-md text-label-md text-text-primary truncate">${name}</span>
                </div>
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap font-medium text-text-primary">${company}</td>
            <td class="py-3.5 px-4 whitespace-nowrap text-text-secondary">${role}</td>
            <td class="py-3.5 px-4 text-text-secondary">
              <div class="line-clamp-1 max-w-[360px]" title="${need}">
                ${need}
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-status-success-bg text-status-success-text font-label-sm text-label-sm">
                ${intent}
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap text-right">
              ${profileHtml}
            </td>
          `;
          dashboardTableBody.appendChild(row);
        });
      } else {
        dashboardTableBody.innerHTML = `
          <tr>
            <td colspan="7" class="py-8 text-center text-text-muted">
              No leads generated yet. Paste a LinkedIn post URL above to get started.
            </td>
          </tr>
        `;
      }
    }

    // Render History table (all historical qualified leads)
    function renderHistoryTable(leads) {
      if (!historyTableBody) return;

      const countBadge = document.getElementById('history-leads-count-badge');
      if (countBadge) {
        countBadge.textContent = `${(leads || []).length} Total Leads`;
      }

      historyTableBody.innerHTML = '';
      if (leads && leads.length > 0) {
        let lastDateLabel = null;

        leads.forEach(lead => {
          const dateLabel = lead.run_date_label || 'History Vault';

          if (dateLabel !== lastDateLabel) {
            lastDateLabel = dateLabel;
            const headerRow = document.createElement('tr');
            headerRow.className = 'bg-surface-subtle/80 border-y border-border-default';
            headerRow.innerHTML = `
              <td colspan="7" class="py-2.5 px-4 font-headline-sm text-headline-sm text-text-primary">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-[18px] text-primary-container">calendar_today</span>
                  <span>${dateLabel}</span>
                </div>
              </td>
            `;
            historyTableBody.appendChild(headerRow);
          }

          const row = document.createElement('tr');
          row.className = 'hover:bg-surface-canvas/60 transition-colors group';

          const initials = lead.name ? lead.name.substring(0, 2).toUpperCase() : '??';
          const name = lead.name || 'Unknown';
          const company = lead.company || '-';
          const role = lead.role || '-';
          const need = lead.business_need || '-';
          const intent = lead.intent || '-';
          const score = lead.lead_score || 0;

          const profileUrl = lead.profile_url || '';
          const profileHtml = profileUrl ? 
            `<a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-primary-container hover:underline font-label-sm text-label-sm">
               <span>View Profile</span>
               <span class="material-symbols-outlined text-[14px]">open_in_new</span>
             </a>` : '<span class="text-text-muted text-label-sm">-</span>';

          row.innerHTML = `
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center px-2 py-0.5 rounded-md font-label-md text-label-sm bg-status-score-high-bg text-status-score-high-text font-mono font-semibold">
                ${score}/100
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-label-md text-[11px] shrink-0 font-medium">
                  ${initials}
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="font-label-md text-label-md text-text-primary truncate">${name}</span>
                </div>
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap font-medium text-text-primary">${company}</td>
            <td class="py-3.5 px-4 whitespace-nowrap text-text-secondary">${role}</td>
            <td class="py-3.5 px-4 text-text-secondary">
              <div class="line-clamp-1 max-w-[360px]" title="${need}">
                ${need}
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-status-success-bg text-status-success-text font-label-sm text-label-sm">
                ${intent}
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap text-right">
              ${profileHtml}
            </td>
          `;
          historyTableBody.appendChild(row);
        });
      } else {
        historyTableBody.innerHTML = `
          <tr>
            <td colspan="7" class="py-12 text-center text-text-muted">
              <div class="flex flex-col items-center justify-center gap-2">
                <span class="material-symbols-outlined text-[36px] text-text-muted">history_toggle_off</span>
                <span class="font-headline-sm text-headline-sm text-text-primary">No historical leads recorded yet.</span>
                <span class="font-body-sm text-body-sm text-text-secondary">Run lead generation on a LinkedIn post to save data to output/*.xlsx.</span>
              </div>
            </td>
          </tr>
        `;
      }
    }

    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => {
        if (!currentDownloadUrl) {
          alert('Please generate leads first before downloading Excel.');
          return;
        }
        window.location.href = currentDownloadUrl;
      });
    }

    if (generateBtn) {
      generateBtn.addEventListener('click', async () => {
        const commentsText = commentsInput ? commentsInput.value.trim() : '';
        if (!commentsText) {
          alert('Please paste LinkedIn comments before generating leads.');
          return;
        }

        const originalHTML = generateBtn.innerHTML;
        generateBtn.disabled = true;
        generateBtn.classList.add('opacity-80', 'cursor-not-allowed');
        generateBtn.innerHTML = `
          <svg class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Generating leads...</span>
        `;
        
        try {
          const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comments_text: commentsText })
          });
          
          const result = await response.json();
          
          if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to generate leads.');
          }

          // Update metrics
          metricSpans[0].textContent = result.comments_analyzed;
          metricSpans[1].textContent = result.qualified_leads_count;
          metricSpans[2].innerHTML = `${result.avg_lead_intent}<span class="font-body-sm text-body-sm text-text-muted font-normal">/100</span>`;
          metricSpans[3].textContent = `${result.processing_time}s`;
          
          currentDownloadUrl = result.download_url;

          // Render dashboard table for current run
          renderDashboardTable(result.leads || []);

          // Refresh historical email and all leads from output/*.xlsx
          fetchHistoricalEmailLeads();
          fetchHistoricalAllLeads();

          generateBtn.innerHTML = `
            <span class="material-symbols-outlined text-[18px]">check</span>
            <span>Completed (${result.qualified_leads_count} Leads)</span>
          `;
          
          setTimeout(() => {
            generateBtn.innerHTML = originalHTML;
          }, 2500);

        } catch (error) {
          alert(error.message);
          generateBtn.innerHTML = originalHTML;
        } finally {
          generateBtn.classList.remove('opacity-80', 'cursor-not-allowed');
          generateBtn.disabled = false;
        }
      });
    }

