/**
 * Inspection History — filterable table of all past inspections.
 */

async function loadHistory() {
    const status = document.getElementById('filter-status').value;
    const search = document.getElementById('filter-search').value.trim();
    const tbody = document.getElementById('history-body');

    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Loading...</td></tr>';
    
    // Reset selection state
    const selectAllCheckbox = document.getElementById('select-all-inspections');
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    const deleteBtn = document.getElementById('btn-delete-selected');
    if (deleteBtn) deleteBtn.style.display = 'none';

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
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Failed to load history: ${err.message}</td></tr>`;
    }
}

function renderHistoryTable(inspections) {
    const tbody = document.getElementById('history-body');
    const currentUser = JSON.parse(localStorage.getItem('auth_user'));

    if (!inspections || inspections.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No inspections found.</td></tr>';
        return;
    }

    tbody.innerHTML = inspections.map(insp => {
        const vehicle = insp.vehicle;
        const vehicleName = vehicle ? `${vehicle.make} ${vehicle.model}` : 'Unknown';
        const plate = vehicle && vehicle.license_plate ? ` (${vehicle.license_plate})` : '';
        const inspector = insp.inspector ? insp.inspector.name : 'Unknown';
        const defectCount = insp.defects ? insp.defects.length : '—';
        const canDelete = currentUser && (currentUser.role === 'manager' || currentUser.id === insp.inspector_id);

        return `
            <tr>
                <td style="text-align: center;">
                    <input type="checkbox" class="inspection-checkbox" data-id="${insp.id}" ${canDelete ? '' : 'disabled style="opacity: 0.3; cursor: not-allowed;"'} onchange="updateDeleteSelectedButtonState()">
                </td>
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
                    ${canDelete ? `
                        <button class="btn-icon btn-icon-danger" onclick="deleteInspection('${insp.id}')" title="Delete Inspection" style="color: var(--accent-red);">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
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

async function deleteInspection(inspectionId) {
    if (!confirm('Are you sure you want to delete this inspection and all of its defect data? This action cannot be undone.')) {
        return;
    }

    try {
        await api.delete(`/api/inspections/${inspectionId}`);
        showToast('Inspection deleted successfully', 'success');
        loadHistory();
    } catch (err) {
        showToast(`Failed to delete inspection: ${err.message}`, 'error');
    }
}

function toggleSelectAllInspections(checked) {
    const checkboxes = document.querySelectorAll('.inspection-checkbox');
    checkboxes.forEach(cb => {
        if (!cb.disabled) {
            cb.checked = checked;
        }
    });
    updateDeleteSelectedButtonState();
}

function updateDeleteSelectedButtonState() {
    const checkboxes = document.querySelectorAll('.inspection-checkbox');
    const checkedBoxes = Array.from(checkboxes).filter(cb => cb.checked);
    const deleteBtn = document.getElementById('btn-delete-selected');
    const headerCheckbox = document.getElementById('select-all-inspections');

    if (checkedBoxes.length > 0) {
        deleteBtn.style.display = 'flex';
    } else {
        deleteBtn.style.display = 'none';
    }

    // Update main header checkbox state
    const enabledCheckboxes = Array.from(checkboxes).filter(cb => !cb.disabled);
    if (enabledCheckboxes.length > 0 && enabledCheckboxes.every(cb => cb.checked)) {
        headerCheckbox.checked = true;
    } else {
        headerCheckbox.checked = false;
    }
}

async function deleteSelectedInspections() {
    const checkedBoxes = Array.from(document.querySelectorAll('.inspection-checkbox')).filter(cb => cb.checked);
    const ids = checkedBoxes.map(cb => cb.getAttribute('data-id'));

    if (ids.length === 0) return;

    if (!confirm(`Are you sure you want to delete the ${ids.length} selected inspections and all of their defect data? This action cannot be undone.`)) {
        return;
    }

    const deleteBtn = document.getElementById('btn-delete-selected');
    deleteBtn.disabled = true;
    deleteBtn.textContent = 'Deleting...';

    try {
        await Promise.all(ids.map(id => api.delete(`/api/inspections/${id}`)));
        showToast(`${ids.length} inspections deleted successfully`, 'success');
        
        // Reset controls
        document.getElementById('select-all-inspections').checked = false;
        deleteBtn.style.display = 'none';
        
        loadHistory();
    } catch (err) {
        showToast(`Failed to delete selected inspections: ${err.message}`, 'error');
    } finally {
        deleteBtn.disabled = false;
        deleteBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
            Delete Selected
        `;
    }
}
