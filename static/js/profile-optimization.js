    // Profile Optimization DOM Elements
    const extractProfileBtn = document.getElementById('extract-profile-btn');
    const optimizeProfileBtn = document.getElementById('optimize-profile-btn');
    const profileUrlInput = document.getElementById('profile-url-input');
    const currentProfileContainer = document.getElementById('current-profile-container');
    const extractedProfileContent = document.getElementById('extracted-profile-content');
    const optimizationResultContainer = document.getElementById('optimization-result-container');
    const optOverallScore = document.getElementById('opt-overall-score');
    const optSummaryText = document.getElementById('opt-summary-text');
    const optCategoryScores = document.getElementById('opt-category-scores');
    const comparisonRowsContainer = document.getElementById('comparison-rows-container');

    // Progressive Extraction DOM Elements
    const extractionProgressContainer = document.getElementById('extraction-progress-container');
    const extractionCurrentStatusTitle = document.getElementById('extraction-current-status-title');
    const extractionProgressCounter = document.getElementById('extraction-progress-counter');
    const extractionSectionChecklist = document.getElementById('extraction-section-checklist');
    const extractionSpinner = document.getElementById('extraction-spinner');

    let currentExtractedData = null;
    let currentDownloadUrl = null;

    // Extraction Type DOM Elements
    const extTypeComplete = document.getElementById('ext-type-complete');
    const extTypeSelected = document.getElementById('ext-type-selected');
    const selectedSectionsContainer = document.getElementById('selected-sections-container');
    const extractProfileBtnText = document.getElementById('extract-profile-btn-text');

    if (extTypeComplete && extTypeSelected) {
      extTypeComplete.addEventListener('change', () => {
        if (extTypeComplete.checked) {
          if (selectedSectionsContainer) selectedSectionsContainer.classList.add('hidden');
          if (extractProfileBtnText) extractProfileBtnText.textContent = 'Extract Profile';
        }
      });
      extTypeSelected.addEventListener('change', () => {
        if (extTypeSelected.checked) {
          if (selectedSectionsContainer) {
            selectedSectionsContainer.classList.remove('hidden');
            selectedSectionsContainer.classList.add('flex');
          }
          if (extractProfileBtnText) extractProfileBtnText.textContent = 'Extract Selected Sections';
        }
      });
    }

    const defaultChecklistSections = [
      { id: 'name', label: 'Name' },
      { id: 'headline', label: 'Headline' },
      { id: 'about', label: 'About' },
      { id: 'experience', label: 'Experience' },
      { id: 'education', label: 'Education' },
      { id: 'skills', label: 'Skills' },
      { id: 'certifications', label: 'Certifications' },
      { id: 'projects', label: 'Projects' }
    ];
    let sectionStates = {};

    function initExtractionChecklist(selectedSectionIds) {
      if (!extractionSectionChecklist) return;
      sectionStates = {};
      const activeSections = (selectedSectionIds && selectedSectionIds.length > 0)
        ? defaultChecklistSections.filter(s => selectedSectionIds.includes(s.id))
        : defaultChecklistSections;
      activeSections.forEach(s => {
        sectionStates[s.id] = { label: s.label, status: 'pending' };
      });
      renderChecklistUI();
    }

    function updateChecklistSection(sectionId, status) {
      if (!sectionStates[sectionId]) {
        sectionStates[sectionId] = { label: sectionId, status: status };
      } else {
        sectionStates[sectionId].status = status;
      }
      renderChecklistUI();
    }

    function renderChecklistUI() {
      if (!extractionSectionChecklist) return;
      let completedCount = 0;
      const keys = Object.keys(sectionStates);
      const totalCount = keys.length;
      let html = '';

      keys.forEach(id => {
        const item = sectionStates[id];
        let iconHtml = '';
        let textClass = 'text-text-muted';
        let bgClass = 'bg-surface-canvas border-border-default/50';

        if (item.status === 'completed') {
          completedCount++;
          iconHtml = `<span class="material-symbols-outlined text-[16px] text-status-success-text shrink-0">check_circle</span>`;
          textClass = 'text-text-primary font-medium';
          bgClass = 'bg-status-success-bg/40 border-status-success-border/60';
        } else if (item.status === 'extracting') {
          iconHtml = `<span class="material-symbols-outlined text-[16px] text-primary-container animate-spin shrink-0">sync</span>`;
          textClass = 'text-primary-container font-semibold';
          bgClass = 'bg-status-score-high-bg border-primary-container/30';
        } else {
          iconHtml = `<span class="material-symbols-outlined text-[16px] text-text-muted shrink-0">radio_button_unchecked</span>`;
        }

        html += `
          <div class="p-2 px-3 rounded-lg border flex items-center gap-2 text-body-sm ${bgClass}">
            ${iconHtml}
            <span class="${textClass} truncate">${item.label}</span>
          </div>
        `;
      });

      extractionSectionChecklist.innerHTML = html;
      if (extractionProgressCounter) {
        extractionProgressCounter.textContent = `${completedCount} / ${totalCount} Sections`;
      }
    }

