/**
 * Defect Review — confirm/reject defects, set severity.
 */

let reviewDefects = [];

async function loadReview() {
    if (!currentInspectionId) return;

    try {
        const defects = await api.get(`/api/defects/inspection/${currentInspectionId}`);
        reviewDefects = defects;
        renderReviewCards();
        updateReviewSummary();
    } catch (err) {
        showToast('Failed to load defects for review', 'error');
    }
}

function renderReviewCards() {
    const grid = document.getElementById('defect-grid');

    if (!reviewDefects || reviewDefects.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align:center; padding:60px; color:var(--text-muted);">
                <p>No defects detected during scanning.</p>
                <button class="btn btn-primary" style="margin-top:16px;" onclick="generateReport()">Generate Clean Report</button>
            </div>
        `;
        return;
    }

    grid.innerHTML = reviewDefects.map((defect, idx) => {
        const imgSrc = defect.snapshot_path
            ? `/uploads/${defect.snapshot_path}`
            : '';
        const isConfirmed = defect.status === 'confirmed';
        const isRejected = defect.status === 'rejected';

        return `
            <div class="defect-card" id="defect-card-${defect.id}">
                <div class="defect-card-image">
                    ${imgSrc
                        ? `<img src="${imgSrc}" alt="${defect.fault_type}" onerror="this.parentElement.innerHTML='<span style=\\'color:var(--text-muted)\\'>No image</span>'">`
                        : '<span style="color:var(--text-muted)">No snapshot</span>'
                    }
                </div>
                <div class="defect-card-body">
                    <div class="defect-card-type">
                        <span class="fault-badge">${formatFaultType(defect.fault_type)}</span>
                        <span style="font-size:0.8rem;color:var(--text-secondary);">${Math.round(defect.confidence * 100)}%</span>
                    </div>
                    <div class="defect-card-meta">
                        Detected at ${formatDate(defect.detected_at)}
                    </div>
                    <div class="defect-card-controls">
                        <select onchange="updateDefectSeverity('${defect.id}', this.value)"
                                id="severity-${defect.id}">
                            <option value="minor" ${defect.severity === 'minor' ? 'selected' : ''}>Minor</option>
                            <option value="moderate" ${defect.severity === 'moderate' ? 'selected' : ''}>Moderate</option>
                            <option value="severe" ${defect.severity === 'severe' ? 'selected' : ''}>Severe</option>
                        </select>
                        <button class="btn-confirm ${isConfirmed ? 'active' : ''}"
                                onclick="updateDefectStatus('${defect.id}', 'confirmed')"
                                title="Confirm">✓</button>
                        <button class="btn-reject ${isRejected ? 'active' : ''}"
                                onclick="updateDefectStatus('${defect.id}', 'rejected')"
                                title="Reject">✕</button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function updateReviewSummary() {
    const detected = reviewDefects.length;
    const confirmed = reviewDefects.filter(d => d.status === 'confirmed').length;
    const rejected = reviewDefects.filter(d => d.status === 'rejected').length;
    const pending = reviewDefects.filter(d => d.status === 'detected').length;

    document.getElementById('rev-detected').textContent = detected;
    document.getElementById('rev-confirmed').textContent = confirmed;
    document.getElementById('rev-rejected').textContent = rejected;
    document.getElementById('rev-pending').textContent = pending;
}

async function updateDefectSeverity(defectId, severity) {
    try {
        const updated = await api.patch(`/api/defects/${defectId}`, { severity });
        // Update local state
        const idx = reviewDefects.findIndex(d => d.id === defectId);
        if (idx !== -1) reviewDefects[idx] = updated;
    } catch (err) {
        showToast('Failed to update severity', 'error');
    }
}

async function updateDefectStatus(defectId, status) {
    try {
        const updated = await api.patch(`/api/defects/${defectId}`, { status });
        // Update local state
        const idx = reviewDefects.findIndex(d => d.id === defectId);
        if (idx !== -1) reviewDefects[idx] = updated;

        renderReviewCards();
        updateReviewSummary();
    } catch (err) {
        showToast('Failed to update status', 'error');
    }
}
