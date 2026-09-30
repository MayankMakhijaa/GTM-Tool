company_modal = """
<!-- ================= ONBOARDING MODAL: COMPANY SETUP ================= -->
<div id="modal-onboarding-company" class="fixed inset-0 bg-on-surface/40 backdrop-blur-sm z-[100] flex items-center justify-center p-space-md hidden">
  <div class="bg-surface-card rounded-2xl shadow-xl border border-border-default/80 max-w-2xl w-full max-h-[90vh] overflow-y-auto p-space-xl flex flex-col gap-space-lg animate-in fade-in zoom-in duration-200">
    <div class="flex items-center gap-3 border-b border-border-default/60 pb-4">
      <div class="w-10 h-10 rounded-xl bg-status-score-high-bg text-primary-container flex items-center justify-center font-bold">
        <span class="material-symbols-outlined text-[22px]">domain</span>
      </div>
      <div class="flex flex-col">
        <h3 class="font-headline-sm text-headline-sm text-text-primary">Company Setup</h3>
        <p class="font-body-sm text-body-sm text-text-secondary">Tell us about your company so we can personalize your experience.</p>
      </div>
    </div>

    <form id="form-onboarding-company" class="flex flex-col gap-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Company Name</label>
            <input type="text" id="ob-company-name" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Website URL *</label>
            <input type="url" id="ob-company-website" required class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container" placeholder="https://example.com">
          </div>
      </div>
      
      <div class="flex flex-col gap-1.5">
        <label class="font-label-md text-label-md text-text-primary font-semibold">Description</label>
        <textarea id="ob-company-desc" rows="2" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container"></textarea>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">What Company Sells</label>
            <input type="text" id="ob-company-sells" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Products/Services</label>
            <input type="text" id="ob-company-products" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Industry</label>
            <input type="text" id="ob-company-industry" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Company Size</label>
            <input type="text" id="ob-company-size" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container" placeholder="e.g. 10-50">
          </div>
      </div>
      
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Revenue</label>
            <input type="text" id="ob-company-revenue" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Location</label>
            <input type="text" id="ob-company-location" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
      </div>

      <div id="ob-company-error" class="hidden text-status-error-text text-sm font-medium"></div>

      <div class="flex justify-end pt-2">
        <button type="submit" id="ob-company-save-btn" class="h-11 px-6 rounded-xl bg-primary-container hover:bg-primary text-on-primary font-label-md text-label-md font-semibold transition-all flex items-center gap-2 shadow-sm">
          <span>Save & Continue</span>
          <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
        </button>
      </div>
    </form>
  </div>
</div>

<!-- ================= ONBOARDING MODAL: ICP SETUP ================= -->
<div id="modal-onboarding-icp" class="fixed inset-0 bg-on-surface/40 backdrop-blur-sm z-[100] flex items-center justify-center p-space-md hidden">
  <div class="bg-surface-card rounded-2xl shadow-xl border border-border-default/80 max-w-2xl w-full max-h-[90vh] overflow-y-auto p-space-xl flex flex-col gap-space-lg animate-in fade-in zoom-in duration-200">
    <div class="flex items-center gap-3 border-b border-border-default/60 pb-4">
      <div class="w-10 h-10 rounded-xl bg-status-score-medium-bg text-status-score-medium-text flex items-center justify-center font-bold">
        <span class="material-symbols-outlined text-[22px]">group</span>
      </div>
      <div class="flex flex-col">
        <h3 class="font-headline-sm text-headline-sm text-text-primary">Ideal Customer Profile (ICP)</h3>
        <p class="font-body-sm text-body-sm text-text-secondary">Define who you are targeting to generate the best leads.</p>
      </div>
    </div>

    <form id="form-onboarding-icp" class="flex flex-col gap-4">
      <div class="flex flex-col gap-1.5">
        <label class="font-label-md text-label-md text-text-primary font-semibold">Target Customer</label>
        <textarea id="ob-icp-target" rows="2" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container" placeholder="e.g. VPs of Sales at B2B SaaS startups..."></textarea>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Company Size</label>
            <input type="text" id="ob-icp-size" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Revenue Range</label>
            <input type="text" id="ob-icp-revenue" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Target Roles (comma-separated)</label>
            <input type="text" id="ob-icp-roles" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Industry</label>
            <input type="text" id="ob-icp-industry" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
      </div>
      
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Location</label>
            <input type="text" id="ob-icp-location" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="font-label-md text-label-md text-text-primary font-semibold">Tone</label>
            <select id="ob-icp-tone" class="p-3 rounded-xl bg-surface-canvas border border-border-default/80 font-body-md focus:outline-none focus:ring-2 focus:ring-primary-container">
                <option value="FORMAL">Formal</option>
                <option value="SEMI_FORMAL">Semi-Formal</option>
                <option value="CASUAL">Casual</option>
            </select>
          </div>
      </div>

      <div id="ob-icp-error" class="hidden text-status-error-text text-sm font-medium"></div>

      <div class="flex justify-end pt-2">
        <button type="submit" id="ob-icp-save-btn" class="h-11 px-6 rounded-xl bg-primary-container hover:bg-primary text-on-primary font-label-md text-label-md font-semibold transition-all flex items-center gap-2 shadow-sm">
          <span>Complete Setup</span>
          <span class="material-symbols-outlined text-[18px]">check_circle</span>
        </button>
      </div>
    </form>
  </div>
</div>
"""

with open("templates/index.html", "r") as f:
    content = f.read()

# Insert right before the closing body tag
content = content.replace("</body>", company_modal + "\n</body>")

with open("templates/index.html", "w") as f:
    f.write(content)
print("Modals injected")
