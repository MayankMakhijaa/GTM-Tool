document.addEventListener('DOMContentLoaded', () => {
    let currentPage = 1;
    const pageLimit = 15;
    let selectedUserId = null;
    let currentDrawerUser = null;

    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    // Metric Elements
    const metricTotalUsers = document.getElementById('metricTotalUsers');
    const metricActiveUsers = document.getElementById('metricActiveUsers');
    const metricTotalCredits = document.getElementById('metricTotalCredits');
    const metricWalletsCount = document.getElementById('metricWalletsCount');
    const metricAvailableCredits = document.getElementById('metricAvailableCredits');
    const metricReservedCredits = document.getElementById('metricReservedCredits');
    const btnRefreshOverview = document.getElementById('btnRefreshOverview');

    // Pricing Elements
    const pricingTableBody = document.getElementById('pricingTableBody');
    const btnRefreshPricing = document.getElementById('btnRefreshPricing');
    const editPricingModal = document.getElementById('editPricingModal');
    const btnClosePricingModal = document.getElementById('btnClosePricingModal');
    const btnCancelPricing = document.getElementById('btnCancelPricing');
    const editPricingBackdrop = document.getElementById('editPricingBackdrop');
    const editPricingForm = document.getElementById('editPricingForm');
    const pricingModalCode = document.getElementById('pricingModalCode');
    const pricingModalCost = document.getElementById('pricingModalCost');
    const pricingModalDesc = document.getElementById('pricingModalDesc');
    const pricingModalActive = document.getElementById('pricingModalActive');
    const pricingError = document.getElementById('pricingError');

    // Table Elements
    const usersTableBody = document.getElementById('usersTableBody');
    const userSearchInput = document.getElementById('userSearchInput');
    const roleFilterSelect = document.getElementById('roleFilterSelect');
    const statusFilterSelect = document.getElementById('statusFilterSelect');
    const chkNonzeroOnly = document.getElementById('chkNonzeroOnly');
    const paginationSummary = document.getElementById('paginationSummary');
    const pageIndicator = document.getElementById('pageIndicator');
    const btnPrevPage = document.getElementById('btnPrevPage');
    const btnNextPage = document.getElementById('btnNextPage');

    // Drawer Elements
    const userDetailDrawer = document.getElementById('userDetailDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');
    const btnCloseDrawer = document.getElementById('btnCloseDrawer');
    const drawerUserName = document.getElementById('drawerUserName');
    const drawerUserEmail = document.getElementById('drawerUserEmail');
    const drawerUserRoleBadge = document.getElementById('drawerUserRoleBadge');
    const drawerUserIdVal = document.getElementById('drawerUserIdVal');
    const drawerUserPhoneVal = document.getElementById('drawerUserPhoneVal');
    const drawerUserVerifiedVal = document.getElementById('drawerUserVerifiedVal');
    const drawerUserOnboardingVal = document.getElementById('drawerUserOnboardingVal');
    const drawerAccountStatusDesc = document.getElementById('drawerAccountStatusDesc');
    const btnToggleAccountStatus = document.getElementById('btnToggleAccountStatus');
    const btnDeleteUserAccount = document.getElementById('btnDeleteUserAccount');

    // Drawer Tabs
    const tabBtnAccount = document.getElementById('tabBtnAccount');
    const tabBtnWallet = document.getElementById('tabBtnWallet');
    const tabBtnCompany = document.getElementById('tabBtnCompany');
    const tabBtnIcp = document.getElementById('tabBtnIcp');
    const tabContentAccount = document.getElementById('tabContentAccount');
    const tabContentWallet = document.getElementById('tabContentWallet');
    const tabContentCompany = document.getElementById('tabContentCompany');
    const tabContentIcp = document.getElementById('tabContentIcp');

    // Wallet Tab Elements
    const drawerWalletTotal = document.getElementById('drawerWalletTotal');
    const drawerWalletReserved = document.getElementById('drawerWalletReserved');
    const drawerWalletAvailable = document.getElementById('drawerWalletAvailable');
    const drawerTransactionsBody = document.getElementById('drawerTransactionsBody');
    const txTypeFilterSelect = document.getElementById('txTypeFilterSelect');
    const btnRefreshTransactions = document.getElementById('btnRefreshTransactions');
    const btnOpenGrantModal = document.getElementById('btnOpenGrantModal');
    const btnOpenAdjustModal = document.getElementById('btnOpenAdjustModal');

    // Grant Modal Elements
    const grantCreditsModal = document.getElementById('grantCreditsModal');
    const btnCloseGrantModal = document.getElementById('btnCloseGrantModal');
    const btnCancelGrant = document.getElementById('btnCancelGrant');
    const grantCreditsBackdrop = document.getElementById('grantCreditsBackdrop');
    const grantCreditsForm = document.getElementById('grantCreditsForm');
    const grantModalUserLabel = document.getElementById('grantModalUserLabel');
    const grantAmountInput = document.getElementById('grantAmountInput');
    const grantReasonInput = document.getElementById('grantReasonInput');
    const grantError = document.getElementById('grantError');

    // Adjust Modal Elements
    const adjustCreditsModal = document.getElementById('adjustCreditsModal');
    const btnCloseAdjustModal = document.getElementById('btnCloseAdjustModal');
    const btnCancelAdjust = document.getElementById('btnCancelAdjust');
    const adjustCreditsBackdrop = document.getElementById('adjustCreditsBackdrop');
    const adjustCreditsForm = document.getElementById('adjustCreditsForm');
    const adjustModalUserLabel = document.getElementById('adjustModalUserLabel');
    const adjustAmountInput = document.getElementById('adjustAmountInput');
    const adjustReasonInput = document.getElementById('adjustReasonInput');
    const adjustError = document.getElementById('adjustError');

    // Company Tab Elements
    const companyEmptyMessage = document.getElementById('companyEmptyMessage');
    const companyDetailsContent = document.getElementById('companyDetailsContent');
    const drawerCompanyName = document.getElementById('drawerCompanyName');
    const drawerCompanyWebsite = document.getElementById('drawerCompanyWebsite');
    const drawerCompanyIndustryLoc = document.getElementById('drawerCompanyIndustryLoc');
    const drawerCompanyDesc = document.getElementById('drawerCompanyDesc');

    // ICP Tab Elements
    const drawerIcpVersionVal = document.getElementById('drawerIcpVersionVal');
    const drawerIcpUpdatedVal = document.getElementById('drawerIcpUpdatedVal');
    const adminIcpForm = document.getElementById('adminIcpForm');
    const icpFieldTargetCustomer = document.getElementById('icpFieldTargetCustomer');
    const icpFieldTargetRoles = document.getElementById('icpFieldTargetRoles');
    const icpFieldIndustry = document.getElementById('icpFieldIndustry');
    const icpFieldLocation = document.getElementById('icpFieldLocation');
    const icpFieldCompanySize = document.getElementById('icpFieldCompanySize');
    const icpFieldKeywords = document.getElementById('icpFieldKeywords');
    const icpFieldExclusions = document.getElementById('icpFieldExclusions');
    const icpSaveFeedback = document.getElementById('icpSaveFeedback');

    // Provision User Modal Elements
    const createUserModal = document.getElementById('createUserModal');
    const btnOpenCreateUserModal = document.getElementById('btnOpenCreateUserModal');
    const btnCloseCreateUserModal = document.getElementById('btnCloseCreateUserModal');
    const btnCancelCreateUser = document.getElementById('btnCancelCreateUser');
    const createUserBackdrop = document.getElementById('createUserBackdrop');
    const adminCreateUserForm = document.getElementById('adminCreateUserForm');
    const createUserError = document.getElementById('createUserError');

    // Helper: Generate Stable Idempotency Key
    function generateIdempotencyKey(action, userId) {
        return `adm_${action}_u${userId}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    }

    // 1. Fetch & Render Overview Metrics (System & Credits)
    async function loadMetrics() {
        try {
            // General Overview
            const resSys = await fetch('/api/admin/overview', {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const dataSys = await resSys.json();
            if (resSys.ok && dataSys.success) {
                if (metricTotalUsers) metricTotalUsers.textContent = Number(dataSys.metrics.total_users).toLocaleString();
                if (metricActiveUsers) metricActiveUsers.textContent = Number(dataSys.metrics.active_users).toLocaleString();
            }

            // Credit Pool Overview
            const resCred = await fetch('/api/admin/credits/overview', {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const dataCred = await resCred.json();
            if (resCred.ok && dataCred.success) {
                if (metricTotalCredits) metricTotalCredits.textContent = parseFloat(dataCred.metrics.total_balance).toFixed(2);
                if (metricWalletsCount) metricWalletsCount.textContent = dataCred.metrics.wallets_count;
                if (metricAvailableCredits) metricAvailableCredits.textContent = parseFloat(dataCred.metrics.available_balance).toFixed(2);
                if (metricReservedCredits) metricReservedCredits.textContent = parseFloat(dataCred.metrics.reserved_balance).toFixed(2);
            }
        } catch (err) {
            console.error('Error loading overview metrics:', err);
        }
    }

    // 2. Fetch & Render Feature Pricing Schema
    async function loadPricing() {
        if (!pricingTableBody) return;
        try {
            pricingTableBody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-on-surface-variant">Loading feature pricing...</td></tr>`;
            const res = await fetch('/api/admin/credits/pricing', {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'Failed to fetch pricing');
            }

            renderPricingTable(data.pricing);
        } catch (err) {
            console.error('Error loading pricing:', err);
            pricingTableBody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-error font-medium">Failed to load pricing: ${err.message}</td></tr>`;
        }
    }

    function renderPricingTable(pricings) {
        if (!pricingTableBody) return;
        if (!pricings || pricings.length === 0) {
            pricingTableBody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-outline">No feature pricing configured yet.</td></tr>`;
            return;
        }

        pricingTableBody.innerHTML = pricings.map(p => {
            const statusBadge = p.is_active
                ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-status-success-bg text-status-success-text border border-status-success-border">Active</span>`
                : `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-surface-container-high text-outline">Disabled</span>`;

            const updatedDate = p.updated_at ? new Date(p.updated_at).toLocaleString() : '--';

            return `
                <tr class="hover:bg-surface-container-low/50 transition-colors">
                    <td class="py-3 px-4 font-mono font-bold text-xs text-primary">${escapeHtml(p.feature_code)}</td>
                    <td class="py-3 px-4">
                        <div class="flex flex-col">
                            <span class="font-medium text-on-surface">${escapeHtml(p.name)}</span>
                            <span class="text-xs text-outline">${escapeHtml(p.description || '')}</span>
                        </div>
                    </td>
                    <td class="py-3 px-4 text-xs font-mono">${escapeHtml(p.unit_name)}</td>
                    <td class="py-3 px-4 font-mono font-bold text-sm text-on-surface">${parseFloat(p.credit_cost).toFixed(2)}</td>
                    <td class="py-3 px-4">${statusBadge}</td>
                    <td class="py-3 px-4 text-xs font-mono">v${p.version}</td>
                    <td class="py-3 px-4 text-xs text-outline">${updatedDate}</td>
                    <td class="py-3 px-4 text-right">
                        <button class="btnEditPricing px-3 py-1 rounded bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-semibold transition-colors"
                            data-code="${escapeHtml(p.feature_code)}"
                            data-cost="${p.credit_cost}"
                            data-desc="${escapeHtml(p.description || '')}"
                            data-active="${p.is_active}">
                            Edit Cost
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // Bind Edit buttons
        document.querySelectorAll('.btnEditPricing').forEach(btn => {
            btn.addEventListener('click', () => {
                const code = btn.getAttribute('data-code');
                const cost = btn.getAttribute('data-cost');
                const desc = btn.getAttribute('data-desc');
                const active = btn.getAttribute('data-active') === 'true';

                pricingModalCode.value = code;
                pricingModalCost.value = parseFloat(cost).toFixed(2);
                pricingModalDesc.value = desc;
                pricingModalActive.checked = active;
                pricingError.classList.add('hidden');
                editPricingModal.classList.remove('hidden');
            });
        });
    }

    // 3. Fetch & Render Users Directory Table (with Credit Balances via LEFT JOIN)
    async function loadUsers() {
        const search = userSearchInput.value.trim();
        const role = roleFilterSelect.value;
        const isActive = statusFilterSelect.value;
        const nonzero = chkNonzeroOnly ? chkNonzeroOnly.checked : false;

        const params = new URLSearchParams({
            page: currentPage,
            limit: pageLimit
        });
        if (search) params.append('search', search);
        if (role) params.append('role', role);
        if (isActive === 'true') params.append('status', 'active');
        if (isActive === 'false') params.append('status', 'inactive');
        if (nonzero) params.append('nonzero_only', 'true');

        try {
            usersTableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-on-surface-variant">Loading user directory...</td></tr>`;
            const res = await fetch(`/api/admin/credits/users?${params.toString()}`, {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'Failed to fetch users');
            }

            renderUsersTable(data.users, data.total);
        } catch (err) {
            console.error('Error loading users:', err);
            usersTableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-error font-medium">Failed to load users: ${err.message}</td></tr>`;
        }
    }

    function renderUsersTable(users, totalCount) {
        if (!users || users.length === 0) {
            usersTableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-on-surface-variant">No user accounts found matching criteria.</td></tr>`;
            paginationSummary.textContent = `Showing 0 of 0 users`;
            btnPrevPage.disabled = true;
            btnNextPage.disabled = true;
            return;
        }

        const startIdx = (currentPage - 1) * pageLimit + 1;
        const endIdx = Math.min(currentPage * pageLimit, totalCount);
        paginationSummary.textContent = `Showing ${startIdx} to ${endIdx} of ${totalCount} users`;
        pageIndicator.textContent = currentPage;
        btnPrevPage.disabled = currentPage <= 1;
        btnNextPage.disabled = endIdx >= totalCount;

        usersTableBody.innerHTML = users.map(u => {
            const roleBadgeClass = u.role === 'SUPER_ADMIN' 
                ? 'bg-primary-container text-on-primary font-bold' 
                : (u.role === 'ADMIN' ? 'bg-secondary-container text-on-secondary-container font-semibold' : 'bg-surface-container-high text-on-surface');

            const statusBadgeClass = u.is_active 
                ? 'bg-status-success-bg text-status-success-text border border-status-success-border' 
                : 'bg-error-container text-on-error-container';

            const totalBal = parseFloat(u.total_balance || 0).toFixed(2);
            const resBal = parseFloat(u.reserved_balance || 0).toFixed(2);
            const availBal = parseFloat(u.available_balance || 0).toFixed(2);

            return `
                <tr class="hover:bg-surface-container-low/50 transition-colors">
                    <td class="py-3 px-4">
                        <div class="flex flex-col">
                            <span class="font-medium text-on-surface">${escapeHtml(u.name)}</span>
                            <span class="text-xs text-on-surface-variant">${escapeHtml(u.email_id || '')}</span>
                        </div>
                    </td>
                    <td class="py-3 px-4">
                        <span class="px-2 py-0.5 rounded text-[11px] ${roleBadgeClass}">${u.role}</span>
                    </td>
                    <td class="py-3 px-4">
                        <span class="px-2 py-0.5 rounded-full text-[11px] font-semibold ${statusBadgeClass}">
                            ${u.is_active ? 'Active' : 'Deactivated'}
                        </span>
                    </td>
                    <td class="py-3 px-4 font-mono font-bold text-sm text-primary">
                        ${totalBal}
                    </td>
                    <td class="py-3 px-4 font-mono text-xs ${parseFloat(resBal) > 0 ? 'text-error font-bold' : 'text-outline'}">
                        ${resBal}
                    </td>
                    <td class="py-3 px-4 font-mono font-bold text-sm text-tertiary">
                        ${availBal}
                    </td>
                    <td class="py-3 px-4 text-right">
                        <button class="btnInspectUser px-3 py-1 rounded bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-semibold transition-colors" data-user-id="${u.user_id}">
                            Inspect & Manage
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // Bind Inspect buttons
        document.querySelectorAll('.btnInspectUser').forEach(btn => {
            btn.addEventListener('click', () => {
                const uid = btn.getAttribute('data-user-id');
                openUserDrawer(uid);
            });
        });
    }

    // 4. User Details Drawer & Credit Wallet Management
    async function openUserDrawer(userId) {
        selectedUserId = userId;
        switchTab('account');
        userDetailDrawer.classList.remove('hidden');

        try {
            const res = await fetch(`/api/admin/users/${userId}`, {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'Failed to load user details');
            }

            currentDrawerUser = data.user;
            renderDrawer(data);
            loadUserWallet(userId);
        } catch (err) {
            console.error('Error opening user drawer:', err);
            alert('Failed to load user details: ' + err.message);
            closeUserDrawer();
        }
    }

    function closeUserDrawer() {
        userDetailDrawer.classList.add('hidden');
        selectedUserId = null;
        currentDrawerUser = null;
        if (icpSaveFeedback) icpSaveFeedback.classList.add('hidden');
    }

    function normalizeIcpField(val) {
        if (Array.isArray(val)) {
            const cleaned = val.map(v => (v !== null && v !== undefined ? String(v).trim() : '')).filter(Boolean);
            return cleaned.join(', ');
        }
        if (typeof val === 'string') {
            return val.trim();
        }
        if (val !== null && val !== undefined) {
            return String(val).trim();
        }
        return '';
    }

    function renderDrawer(data) {
        const u = data.user;
        const comp = data.company;
        const icp = data.icp;

        drawerUserName.textContent = u.name;
        drawerUserEmail.textContent = u.email_id || u.phone_no;
        drawerUserRoleBadge.textContent = u.role;
        drawerUserIdVal.textContent = u.user_id;
        drawerUserPhoneVal.textContent = u.phone_no || 'None';
        drawerUserVerifiedVal.textContent = u.email_verified ? `Yes (${u.email_verified_at})` : 'No (Pending OTP)';
        drawerUserOnboardingVal.textContent = u.onboarding_step;

        updateAccountStatusUI(u.is_active);

        // Company Tab
        if (comp && comp.website_url) {
            companyEmptyMessage.classList.add('hidden');
            companyDetailsContent.classList.remove('hidden');
            drawerCompanyName.textContent = comp.name || '--';
            drawerCompanyWebsite.textContent = comp.website_url || '--';
            drawerCompanyIndustryLoc.textContent = `${comp.industry || '--'} | ${comp.location || '--'}`;
            drawerCompanyDesc.textContent = comp.description || '--';
        } else {
            companyEmptyMessage.classList.remove('hidden');
            companyDetailsContent.classList.add('hidden');
        }

        // ICP Tab
        if (icp) {
            drawerIcpVersionVal.textContent = icp.version || 1;
            drawerIcpUpdatedVal.textContent = icp.updated_at ? `Updated: ${new Date(icp.updated_at).toLocaleDateString()}` : 'Initial';
            icpFieldTargetCustomer.value = typeof icp.target_customer === 'string' ? icp.target_customer : (icp.target_customer || '');
            icpFieldTargetRoles.value = normalizeIcpField(icp.target_roles || icp.target_jobs_roles);
            icpFieldIndustry.value = normalizeIcpField(icp.industry);
            icpFieldLocation.value = normalizeIcpField(icp.location);
            icpFieldCompanySize.value = normalizeIcpField(icp.company_size);
            icpFieldKeywords.value = normalizeIcpField(icp.keywords);
            icpFieldExclusions.value = normalizeIcpField(icp.exclusions);
        }
    }

    // 5. Load User Credit Balance & Ledger Transactions
    async function loadUserWallet(userId) {
        if (!userId) return;
        try {
            // Wallet balances
            const res = await fetch(`/api/admin/credits/users/${userId}`, {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const data = await res.json();
            if (res.ok && data.success) {
                drawerWalletTotal.textContent = parseFloat(data.wallet.total_balance).toFixed(2);
                drawerWalletReserved.textContent = parseFloat(data.wallet.reserved_balance).toFixed(2);
                drawerWalletAvailable.textContent = parseFloat(data.wallet.available_balance).toFixed(2);
            }

            // Ledger transactions
            loadUserTransactions(userId);
        } catch (err) {
            console.error('Error loading wallet:', err);
        }
    }

    async function loadUserTransactions(userId) {
        if (!userId) return;
        const txType = txTypeFilterSelect ? txTypeFilterSelect.value : '';
        const url = `/api/admin/credits/users/${userId}/transactions${txType ? '?type=' + txType : ''}`;

        try {
            drawerTransactionsBody.innerHTML = `<tr><td colspan="6" class="py-4 text-center text-outline">Loading transactions...</td></tr>`;
            const res = await fetch(url, {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'Failed to load transactions');
            }

            if (!data.transactions || data.transactions.length === 0) {
                drawerTransactionsBody.innerHTML = `<tr><td colspan="6" class="py-4 text-center text-outline">No transaction history found.</td></tr>`;
                return;
            }

            drawerTransactionsBody.innerHTML = data.transactions.map(t => {
                const amountVal = parseFloat(t.amount);
                const amountColor = amountVal > 0 ? 'text-status-success-text font-bold' : (amountVal < 0 ? 'text-error font-bold' : 'text-outline');
                const sign = amountVal > 0 ? '+' : '';
                const createdStr = t.created_at ? new Date(t.created_at).toLocaleDateString() : '--';

                return `
                    <tr class="hover:bg-surface-container-low transition-colors">
                        <td class="py-2 px-3 text-outline">${createdStr}</td>
                        <td class="py-2 px-3 font-mono font-semibold">${escapeHtml(t.transaction_type)}</td>
                        <td class="py-2 px-3 font-mono ${amountColor}">${sign}${amountVal.toFixed(2)}</td>
                        <td class="py-2 px-3 font-mono text-outline">${parseFloat(t.reserved_delta).toFixed(2)}</td>
                        <td class="py-2 px-3 font-mono font-semibold">${parseFloat(t.balance_after).toFixed(2)}</td>
                        <td class="py-2 px-3 text-on-surface-variant truncate max-w-[140px]" title="${escapeHtml(t.reason)}">${escapeHtml(t.reason)}</td>
                    </tr>
                `;
            }).join('');
        } catch (err) {
            console.error('Error loading transactions:', err);
            drawerTransactionsBody.innerHTML = `<tr><td colspan="6" class="py-4 text-center text-error font-medium">Failed to load transactions: ${err.message}</td></tr>`;
        }
    }

    if (txTypeFilterSelect) {
        txTypeFilterSelect.addEventListener('change', () => {
            if (selectedUserId) loadUserTransactions(selectedUserId);
        });
    }

    if (btnRefreshTransactions) {
        btnRefreshTransactions.addEventListener('click', () => {
            if (selectedUserId) loadUserWallet(selectedUserId);
        });
    }

    // 6. Grant Credits Modal Flow
    if (btnOpenGrantModal) {
        btnOpenGrantModal.addEventListener('click', () => {
            if (!currentDrawerUser) return;
            grantModalUserLabel.textContent = `${currentDrawerUser.name} (${currentDrawerUser.email_id || currentDrawerUser.phone_no})`;
            grantAmountInput.value = '';
            grantReasonInput.value = '';
            grantError.classList.add('hidden');
            grantCreditsModal.classList.remove('hidden');
        });
    }

    function closeGrantModal() {
        grantCreditsModal.classList.add('hidden');
    }

    if (btnCloseGrantModal) btnCloseGrantModal.addEventListener('click', closeGrantModal);
    if (btnCancelGrant) btnCancelGrant.addEventListener('click', closeGrantModal);
    if (grantCreditsBackdrop) grantCreditsBackdrop.addEventListener('click', closeGrantModal);

    if (grantCreditsForm) {
        grantCreditsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!selectedUserId) return;

            const amount = parseFloat(grantAmountInput.value);
            const reason = grantReasonInput.value.trim();
            const idempotencyKey = generateIdempotencyKey('grant', selectedUserId);

            if (isNaN(amount) || amount <= 0) {
                grantError.textContent = "Amount must be strictly greater than zero.";
                grantError.classList.remove('hidden');
                return;
            }
            if (!reason) {
                grantError.textContent = "A business justification reason is required.";
                grantError.classList.remove('hidden');
                return;
            }

            grantError.classList.add('hidden');
            const submitBtn = document.getElementById('btnSubmitGrant');
            submitBtn.disabled = true;
            submitBtn.textContent = "Processing Grant...";

            try {
                const res = await fetch(`/api/admin/credits/users/${selectedUserId}/grant`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ amount, reason, idempotency_key: idempotencyKey })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || data.error || 'Failed to grant credits');
                }

                closeGrantModal();
                loadUserWallet(selectedUserId);
                loadMetrics();
                loadUsers();
                alert(`Successfully granted ${amount.toFixed(2)} credits to user.`);
            } catch (err) {
                grantError.textContent = err.message;
                grantError.classList.remove('hidden');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Confirm Grant";
            }
        });
    }

    // 7. Adjust Credits Modal Flow
    if (btnOpenAdjustModal) {
        btnOpenAdjustModal.addEventListener('click', () => {
            if (!currentDrawerUser) return;
            adjustModalUserLabel.textContent = `${currentDrawerUser.name} (${currentDrawerUser.email_id || currentDrawerUser.phone_no})`;
            adjustAmountInput.value = '';
            adjustReasonInput.value = '';
            adjustError.classList.add('hidden');
            adjustCreditsModal.classList.remove('hidden');
        });
    }

    function closeAdjustModal() {
        adjustCreditsModal.classList.add('hidden');
    }

    if (btnCloseAdjustModal) btnCloseAdjustModal.addEventListener('click', closeAdjustModal);
    if (btnCancelAdjust) btnCancelAdjust.addEventListener('click', closeAdjustModal);
    if (adjustCreditsBackdrop) adjustCreditsBackdrop.addEventListener('click', closeAdjustModal);

    if (adjustCreditsForm) {
        adjustCreditsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!selectedUserId) return;

            const amount = parseFloat(adjustAmountInput.value);
            const reason = adjustReasonInput.value.trim();
            const idempotencyKey = generateIdempotencyKey('adjust', selectedUserId);

            if (isNaN(amount) || amount === 0) {
                adjustError.textContent = "Adjustment amount cannot be zero.";
                adjustError.classList.remove('hidden');
                return;
            }
            if (!reason) {
                adjustError.textContent = "A justification reason is required.";
                adjustError.classList.remove('hidden');
                return;
            }

            adjustError.classList.add('hidden');
            const submitBtn = document.getElementById('btnSubmitAdjust');
            submitBtn.disabled = true;
            submitBtn.textContent = "Processing Adjustment...";

            try {
                const res = await fetch(`/api/admin/credits/users/${selectedUserId}/adjust`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ amount, reason, idempotency_key: idempotencyKey })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || data.error || 'Failed to adjust credits');
                }

                closeAdjustModal();
                loadUserWallet(selectedUserId);
                loadMetrics();
                loadUsers();
                alert(`Successfully adjusted balance by ${amount > 0 ? '+' : ''}${amount.toFixed(2)} credits.`);
            } catch (err) {
                adjustError.textContent = err.message;
                adjustError.classList.remove('hidden');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Confirm Adjustment";
            }
        });
    }

    // 8. Edit Pricing Modal Flow
    function closePricingModal() {
        editPricingModal.classList.add('hidden');
    }

    if (btnClosePricingModal) btnClosePricingModal.addEventListener('click', closePricingModal);
    if (btnCancelPricing) btnCancelPricing.addEventListener('click', closePricingModal);
    if (editPricingBackdrop) editPricingBackdrop.addEventListener('click', closePricingModal);

    if (editPricingForm) {
        editPricingForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const code = pricingModalCode.value;
            const cost = parseFloat(pricingModalCost.value);
            const desc = pricingModalDesc.value.trim();
            const active = pricingModalActive.checked;

            if (isNaN(cost) || cost < 0) {
                pricingError.textContent = "Credit cost must be a non-negative number.";
                pricingError.classList.remove('hidden');
                return;
            }

            pricingError.classList.add('hidden');
            const submitBtn = document.getElementById('btnSubmitPricing');
            submitBtn.disabled = true;
            submitBtn.textContent = "Saving...";

            try {
                const res = await fetch(`/api/admin/credits/pricing/${encodeURIComponent(code)}`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ credit_cost: cost, description: desc, is_active: active })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || data.error || 'Failed to update pricing');
                }

                closePricingModal();
                loadPricing();
                loadMetrics();
                alert(`Feature pricing for '${code}' updated successfully.`);
            } catch (err) {
                pricingError.textContent = err.message;
                pricingError.classList.remove('hidden');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Save Pricing Changes";
            }
        });
    }

    if (btnRefreshPricing) {
        btnRefreshPricing.addEventListener('click', () => loadPricing());
    }

    // Account Status Toggle in Drawer
    function updateAccountStatusUI(isActive) {
        if (isActive) {
            drawerAccountStatusDesc.textContent = "Active and authorized to sign in.";
            btnToggleAccountStatus.textContent = "Deactivate Account";
            btnToggleAccountStatus.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-error/10 text-error hover:bg-error/20 border border-error/20 transition-colors";
        } else {
            drawerAccountStatusDesc.textContent = "Deactivated. Account sessions revoked.";
            btnToggleAccountStatus.textContent = "Reactivate Account";
            btnToggleAccountStatus.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-tertiary-fixed/30 text-tertiary hover:bg-tertiary-fixed/50 border border-tertiary/20 transition-colors";
        }
    }

    btnToggleAccountStatus.addEventListener('click', async () => {
        if (!selectedUserId || !currentDrawerUser) return;
        const newStatus = !currentDrawerUser.is_active;
        const actionLabel = newStatus ? 'reactivate' : 'deactivate';

        if (!confirm(`Are you sure you want to ${actionLabel} account for ${currentDrawerUser.name}?`)) {
            return;
        }

        try {
            const res = await fetch(`/api/admin/users/${selectedUserId}/status`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ is_active: newStatus })
            });
            const contentType = res.headers.get('content-type') || '';
            const data = contentType.includes('application/json') ? await res.json() : null;
            if (!res.ok || !data || !data.success) {
                const errMsg = (data && (data.message || data.error)) || `Server returned ${res.status} ${res.statusText}`;
                throw new Error(errMsg);
            }

            currentDrawerUser.is_active = newStatus;
            updateAccountStatusUI(newStatus);
            loadMetrics();
            loadUsers();
        } catch (err) {
            alert('Action failed: ' + err.message);
        }
    });

    if (btnDeleteUserAccount) {
        btnDeleteUserAccount.addEventListener('click', async () => {
            if (!selectedUserId || !currentDrawerUser || btnDeleteUserAccount.disabled) return;
            const userName = currentDrawerUser.name || 'this user';
            const userEmail = currentDrawerUser.email_id || currentDrawerUser.phone_no || `ID #${selectedUserId}`;

            if (!confirm(`WARNING: Are you sure you want to PERMANENTLY DELETE the account for ${userName} (${userEmail})?\n\nThis action cannot be undone.`)) {
                return;
            }

            try {
                btnDeleteUserAccount.disabled = true;
                btnDeleteUserAccount.textContent = 'Deleting...';

                const res = await fetch(`/api/admin/users/${selectedUserId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                });

                const contentType = res.headers.get('content-type') || '';
                const data = contentType.includes('application/json') ? await res.json() : null;

                if (!res.ok || !data || !data.success) {
                    const errMsg = (data && (data.message || data.error)) || `Server returned ${res.status} ${res.statusText}`;
                    throw new Error(errMsg);
                }

                const deletedId = selectedUserId;
                // If drawer currently inspects the deleted user, close it and clear state
                if (selectedUserId === deletedId) {
                    closeUserDrawer();
                }
                // Refresh counts and user table
                await Promise.all([loadMetrics(), loadUsers()]);
                alert(`User account for ${userName} was permanently deleted.`);
            } catch (err) {
                alert('Action failed: ' + err.message);
            } finally {
                if (btnDeleteUserAccount) {
                    btnDeleteUserAccount.disabled = false;
                    btnDeleteUserAccount.textContent = 'Delete User';
                }
            }
        });
    }

    // Drawer Tabs Navigation
    function switchTab(tab) {
        // Reset Tabs styling
        [tabBtnAccount, tabBtnWallet, tabBtnCompany, tabBtnIcp].forEach(b => {
            if (b) b.className = 'py-3 px-4 font-label-md text-label-md border-b-2 border-transparent text-on-surface-variant hover:text-on-surface font-semibold';
        });
        // Hide Tab Contents
        [tabContentAccount, tabContentWallet, tabContentCompany, tabContentIcp].forEach(c => {
            if (c) c.classList.add('hidden');
        });

        if (tab === 'account') {
            tabBtnAccount.className = 'py-3 px-4 font-label-md text-label-md border-b-2 border-primary text-primary font-semibold';
            tabContentAccount.classList.remove('hidden');
        } else if (tab === 'wallet') {
            tabBtnWallet.className = 'py-3 px-4 font-label-md text-label-md border-b-2 border-primary text-primary font-semibold';
            tabContentWallet.classList.remove('hidden');
            if (selectedUserId) loadUserWallet(selectedUserId);
        } else if (tab === 'company') {
            tabBtnCompany.className = 'py-3 px-4 font-label-md text-label-md border-b-2 border-primary text-primary font-semibold';
            tabContentCompany.classList.remove('hidden');
        } else if (tab === 'icp') {
            tabBtnIcp.className = 'py-3 px-4 font-label-md text-label-md border-b-2 border-primary text-primary font-semibold';
            tabContentIcp.classList.remove('hidden');
        }
    }

    tabBtnAccount.addEventListener('click', () => switchTab('account'));
    if (tabBtnWallet) tabBtnWallet.addEventListener('click', () => switchTab('wallet'));
    tabBtnCompany.addEventListener('click', () => switchTab('company'));
    tabBtnIcp.addEventListener('click', () => switchTab('icp'));

    btnCloseDrawer.addEventListener('click', closeUserDrawer);
    drawerBackdrop.addEventListener('click', closeUserDrawer);

    // ICP Form submission
    if (adminIcpForm) {
        adminIcpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!selectedUserId) return;

            const payload = {
                target_customer: icpFieldTargetCustomer.value.trim(),
                target_roles: icpFieldTargetRoles.value.split(',').map(s => s.trim()).filter(Boolean),
                industry: icpFieldIndustry.value.split(',').map(s => s.trim()).filter(Boolean),
                location: icpFieldLocation.value.split(',').map(s => s.trim()).filter(Boolean),
                company_size: icpFieldCompanySize.value.split(',').map(s => s.trim()).filter(Boolean),
                keywords: icpFieldKeywords.value.split(',').map(s => s.trim()).filter(Boolean),
                exclusions: icpFieldExclusions.value.split(',').map(s => s.trim()).filter(Boolean)
            };

            try {
                const res = await fetch(`/api/admin/users/${selectedUserId}/icp`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || data.error || 'Failed to update ICP');
                }

                icpSaveFeedback.classList.remove('hidden');
                setTimeout(() => icpSaveFeedback.classList.add('hidden'), 3000);
                if (data.icp) {
                    drawerIcpVersionVal.textContent = data.icp.version;
                    drawerIcpUpdatedVal.textContent = 'Updated just now';
                }
            } catch (err) {
                alert('Failed to save ICP: ' + err.message);
            }
        });
    }

    // Provision User Modal
    btnOpenCreateUserModal.addEventListener('click', () => {
        adminCreateUserForm.reset();
        createUserError.classList.add('hidden');
        createUserModal.classList.remove('hidden');
    });

    function closeCreateUserModal() {
        createUserModal.classList.add('hidden');
    }

    btnCloseCreateUserModal.addEventListener('click', closeCreateUserModal);
    btnCancelCreateUser.addEventListener('click', closeCreateUserModal);
    createUserBackdrop.addEventListener('click', closeCreateUserModal);

    adminCreateUserForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('createUserName').value.trim();
        const email = document.getElementById('createUserEmail').value.trim();
        const phone = document.getElementById('createUserPhone').value.trim();
        const password = document.getElementById('createUserPassword').value;

        createUserError.classList.add('hidden');

        try {
            const res = await fetch('/api/admin/users/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ name, email, phone, password })
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.message || data.error || 'Failed to provision user');
            }

            closeCreateUserModal();
            loadMetrics();
            loadUsers();
            alert('Customer account provisioned successfully! A verification code has been dispatched.');
        } catch (err) {
            createUserError.textContent = err.message;
            createUserError.classList.remove('hidden');
        }
    });

    // Filters & Search Debounce
    let searchTimeout = null;
    userSearchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentPage = 1;
            loadUsers();
        }, 300);
    });

    roleFilterSelect.addEventListener('change', () => {
        currentPage = 1;
        loadUsers();
    });

    statusFilterSelect.addEventListener('change', () => {
        currentPage = 1;
        loadUsers();
    });

    if (chkNonzeroOnly) {
        chkNonzeroOnly.addEventListener('change', () => {
            currentPage = 1;
            loadUsers();
        });
    }

    btnPrevPage.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadUsers();
        }
    });

    btnNextPage.addEventListener('click', () => {
        currentPage++;
        loadUsers();
    });

    btnRefreshOverview.addEventListener('click', () => {
        loadMetrics();
        loadPricing();
        loadUsers();
        loadAiUsageDashboard();
    });

    // Helper
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // ====================================================================
    // TICKET 3F: AI PROVIDER COST & USAGE DASHBOARD
    // ====================================================================
    let aiCurrentPage = 1;
    const aiPageLimit = 20;
    let aiCurrentRangePreset = '7d';
    let aiCustomStart = null;
    let aiCustomEnd = null;

    // AI DOM Elements
    const btnAiRange24h = document.getElementById('btnAiRange24h');
    const btnAiRange7d = document.getElementById('btnAiRange7d');
    const btnAiRange30d = document.getElementById('btnAiRange30d');
    const btnAiRangeCustom = document.getElementById('btnAiRangeCustom');
    const customDateRangeInputs = document.getElementById('customDateRangeInputs');
    const aiCustomStartDate = document.getElementById('aiCustomStartDate');
    const aiCustomEndDate = document.getElementById('aiCustomEndDate');
    const btnApplyCustomDate = document.getElementById('btnApplyCustomDate');
    const btnRefreshAiUsage = document.getElementById('btnRefreshAiUsage');

    const aiMetricTotalCost = document.getElementById('aiMetricTotalCost');
    const aiMetricTotalAttempts = document.getElementById('aiMetricTotalAttempts');
    const aiMetricTotalTokens = document.getElementById('aiMetricTotalTokens');
    const aiMetricPromptTokens = document.getElementById('aiMetricPromptTokens');
    const aiMetricCompTokens = document.getElementById('aiMetricCompTokens');
    const aiMetricSuccessRate = document.getElementById('aiMetricSuccessRate');
    const aiMetricSuccessCount = document.getElementById('aiMetricSuccessCount');
    const aiMetricFailedAttempts = document.getElementById('aiMetricFailedAttempts');
    const aiMetricUnknownCostCount = document.getElementById('aiMetricUnknownCostCount');

    const aiModelBreakdownContainer = document.getElementById('aiModelBreakdownContainer');
    const aiOperationBreakdownContainer = document.getElementById('aiOperationBreakdownContainer');
    const aiCostTrendsContainer = document.getElementById('aiCostTrendsContainer');
    const aiTokensTrendsContainer = document.getElementById('aiTokensTrendsContainer');

    const aiFilterProvider = document.getElementById('aiFilterProvider');
    const aiFilterModel = document.getElementById('aiFilterModel');
    const aiFilterOperation = document.getElementById('aiFilterOperation');
    const aiFilterStatus = document.getElementById('aiFilterStatus');
    const aiFilterUserId = document.getElementById('aiFilterUserId');
    const aiFilterJobId = document.getElementById('aiFilterJobId');
    const aiFilterCorrelationId = document.getElementById('aiFilterCorrelationId');
    const btnAiResetFilters = document.getElementById('btnAiResetFilters');

    const aiUsageTableBody = document.getElementById('aiUsageTableBody');
    const aiPaginationSummary = document.getElementById('aiPaginationSummary');
    const aiPageIndicator = document.getElementById('aiPageIndicator');
    const btnAiPrevPage = document.getElementById('btnAiPrevPage');
    const btnAiNextPage = document.getElementById('btnAiNextPage');

    function getAiDateRangeParams() {
        const now = new Date();
        let start = new Date();

        if (aiCurrentRangePreset === '24h') {
            start.setTime(now.getTime() - (24 * 60 * 60 * 1000));
            return `start_date=${encodeURIComponent(start.toISOString())}&end_date=${encodeURIComponent(now.toISOString())}`;
        } else if (aiCurrentRangePreset === '7d') {
            start.setTime(now.getTime() - (7 * 24 * 60 * 60 * 1000));
            return `start_date=${encodeURIComponent(start.toISOString())}&end_date=${encodeURIComponent(now.toISOString())}`;
        } else if (aiCurrentRangePreset === '30d') {
            start.setTime(now.getTime() - (30 * 24 * 60 * 60 * 1000));
            return `start_date=${encodeURIComponent(start.toISOString())}&end_date=${encodeURIComponent(now.toISOString())}`;
        } else if (aiCurrentRangePreset === 'custom' && aiCustomStart && aiCustomEnd) {
            return `start_date=${encodeURIComponent(aiCustomStart)}&end_date=${encodeURIComponent(aiCustomEnd)}`;
        }
        return '';
    }

    function setAiRangeButtonActive(btn) {
        [btnAiRange24h, btnAiRange7d, btnAiRange30d, btnAiRangeCustom].forEach(b => {
            if (b) {
                b.className = 'px-2.5 py-1 rounded-md text-on-surface-variant hover:text-on-surface transition-colors';
            }
        });
        if (btn) {
            btn.className = 'px-2.5 py-1 rounded-md bg-primary text-on-primary font-semibold transition-colors';
        }
    }

    async function loadAiUsageFilters() {
        if (!aiFilterModel || !aiFilterOperation) return;
        try {
            const res = await fetch('/api/admin/ai-usage/filters');
            const data = await res.json();
            if (data.success) {
                // Providers
                if (aiFilterProvider) {
                    const currentProvider = aiFilterProvider.value;
                    aiFilterProvider.innerHTML = '<option value="">All Providers</option>' +
                        (data.providers || []).map(p => `<option value="${escapeHtml(p)}"${p === currentProvider ? ' selected' : ''}>${escapeHtml(p)}</option>`).join('');
                }

                // Models
                const currentModel = aiFilterModel.value;
                aiFilterModel.innerHTML = '<option value="">All Models</option>' +
                    data.models.map(m => `<option value="${escapeHtml(m)}"${m === currentModel ? ' selected' : ''}>${escapeHtml(m)}</option>`).join('');

                // Operations
                const currentOp = aiFilterOperation.value;
                aiFilterOperation.innerHTML = '<option value="">All Operations</option>' +
                    data.operations.map(o => `<option value="${escapeHtml(o)}"${o === currentOp ? ' selected' : ''}>${escapeHtml(o)}</option>`).join('');
            }
        } catch (e) {
            console.error('[AI Usage] Error loading filter options:', e);
        }
    }

    async function loadAiUsageOverview() {
        if (!aiMetricTotalCost) return;
        try {
            const dateParams = getAiDateRangeParams();
            const res = await fetch(`/api/admin/ai-usage/overview?${dateParams}`);
            const data = await res.json();
            if (!data.success) throw new Error(data.message || 'Failed to load overview');

            const s = data.summary;
            const costVal = parseFloat(s.costs.total_estimated_usd || 0);
            aiMetricTotalCost.textContent = `$${costVal.toFixed(4)}`;
            aiMetricTotalAttempts.textContent = s.total_attempts.toLocaleString();
            aiMetricTotalTokens.textContent = s.tokens.total_tokens.toLocaleString();
            aiMetricPromptTokens.textContent = s.tokens.prompt_tokens.toLocaleString();
            aiMetricCompTokens.textContent = s.tokens.completion_tokens.toLocaleString();
            aiMetricSuccessRate.textContent = `${s.success_rate}%`;
            aiMetricSuccessCount.textContent = s.successful_attempts.toLocaleString();
            aiMetricFailedAttempts.textContent = s.failed_attempts.toLocaleString();
            aiMetricUnknownCostCount.textContent = s.costs.unknown_cost_count.toLocaleString();

            // Render Model Breakdown
            const byModel = data.breakdowns.by_model || [];
            if (byModel.length === 0) {
                aiModelBreakdownContainer.innerHTML = '<div class="text-xs text-outline py-2 text-center">No AI model calls in this time window.</div>';
            } else {
                const maxAttempts = Math.max(...byModel.map(m => m.attempts), 1);
                aiModelBreakdownContainer.innerHTML = byModel.map(m => {
                    const pct = Math.round((m.attempts / maxAttempts) * 100);
                    const costFmt = parseFloat(m.estimated_cost_usd || 0).toFixed(4);
                    return `
                        <div class="flex flex-col gap-1 text-xs">
                            <div class="flex justify-between items-center">
                                <span class="font-medium text-on-surface">${escapeHtml(m.model_name)} (${m.attempts} calls)</span>
                                <span class="text-primary font-semibold">$${costFmt} USD</span>
                            </div>
                            <div class="w-full bg-surface-container rounded-full h-1.5 overflow-hidden">
                                <div class="bg-primary h-1.5 rounded-full" style="width: ${pct}%"></div>
                            </div>
                            <div class="flex justify-between text-[10px] text-outline">
                                <span>Tokens: ${m.prompt_tokens.toLocaleString()} in / ${m.completion_tokens.toLocaleString()} out</span>
                                <span>${m.unknown_cost_count > 0 ? `${m.unknown_cost_count} unpriced` : 'all priced'}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            // Render Operation Breakdown
            const byOp = data.breakdowns.by_operation || [];
            if (byOp.length === 0) {
                aiOperationBreakdownContainer.innerHTML = '<div class="text-xs text-outline py-2 text-center">No operations recorded.</div>';
            } else {
                aiOperationBreakdownContainer.innerHTML = byOp.map(o => {
                    const succPct = o.attempts > 0 ? Math.round((o.successful_attempts / o.attempts) * 100) : 0;
                    return `
                        <div class="flex flex-col gap-1 text-xs">
                            <div class="flex justify-between items-center">
                                <span class="font-medium text-on-surface">${escapeHtml(o.operation)}</span>
                                <span class="text-on-surface-variant font-semibold">${o.attempts} reqs (${succPct}% ok)</span>
                            </div>
                            <div class="w-full bg-surface-container rounded-full h-1.5 overflow-hidden flex">
                                <div class="bg-tertiary h-1.5" style="width: ${succPct}%"></div>
                                <div class="bg-error h-1.5" style="width: ${100 - succPct}%"></div>
                            </div>
                            <div class="flex justify-between text-[10px] text-outline">
                                <span>Success: ${o.successful_attempts} | Failed: ${o.failed_attempts}</span>
                                <span>Cost: $${parseFloat(o.estimated_cost_usd || 0).toFixed(4)}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            // Render Daily Cost Trends
            const dailyTrends = data.breakdowns.daily_trends || [];
            if (aiCostTrendsContainer) {
                if (dailyTrends.length === 0) {
                    aiCostTrendsContainer.innerHTML = '<div class="text-xs text-outline py-2 text-center">No cost data recorded in this time range.</div>';
                } else {
                    const maxCost = Math.max(...dailyTrends.map(d => parseFloat(d.estimated_cost_usd || 0)), 0.0001);
                    aiCostTrendsContainer.innerHTML = dailyTrends.map(d => {
                        const costVal = parseFloat(d.estimated_cost_usd || 0);
                        const pct = Math.min(100, Math.max(costVal > 0 ? 4 : 0, Math.round((costVal / maxCost) * 100)));
                        const unknownBadge = d.unknown_cost_count > 0
                            ? `<span class="text-outline italic">(${d.unknown_cost_count} unpriced)</span>`
                            : '';
                        return `
                            <div class="flex flex-col gap-1 text-xs" title="${escapeHtml(d.date)}: $${costVal.toFixed(6)} (${d.attempts} attempts, ${d.unknown_cost_count || 0} unpriced)">
                                <div class="flex justify-between items-center">
                                    <span class="font-medium text-on-surface font-code-sm">${escapeHtml(d.date)}</span>
                                    <span class="text-primary font-semibold">$${costVal.toFixed(4)} USD ${unknownBadge}</span>
                                </div>
                                <div class="w-full bg-surface-container rounded-full h-1.5 overflow-hidden">
                                    <div class="bg-primary h-1.5 rounded-full" style="width: ${pct}%"></div>
                                </div>
                                <div class="flex justify-between text-[10px] text-outline">
                                    <span>${d.attempts} total attempts (${d.failed_attempts} failed)</span>
                                    <span>${d.unknown_cost_count > 0 ? `${d.unknown_cost_count} unverified cost` : 'all priced'}</span>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }

            // Render Daily Token Usage Trends
            if (aiTokensTrendsContainer) {
                if (dailyTrends.length === 0) {
                    aiTokensTrendsContainer.innerHTML = '<div class="text-xs text-outline py-2 text-center">No token usage data recorded in this time range.</div>';
                } else {
                    const maxTokens = Math.max(...dailyTrends.map(d => d.total_tokens || 0), 1);
                    aiTokensTrendsContainer.innerHTML = dailyTrends.map(d => {
                        const totTokens = d.total_tokens || 0;
                        const pct = Math.min(100, Math.max(totTokens > 0 ? 4 : 0, Math.round((totTokens / maxTokens) * 100)));
                        const pTok = (d.prompt_tokens || 0).toLocaleString();
                        const cTok = (d.completion_tokens || 0).toLocaleString();
                        return `
                            <div class="flex flex-col gap-1 text-xs" title="${escapeHtml(d.date)}: ${totTokens.toLocaleString()} tokens (${d.attempts} attempts)">
                                <div class="flex justify-between items-center">
                                    <span class="font-medium text-on-surface font-code-sm">${escapeHtml(d.date)}</span>
                                    <span class="text-on-surface-variant font-semibold">${totTokens.toLocaleString()} tokens</span>
                                </div>
                                <div class="w-full bg-surface-container rounded-full h-1.5 overflow-hidden">
                                    <div class="bg-secondary h-1.5 rounded-full" style="width: ${pct}%"></div>
                                </div>
                                <div class="flex justify-between text-[10px] text-outline">
                                    <span>Prompt: ${pTok} | Comp: ${cTok}</span>
                                    <span>${d.attempts} requests</span>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }

        } catch (e) {
            console.error('[AI Usage] Error loading overview:', e);
            if (aiMetricTotalCost) aiMetricTotalCost.textContent = '$0.00';
            if (aiModelBreakdownContainer) aiModelBreakdownContainer.innerHTML = '<div class="text-xs text-error py-2 text-center">Failed to load model metrics.</div>';
            if (aiCostTrendsContainer) aiCostTrendsContainer.innerHTML = '<div class="text-xs text-error py-2 text-center">Failed to load cost trends.</div>';
            if (aiTokensTrendsContainer) aiTokensTrendsContainer.innerHTML = '<div class="text-xs text-error py-2 text-center">Failed to load token trends.</div>';
        }
    }

    async function loadAiUsageRecords() {
        if (!aiUsageTableBody) return;
        aiUsageTableBody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-on-surface-variant">Loading records...</td></tr>';

        try {
            const params = new URLSearchParams();
            params.append('page', aiCurrentPage);
            params.append('limit', aiPageLimit);

            const dateParams = getAiDateRangeParams();
            if (dateParams) {
                const parts = new URLSearchParams(dateParams);
                for (const [k, v] of parts.entries()) {
                    params.append(k, v);
                }
            }

            if (aiFilterProvider && aiFilterProvider.value) params.append('provider', aiFilterProvider.value);
            if (aiFilterModel && aiFilterModel.value) params.append('model', aiFilterModel.value);
            if (aiFilterOperation && aiFilterOperation.value) params.append('operation', aiFilterOperation.value);
            if (aiFilterStatus && aiFilterStatus.value) params.append('status', aiFilterStatus.value);
            if (aiFilterUserId && aiFilterUserId.value.trim()) params.append('user_id', aiFilterUserId.value.trim());
            if (aiFilterJobId && aiFilterJobId.value.trim()) params.append('job_id', aiFilterJobId.value.trim());
            if (aiFilterCorrelationId && aiFilterCorrelationId.value.trim()) params.append('correlation_id', aiFilterCorrelationId.value.trim());

            const res = await fetch(`/api/admin/ai-usage/records?${params.toString()}`);
            const data = await res.json();
            if (!data.success) throw new Error(data.message || 'Failed to load records');

            const records = data.records || [];
            const pag = data.pagination;

            if (records.length === 0) {
                aiUsageTableBody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-outline">No AI provider telemetry found matching criteria.</td></tr>';
                aiPaginationSummary.textContent = 'Showing 0 of 0 records';
                btnAiPrevPage.disabled = true;
                btnAiNextPage.disabled = true;
                return;
            }

            aiUsageTableBody.innerHTML = records.map(r => {
                const isSuccess = r.status === 'SUCCESS';
                const statusBadge = isSuccess
                    ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-tertiary-fixed text-tertiary">SUCCESS</span>'
                    : `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-error-container text-error" title="${escapeHtml(r.error_category || 'FAILED')}">FAILED</span>`;

                const costStr = r.estimated_cost_usd !== null
                    ? `$${parseFloat(r.estimated_cost_usd).toFixed(6)}`
                    : '<span class="text-outline text-xs italic">Unknown</span>';

                const promptTok = r.prompt_tokens !== null ? r.prompt_tokens.toLocaleString() : '-';
                const compTok = r.completion_tokens !== null ? r.completion_tokens.toLocaleString() : '-';
                const tokensStr = `${promptTok} / ${compTok}`;

                const durationStr = r.duration_ms !== null ? `${r.duration_ms} ms` : '-';
                const timeStr = r.created_at ? new Date(r.created_at).toISOString().replace('T', ' ').slice(0, 19) : '--';
                const shortCorr = r.correlation_id ? r.correlation_id.slice(0, 8) + '...' : '-';

                return `
                    <tr class="hover:bg-surface-container-low/50 text-xs">
                        <td class="py-2.5 px-3 whitespace-nowrap text-on-surface-variant font-code-sm">${timeStr}</td>
                        <td class="py-2.5 px-3">
                            <span class="font-semibold text-on-surface">${escapeHtml(r.model_name)}</span>
                            <span class="block text-[10px] text-outline">${escapeHtml(r.provider)}</span>
                        </td>
                        <td class="py-2.5 px-3 text-on-surface-variant">${escapeHtml(r.operation)}</td>
                        <td class="py-2.5 px-3">${statusBadge}</td>
                        <td class="py-2.5 px-3 text-on-surface-variant whitespace-nowrap">${tokensStr}</td>
                        <td class="py-2.5 px-3 text-on-surface-variant whitespace-nowrap">${durationStr}</td>
                        <td class="py-2.5 px-3 font-semibold text-primary whitespace-nowrap">${costStr}</td>
                        <td class="py-2.5 px-3 text-on-surface-variant whitespace-nowrap">
                            <span>UID: ${r.user_id}</span>
                            ${r.job_id ? `<span class="block text-[10px] text-outline">Job: #${r.job_id}</span>` : ''}
                        </td>
                        <td class="py-2.5 px-3 font-code-sm text-outline" title="${escapeHtml(r.correlation_id || '')}">
                            ${escapeHtml(shortCorr)}
                        </td>
                    </tr>
                `;
            }).join('');

            // Pagination Controls
            const startIdx = ((pag.page - 1) * pag.limit) + 1;
            const endIdx = Math.min(pag.page * pag.limit, pag.total_count);
            aiPaginationSummary.textContent = `Showing ${startIdx}-${endIdx} of ${pag.total_count.toLocaleString()} records`;
            aiPageIndicator.textContent = `${pag.page} / ${pag.total_pages}`;
            btnAiPrevPage.disabled = !pag.has_prev;
            btnAiNextPage.disabled = !pag.has_next;

        } catch (e) {
            console.error('[AI Usage] Error loading records:', e);
            aiUsageTableBody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-error">Failed to load AI usage records.</td></tr>';
        }
    }

    function loadAiUsageDashboard() {
        loadAiUsageOverview();
        loadAiUsageRecords();
    }

    // AI Event Handlers
    if (btnAiRange24h) {
        btnAiRange24h.addEventListener('click', () => {
            aiCurrentRangePreset = '24h';
            setAiRangeButtonActive(btnAiRange24h);
            if (customDateRangeInputs) customDateRangeInputs.classList.add('hidden');
            aiCurrentPage = 1;
            loadAiUsageDashboard();
        });
    }

    if (btnAiRange7d) {
        btnAiRange7d.addEventListener('click', () => {
            aiCurrentRangePreset = '7d';
            setAiRangeButtonActive(btnAiRange7d);
            if (customDateRangeInputs) customDateRangeInputs.classList.add('hidden');
            aiCurrentPage = 1;
            loadAiUsageDashboard();
        });
    }

    if (btnAiRange30d) {
        btnAiRange30d.addEventListener('click', () => {
            aiCurrentRangePreset = '30d';
            setAiRangeButtonActive(btnAiRange30d);
            if (customDateRangeInputs) customDateRangeInputs.classList.add('hidden');
            aiCurrentPage = 1;
            loadAiUsageDashboard();
        });
    }

    if (btnAiRangeCustom) {
        btnAiRangeCustom.addEventListener('click', () => {
            aiCurrentRangePreset = 'custom';
            setAiRangeButtonActive(btnAiRangeCustom);
            if (customDateRangeInputs) customDateRangeInputs.classList.remove('hidden');
        });
    }

    if (btnApplyCustomDate) {
        btnApplyCustomDate.addEventListener('click', () => {
            const startVal = aiCustomStartDate?.value;
            const endVal = aiCustomEndDate?.value;
            if (startVal && endVal) {
                aiCustomStart = new Date(startVal + 'T00:00:00Z').toISOString();
                aiCustomEnd = new Date(endVal + 'T23:59:59Z').toISOString();
                aiCurrentPage = 1;
                loadAiUsageDashboard();
            }
        });
    }

    if (btnRefreshAiUsage) {
        btnRefreshAiUsage.addEventListener('click', () => {
            loadAiUsageFilters();
            loadAiUsageDashboard();
        });
    }

    [aiFilterProvider, aiFilterModel, aiFilterOperation, aiFilterStatus].forEach(sel => {
        if (sel) {
            sel.addEventListener('change', () => {
                aiCurrentPage = 1;
                loadAiUsageRecords();
            });
        }
    });

    let aiFilterDebounce;
    [aiFilterUserId, aiFilterJobId, aiFilterCorrelationId].forEach(inp => {
        if (inp) {
            inp.addEventListener('input', () => {
                clearTimeout(aiFilterDebounce);
                aiFilterDebounce = setTimeout(() => {
                    aiCurrentPage = 1;
                    loadAiUsageRecords();
                }, 300);
            });
        }
    });

    if (btnAiResetFilters) {
        btnAiResetFilters.addEventListener('click', () => {
            if (aiFilterProvider) aiFilterProvider.value = '';
            if (aiFilterModel) aiFilterModel.value = '';
            if (aiFilterOperation) aiFilterOperation.value = '';
            if (aiFilterStatus) aiFilterStatus.value = '';
            if (aiFilterUserId) aiFilterUserId.value = '';
            if (aiFilterJobId) aiFilterJobId.value = '';
            if (aiFilterCorrelationId) aiFilterCorrelationId.value = '';
            aiCurrentPage = 1;
            loadAiUsageRecords();
        });
    }

    if (btnAiPrevPage) {
        btnAiPrevPage.addEventListener('click', () => {
            if (aiCurrentPage > 1) {
                aiCurrentPage--;
                loadAiUsageRecords();
            }
        });
    }

    if (btnAiNextPage) {
        btnAiNextPage.addEventListener('click', () => {
            aiCurrentPage++;
            loadAiUsageRecords();
        });
    }

    // =========================================================================
    // Claude API Configuration & Connection Testing
    // =========================================================================
    const claudeApiKeyInput = document.getElementById('claudeApiKeyInput');
    const claudeKeyStatusText = document.getElementById('claudeKeyStatusText');
    const claudeModelSelect = document.getElementById('claudeModelSelect');
    const claudeModelDiscoveryStatus = document.getElementById('claudeModelDiscoveryStatus');
    const btnDiscoverClaudeModels = document.getElementById('btnDiscoverClaudeModels');
    const claudeTimeoutInput = document.getElementById('claudeTimeoutInput');
    const claudeConfigForm = document.getElementById('claudeConfigForm');
    const btnTestClaudeConnection = document.getElementById('btnTestClaudeConnection');
    const claudeTestResultBox = document.getElementById('claudeTestResultBox');
    const claudeTestBadge = document.getElementById('claudeTestBadge');
    const claudeTestLatency = document.getElementById('claudeTestLatency');
    const claudeTestMessage = document.getElementById('claudeTestMessage');
    const claudeTestTimestamp = document.getElementById('claudeTestTimestamp');

    async function loadClaudeConfig() {
        if (!claudeKeyStatusText) return;
        try {
            const res = await fetch('/api/admin/claude/config', {
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            const data = await res.json();
            if (res.ok && data.success && data.config) {
                const cfg = data.config;
                if (cfg.is_configured) {
                    claudeKeyStatusText.textContent = `Configured: ${cfg.masked_key || '***'}`;
                    claudeKeyStatusText.className = 'text-[11px] text-tertiary mt-1 font-mono';
                } else {
                    claudeKeyStatusText.textContent = 'Not configured';
                    claudeKeyStatusText.className = 'text-[11px] text-outline mt-1 font-mono';
                }
                if (claudeModelSelect && cfg.model) claudeModelSelect.value = cfg.model;
                if (claudeTimeoutInput && cfg.timeout_seconds) claudeTimeoutInput.value = cfg.timeout_seconds;
            }
        } catch (err) {
            console.error('Failed to load Claude configuration:', err);
        }
    }

    if (btnDiscoverClaudeModels) {
        btnDiscoverClaudeModels.addEventListener('click', async () => {
            btnDiscoverClaudeModels.disabled = true;
            btnDiscoverClaudeModels.innerHTML = '<span class="material-symbols-outlined text-[14px] animate-spin">sync</span><span>Fetching...</span>';
            if (claudeModelDiscoveryStatus) claudeModelDiscoveryStatus.textContent = 'Querying Anthropic /v1/models...';

            try {
                const res = await fetch('/api/admin/claude/models', {
                    headers: { 'X-CSRFToken': getCsrfToken() }
                });
                const data = await res.json();
                if (res.ok && data.success && data.result) {
                    const resData = data.result;
                    if (resData.success && resData.models && resData.models.length > 0) {
                        const currentVal = claudeModelSelect.value;
                        claudeModelSelect.innerHTML = resData.models.map(m => {
                            const badge = m.status === 'RETIRED' ? ' [RETIRED]' : (m.status === 'DEPRECATED' ? ' [DEPRECATED]' : '');
                            return `<option value="${escapeHtml(m.id)}">${escapeHtml(m.display_name || m.id)}${badge}</option>`;
                        }).join('');

                        // Set default selection
                        if (resData.models.some(m => m.id === currentVal)) {
                            claudeModelSelect.value = currentVal;
                        } else if (resData.default_recommendation) {
                            claudeModelSelect.value = resData.default_recommendation;
                        }
                        if (claudeModelDiscoveryStatus) {
                            claudeModelDiscoveryStatus.textContent = `Retrieved ${resData.models.length} account models. Default: ${resData.default_recommendation}`;
                            claudeModelDiscoveryStatus.className = 'text-[11px] text-tertiary mt-1 font-mono';
                        }
                    } else {
                        if (claudeModelDiscoveryStatus) {
                            claudeModelDiscoveryStatus.textContent = resData.message || 'No models returned';
                            claudeModelDiscoveryStatus.className = 'text-[11px] text-error mt-1 font-mono';
                        }
                    }
                } else {
                    if (claudeModelDiscoveryStatus) {
                        claudeModelDiscoveryStatus.textContent = data.message || 'Discovery failed';
                        claudeModelDiscoveryStatus.className = 'text-[11px] text-error mt-1 font-mono';
                    }
                }
            } catch (err) {
                if (claudeModelDiscoveryStatus) {
                    claudeModelDiscoveryStatus.textContent = 'Network error during discovery';
                    claudeModelDiscoveryStatus.className = 'text-[11px] text-error mt-1 font-mono';
                }
            } finally {
                btnDiscoverClaudeModels.disabled = false;
                btnDiscoverClaudeModels.innerHTML = '<span class="material-symbols-outlined text-[14px]">sync</span><span>Discover Models</span>';
            }
        });
    }

    if (claudeConfigForm) {
        claudeConfigForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const apiKey = claudeApiKeyInput.value.trim();
            const model = claudeModelSelect.value;
            const timeoutSeconds = parseInt(claudeTimeoutInput.value, 10);

            try {
                const res = await fetch('/api/admin/claude/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        api_key: apiKey || undefined,
                        model: model,
                        timeout_seconds: timeoutSeconds
                    })
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    alert('Claude API settings saved successfully.');
                    claudeApiKeyInput.value = '';
                    await loadClaudeConfig();
                } else {
                    alert('Failed to save Claude settings: ' + (data.message || data.error));
                }
            } catch (err) {
                alert('Network error while saving Claude settings: ' + err.message);
            }
        });
    }

    if (btnTestClaudeConnection) {
        btnTestClaudeConnection.addEventListener('click', async () => {
            const tempKey = claudeApiKeyInput.value.trim();
            const model = claudeModelSelect.value;
            const timeoutSeconds = parseInt(claudeTimeoutInput.value, 10);

            btnTestClaudeConnection.disabled = true;
            btnTestClaudeConnection.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">refresh</span><span>Testing...</span>';
            claudeTestResultBox.classList.remove('hidden');
            claudeTestBadge.textContent = 'RUNNING DIAGNOSTIC...';
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-surface-container text-on-surface';
            claudeTestLatency.textContent = '';
            claudeTestMessage.textContent = 'Contacting Anthropic API with minimal ping payload...';
            claudeTestTimestamp.textContent = '';

            try {
                const res = await fetch('/api/admin/claude/test-connection', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        api_key: tempKey || undefined,
                        model: model,
                        timeout_seconds: timeoutSeconds
                    })
                });
                const data = await res.json();
                if (res.ok && data.success && data.diagnostic) {
                    const diag = data.diagnostic;
                    renderClaudeDiagnosticResult(diag);
                } else {
                    claudeTestBadge.textContent = 'TEST FAILED';
                    claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error-container text-error';
                    claudeTestMessage.textContent = data.message || data.error || 'Server returned an error';
                }
            } catch (err) {
                claudeTestBadge.textContent = 'NETWORK ERROR';
                claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error-container text-error';
                claudeTestMessage.textContent = err.message;
            } finally {
                btnTestClaudeConnection.disabled = false;
                btnTestClaudeConnection.innerHTML = '<span class="material-symbols-outlined text-[16px]">bolt</span><span>Test Connection</span>';
            }
        });
    }

    function renderClaudeDiagnosticResult(diag) {
        const reqStr = diag.request_id ? ` | Req ID: ${escapeHtml(diag.request_id)}` : '';
        claudeTestLatency.textContent = `${diag.latency_ms} ms (${diag.model_used})${reqStr}`;
        claudeTestTimestamp.textContent = `Tested at: ${diag.tested_at}`;
        claudeTestMessage.textContent = diag.message;

        if (diag.status === 'CONNECTED') {
            claudeTestResultBox.className = 'p-space-md rounded-lg border border-tertiary/50 bg-tertiary-fixed/20 text-xs flex flex-col gap-1';
            claudeTestBadge.textContent = 'CONNECTED (HEALTHY)';
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-tertiary text-on-tertiary';
        } else if (diag.status === 'INSUFFICIENT_CREDITS') {
            claudeTestResultBox.className = 'p-space-md rounded-lg border border-warning/50 bg-warning-container/40 text-xs flex flex-col gap-1';
            claudeTestBadge.textContent = 'AUTHENTICATED (ZERO BALANCE / INSUFFICIENT CREDITS)';
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-amber-500 text-white';
        } else if (diag.status === 'AUTHENTICATION_FAILED') {
            claudeTestResultBox.className = 'p-space-md rounded-lg border border-error/50 bg-error-container/30 text-xs flex flex-col gap-1';
            claudeTestBadge.textContent = 'AUTHENTICATION FAILED (INVALID KEY)';
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error text-on-error';
        } else if (diag.status === 'PERMISSION_DENIED') {
            claudeTestResultBox.className = 'p-space-md rounded-lg border border-error/50 bg-error-container/30 text-xs flex flex-col gap-1';
            claudeTestBadge.textContent = 'PERMISSION DENIED (MODEL ACCESS RESTRICTED)';
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error text-on-error';
        } else if (diag.status === 'INVALID_MODEL') {
            claudeTestResultBox.className = 'p-space-md rounded-lg border border-error/50 bg-error-container/30 text-xs flex flex-col gap-1';
            claudeTestBadge.textContent = 'INVALID / UNRECOGNIZED MODEL';
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error text-on-error';
        } else if (diag.status === 'RATE_LIMITED') {
            claudeTestResultBox.className = 'p-space-md rounded-lg border border-warning/50 bg-warning-container/40 text-xs flex flex-col gap-1';
            claudeTestBadge.textContent = 'RATE LIMITED (HTTP 429)';
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-amber-500 text-white';
        } else {
            claudeTestResultBox.className = 'p-space-md rounded-lg border border-border-default bg-surface-container-low text-xs flex flex-col gap-1';
            claudeTestBadge.textContent = diag.status;
            claudeTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-surface-container-high text-on-surface';
        }
    }

    // Initial Load
    loadMetrics();
    loadPricing();
    loadUsers();
    loadClaudeConfig();
    loadGeminiConfig();
    loadAiUsageFilters();

    // ====================================================================
    // Gemini API Configuration & Connection Testing
    // ====================================================================
    const geminiApiKeyInput = document.getElementById('geminiApiKeyInput');
    const geminiKeyStatusText = document.getElementById('geminiKeyStatusText');
    const geminiModelSelect = document.getElementById('geminiModelSelect');
    const geminiModelDiscoveryStatus = document.getElementById('geminiModelDiscoveryStatus');
    const btnDiscoverGeminiModels = document.getElementById('btnDiscoverGeminiModels');
    const geminiTimeoutInput = document.getElementById('geminiTimeoutInput');
    const geminiConfigForm = document.getElementById('geminiConfigForm');
    const btnSaveGeminiConfig = document.getElementById('btnSaveGeminiConfig');
    const btnTestGeminiConnection = document.getElementById('btnTestGeminiConnection');
    const geminiTestResultBox = document.getElementById('geminiTestResultBox');
    const geminiTestBadge = document.getElementById('geminiTestBadge');
    const geminiTestLatency = document.getElementById('geminiTestLatency');
    const geminiTestMessage = document.getElementById('geminiTestMessage');
    const geminiTestTimestamp = document.getElementById('geminiTestTimestamp');

    async function loadGeminiConfig() {
        if (!geminiKeyStatusText) return;
        try {
            const res = await fetch('/api/admin/gemini/config', {
                headers: { 'Accept': 'application/json' }
            });
            const data = await res.json();
            if (data.success && data.config) {
                const cfg = data.config;
                if (cfg.is_configured && cfg.masked_key) {
                    geminiKeyStatusText.textContent = `Configured: ${cfg.masked_key}`;
                    geminiKeyStatusText.className = 'text-[11px] text-tertiary mt-1 font-mono font-semibold';
                    geminiApiKeyInput.placeholder = '•••••••••••••••••••• (Leave blank to keep existing key)';
                } else {
                    geminiKeyStatusText.textContent = 'Not configured. Enter Gemini API key to activate.';
                    geminiKeyStatusText.className = 'text-[11px] text-warning mt-1 font-mono';
                }

                if (geminiTimeoutInput && cfg.timeout_seconds) {
                    geminiTimeoutInput.value = cfg.timeout_seconds;
                }

                if (geminiModelSelect && cfg.supported_models && cfg.supported_models.length > 0) {
                    renderGeminiModelOptions(cfg.supported_models, cfg.model);
                }
            } else {
                geminiKeyStatusText.textContent = 'Status unavailable';
            }
        } catch (err) {
            console.error('[Admin Gemini] Error loading Gemini config:', err);
            if (geminiKeyStatusText) {
                geminiKeyStatusText.textContent = 'Error checking configuration.';
            }
        }
    }

    function renderGeminiModelOptions(models, selectedModel) {
        if (!geminiModelSelect) return;
        geminiModelSelect.innerHTML = '';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === selectedModel) {
                opt.selected = true;
            }
            geminiModelSelect.appendChild(opt);
        });
    }

    if (btnDiscoverGeminiModels) {
        btnDiscoverGeminiModels.addEventListener('click', async () => {
            btnDiscoverGeminiModels.disabled = true;
            btnDiscoverGeminiModels.innerHTML = '<span class="material-symbols-outlined text-[14px] animate-spin">progress_activity</span><span>Discovering...</span>';
            if (geminiModelDiscoveryStatus) geminiModelDiscoveryStatus.textContent = 'Querying Google GenAI models API...';

            try {
                const res = await fetch('/api/admin/gemini/models', {
                    headers: { 'Accept': 'application/json' }
                });
                const data = await res.json();
                if (data.success && data.result) {
                    const resObj = data.result;
                    if (resObj.models && resObj.models.length > 0) {
                        renderGeminiModelOptions(resObj.models, resObj.active_model);
                        if (geminiModelDiscoveryStatus) {
                            geminiModelDiscoveryStatus.textContent = `Discovered ${resObj.total_count} models from Google API.`;
                            geminiModelDiscoveryStatus.className = 'text-[11px] text-tertiary mt-1 font-mono font-semibold';
                        }
                    } else {
                        if (geminiModelDiscoveryStatus) {
                            geminiModelDiscoveryStatus.textContent = resObj.error || 'No active Gemini models returned.';
                            geminiModelDiscoveryStatus.className = 'text-[11px] text-warning mt-1 font-mono';
                        }
                    }
                } else {
                    if (geminiModelDiscoveryStatus) {
                        geminiModelDiscoveryStatus.textContent = data.message || 'Discovery request failed.';
                        geminiModelDiscoveryStatus.className = 'text-[11px] text-error mt-1 font-mono';
                    }
                }
            } catch (err) {
                if (geminiModelDiscoveryStatus) {
                    geminiModelDiscoveryStatus.textContent = `Network error: ${err.message}`;
                    geminiModelDiscoveryStatus.className = 'text-[11px] text-error mt-1 font-mono';
                }
            } finally {
                btnDiscoverGeminiModels.disabled = false;
                btnDiscoverGeminiModels.innerHTML = '<span class="material-symbols-outlined text-[14px]">sync</span><span>Discover Models</span>';
            }
        });
    }

    if (geminiConfigForm) {
        geminiConfigForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            btnSaveGeminiConfig.disabled = true;
            btnSaveGeminiConfig.textContent = 'Saving...';

            const payload = {
                model: geminiModelSelect ? geminiModelSelect.value : null,
                timeout: geminiTimeoutInput ? parseInt(geminiTimeoutInput.value, 10) : 15
            };

            const keyVal = geminiApiKeyInput ? geminiApiKeyInput.value.trim() : '';
            if (keyVal) {
                payload.api_key = keyVal;
            }

            try {
                const res = await fetch('/api/admin/gemini/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    alert(data.message || 'Gemini configuration saved successfully.');
                    if (geminiApiKeyInput) geminiApiKeyInput.value = '';
                    await loadGeminiConfig();
                } else {
                    alert(`Save failed: ${data.message || data.error || 'Unknown error'}`);
                }
            } catch (err) {
                alert(`Error saving Gemini configuration: ${err.message}`);
            } finally {
                btnSaveGeminiConfig.disabled = false;
                btnSaveGeminiConfig.textContent = 'Save Gemini Settings';
            }
        });
    }

    if (btnTestGeminiConnection) {
        btnTestGeminiConnection.addEventListener('click', async () => {
            btnTestGeminiConnection.disabled = true;
            btnTestGeminiConnection.innerHTML = '<span class="material-symbols-outlined animate-spin text-[16px]">progress_activity</span><span>Testing...</span>';

            geminiTestResultBox.classList.remove('hidden');
            geminiTestBadge.textContent = 'RUNNING LIVE DIAGNOSTIC...';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-surface-container text-on-surface';
            geminiTestLatency.textContent = '';
            geminiTestMessage.textContent = 'Contacting Google Gemini API with minimal ping payload...';
            geminiTestTimestamp.textContent = '';

            try {
                const res = await fetch('/api/admin/gemini/test-connection', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        api_key: geminiApiKeyInput && geminiApiKeyInput.value.trim() ? geminiApiKeyInput.value.trim() : null,
                        model: geminiModelSelect ? geminiModelSelect.value : null
                    })
                });

                const data = await res.json();
                if (data.success && data.diagnostic) {
                    const diag = data.diagnostic;
                    renderGeminiDiagnosticResult(diag);
                } else {
                    geminiTestBadge.textContent = 'TEST FAILED';
                    geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error-container text-error';
                    geminiTestMessage.textContent = data.message || data.error || 'Server returned an error';
                }
            } catch (err) {
                geminiTestBadge.textContent = 'NETWORK ERROR';
                geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error-container text-error';
                geminiTestMessage.textContent = err.message;
            } finally {
                btnTestGeminiConnection.disabled = false;
                btnTestGeminiConnection.innerHTML = '<span class="material-symbols-outlined text-[16px]">bolt</span><span>Test Connection</span>';
            }
        });
    }

    function renderGeminiDiagnosticResult(diag) {
        geminiTestLatency.textContent = `${diag.latency_ms} ms (${diag.model_used})`;
        geminiTestTimestamp.textContent = `Tested at: ${diag.tested_at}`;
        geminiTestMessage.textContent = diag.message;

        if (diag.status === 'LIVE_CONNECTION_SUCCESS') {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-tertiary/50 bg-tertiary-fixed/20 text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = 'LIVE CONNECTION SUCCESS (HEALTHY)';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-tertiary text-on-tertiary';
        } else if (diag.status === 'PROVIDER_UNAVAILABLE') {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-warning/50 bg-warning-container/40 text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = 'HIGH DEMAND / TEMPORARILY OVERLOADED (503)';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-amber-500 text-white';
        } else if (diag.status === 'QUOTA_EXCEEDED' || diag.status === 'INSUFFICIENT_CREDITS') {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-warning/50 bg-warning-container/40 text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = 'QUOTA EXCEEDED / RATE LIMITED (429)';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-amber-500 text-white';
        } else if (diag.status === 'AUTHENTICATION_FAILED') {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-error/50 bg-error-container/30 text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = 'AUTHENTICATION FAILED (INVALID KEY)';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error text-on-error';
        } else if (diag.status === 'MODEL_ACCESS_DENIED') {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-error/50 bg-error-container/30 text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = 'PERMISSION DENIED (MODEL ACCESS RESTRICTED)';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error text-on-error';
        } else if (diag.status === 'INVALID_MODEL') {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-error/50 bg-error-container/30 text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = 'INVALID / UNRECOGNIZED MODEL';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-error text-on-error';
        } else if (diag.status === 'NOT_CONFIGURED') {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-warning/50 bg-warning-container/40 text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = 'NOT CONFIGURED';
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-amber-500 text-white';
        } else {
            geminiTestResultBox.className = 'p-space-md rounded-lg border border-border-default bg-surface-container-low text-xs flex flex-col gap-1';
            geminiTestBadge.textContent = diag.status;
            geminiTestBadge.className = 'font-bold px-2 py-0.5 rounded text-[11px] bg-surface-container-high text-on-surface';
        }
    }

    loadAiUsageDashboard();
});

