document.addEventListener('DOMContentLoaded', () => {
    const btnGenerate = document.getElementById('generate-suggestions-btn');
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');
    
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    
    window.showToast = function(message) {
        if (!toast || !toastMessage) return alert(message);
        toastMessage.innerText = message;
        toast.classList.remove('translate-y-20', 'opacity-0', 'pointer-events-none');
        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0', 'pointer-events-none');
        }, 3200);
    };

    window.copyToClipboard = function(elementId, btn) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const textToCopy = el.innerText.replace(/^"|"$/g, '');
        navigator.clipboard.writeText(textToCopy).then(() => {
            showToast('Copied to clipboard');
            const originalContent = btn.innerHTML;
            btn.innerHTML = '<span class="material-symbols-outlined text-[16px] text-tertiary">done</span><span>Copied</span>';
            setTimeout(() => {
                btn.innerHTML = originalContent;
            }, 2000);
        }).catch(() => {
            showToast('Failed to copy');
        });
    };

    if (btnGenerate) {
        btnGenerate.addEventListener('click', async () => {
            const original = btnGenerate.innerHTML;
            btnGenerate.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span><span>Analyzing your profile...</span>';
            btnGenerate.disabled = true;
            
            try {
                const res = await fetch('/api/optimize-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({}) // Backend pulls data from DB
                });
                
                const data = await res.json();
                if (data.success) {
                    showToast('Analysis complete');
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Failed to analyze profile');
                }
            } catch (err) {
                alert('Unable to analyze profile: ' + err.message);
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = original;
            }
        });
    }
});
