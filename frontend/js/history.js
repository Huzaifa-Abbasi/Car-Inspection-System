/**
 * Inspection History — filterable table of all past inspections.
 */

async function loadHistory() {
    const status = document.getElementById('filter-status').value;
    const search = document.getElementById('filter-search').value.trim();
    const tbody = document.getElementById('history-body');

    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Loading...</td></tr>';

    try {
        let url = '/api/inspections?limit=100';
        if (status) url += `&status=${status}`;

        const inspections = await api.get(url);

        // Client-side search filter
        let filtered = inspections;
        if (search) {
            const s = search.toLowerCase();
            filtered = inspections.filter(insp => {
                const v = insp.vehicle;
                if (!v) return false;
                return (
                    (v.make || '').toLowerCase().includes(s) ||
                    (v.model || '').toLowerCase().includes(s) ||
                    (v.license_plate || '').toLowerCase().includes(s) ||
                    (v.vin || '').toLowerCase().includes(s) ||
                    (v.owner_name || '').toLowerCase().includes(s)
                );
            });
        }

        renderHistoryTable(filtered);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Failed to load history: ${err.message}</td></tr>`;
    }
}

function renderHistoryTable(inspections) {
    const tbody = document.getElementById('history-body');

    if (!inspections || inspections.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No inspections found.</td></tr>';
        return;
    }

    tbody.innerHTML = inspections.map(insp => {
        const vehicle = insp.vehicle;
        const vehicleName = vehicle ? `${vehicle.make} ${vehicle.model}` : 'Unknown';
        const plate = vehicle && vehicle.license_plate ? ` (${vehicle.license_plate})` : '';
        const inspector = insp.inspector ? insp.inspector.name : 'Unknown';
        const defectCount = insp.defects ? insp.defects.length : '—';

        return `
            <tr>
                <td>${formatDate(insp.started_at)}</td>
                <td>${vehicleName}${plate}</td>
                <td>${inspector}</td>
                <td>${statusBadge(insp.status)}</td>
                <td>${defectCount}</td>
                <td>
                    <button class="btn-icon" onclick="viewInspection('${insp.id}')" title="View Details">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    </button>
                    ${insp.status === 'completed' ? `
                        <button class="btn-icon" onclick="downloadHistoryReport('${insp.id}')" title="Download Report">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
    }).join('');
}

function downloadHistoryReport(inspectionId) {
    const token = api.getToken();
    window.open(`/api/reports/${inspectionId}/download?token=${token}`, '_blank');
}
