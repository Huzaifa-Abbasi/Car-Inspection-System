/**
 * Dashboard — load summary stats and recent inspections.
 */

async function loadDashboard() {
    try {
        // Load summary stats
        const summary = await api.get('/api/inspections/summary');
        document.getElementById('stat-active').textContent = summary.active_inspections;
        document.getElementById('stat-completed').textContent = summary.completed_today;
        document.getElementById('stat-pending').textContent = summary.pending_reports;
        document.getElementById('stat-vehicles').textContent = summary.total_vehicles;

        // Load recent inspections
        const inspections = await api.get('/api/inspections?limit=10');
        renderRecentInspections(inspections);

    } catch (err) {
        console.error('Failed to load dashboard:', err);
        showToast('Failed to load dashboard data', 'error');
    }
}

function renderRecentInspections(inspections) {
    const tbody = document.getElementById('recent-inspections-body');

    if (!inspections || inspections.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No inspections yet. Start your first one!</td></tr>';
        return;
    }

    tbody.innerHTML = inspections.map(insp => {
        const vehicle = insp.vehicle;
        const vehicleName = vehicle ? `${vehicle.make} ${vehicle.model}` : 'Unknown';
        const inspector = insp.inspector ? insp.inspector.name : 'Unknown';
        const defectCount = insp.defects ? insp.defects.length : '—';

        return `
            <tr>
                <td>${formatDate(insp.started_at)}</td>
                <td>${vehicleName}</td>
                <td>${inspector}</td>
                <td>${statusBadge(insp.status)}</td>
                <td>${defectCount}</td>
                <td>
                    <button class="btn-icon" onclick="viewInspection('${insp.id}')" title="View">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function viewInspection(inspectionId) {
    currentInspectionId = inspectionId;
    try {
        const insp = await api.get(`/api/inspections/${inspectionId}`);

        // Navigate based on status
        if (insp.status === 'scanning') {
            document.getElementById('nav-detection').style.display = '';
            navigateTo('detection');
        } else if (insp.status === 'reviewing') {
            document.getElementById('nav-review').style.display = '';
            navigateTo('review');
        } else if (insp.status === 'completed') {
            document.getElementById('nav-report').style.display = '';
            navigateTo('report');
            loadReportPreview();
        } else {
            navigateTo('new-inspection');
        }
    } catch (err) {
        showToast('Failed to load inspection', 'error');
    }
}
