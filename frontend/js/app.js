/**
 * App router and initialization.
 */

// Current state
let currentPage = 'dashboard';
let currentInspectionId = null;

// Page title mapping
const pageTitles = {
    'dashboard': 'Dashboard',
    'new-inspection': 'New Inspection',
    'detection': 'Live Detection',
    'review': 'Defect Review',
    'report': 'Report Preview',
    'history': 'Inspection History',
};

/**
 * Navigate to a page.
 */
function navigateTo(page) {
    if (page !== 'detection') {
        if (typeof stopDetectionStream === 'function') {
            stopDetectionStream();
        }
    }

    currentPage = page;

    // Hide all pages, show target
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.add('active');

    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    // Show/hide sidebar camera panel based on page
    const sidebarCameraPanel = document.getElementById('sidebar-camera-panel');
    if (sidebarCameraPanel) {
        sidebarCameraPanel.style.display = (page === 'detection') ? 'flex' : 'none';
    }

    // Update page title
    document.getElementById('page-title').textContent = pageTitles[page] || page;

    // Trigger page-specific load
    switch (page) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'new-inspection':
            resetInspectionForm();
            break;
        case 'history':
            loadHistory();
            break;
        case 'review':
            loadReview();
            break;
        case 'detection':
            if (typeof loadCameraDevices === 'function') {
                loadCameraDevices();
            }
            break;
    }
}

/**
 * Show a toast notification.
 */
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.style.display = '';

    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.style.display = 'none';
    }, 4000);
}

/**
 * Format a date string.
 */
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
    });
}

/**
 * Format fault type for display.
 */
function formatFaultType(name) {
    return (name || '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Get status badge HTML.
 */
function statusBadge(status) {
    return `<span class="status-badge status-${status}">${status}</span>`;
}

/**
 * App initialization — check for existing session.
 */
(function init() {
    const token = localStorage.getItem('auth_token');
    const userJson = localStorage.getItem('auth_user');

    if (token && userJson) {
        try {
            const user = JSON.parse(userJson);
            api.setToken(token);
            enterApp(user);
        } catch {
            logout();
        }
    }
})();
