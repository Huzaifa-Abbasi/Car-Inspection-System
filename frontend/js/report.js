/**
 * Report Preview — generate, download, and send report.
 */

async function generateReport() {
    if (!currentInspectionId) {
        showToast('No active inspection', 'error');
        return;
    }

    // Advance to report phase
    try {
        await api.patch(`/api/inspections/${currentInspectionId}/phase`, { phase: 4 });
    } catch (err) {
        // May already be in this phase
    }

    // Show report nav and navigate
    document.getElementById('nav-report').style.display = '';
    navigateTo('report');

    // Generate the report
    const preview = document.getElementById('report-preview');
    preview.innerHTML = `
        <div class="report-loading">
            <div class="spinner"></div>
            <p>Generating report...</p>
        </div>
    `;

    try {
        await api.post(`/api/reports/${currentInspectionId}/generate`);
        showToast('Report generated successfully!', 'success');
        await loadReportPreview();
    } catch (err) {
        preview.innerHTML = `
            <div class="report-loading">
                <p style="color:#FF1744;">Failed to generate report: ${err.message}</p>
                <button class="btn btn-primary" onclick="generateReport()" style="margin-top:16px;">Retry</button>
            </div>
        `;
    }

    // Pre-fill client email from vehicle owner
    try {
        const insp = await api.get(`/api/inspections/${currentInspectionId}`);
        if (insp.vehicle && insp.vehicle.owner_email) {
            document.getElementById('send-client-email').value = insp.vehicle.owner_email;
        }
    } catch (err) {
        // Non-critical
    }
}

async function loadReportPreview() {
    if (!currentInspectionId) return;

    const preview = document.getElementById('report-preview');

    try {
        const insp = await api.get(`/api/inspections/${currentInspectionId}`);
        const defects = (insp.defects || []).filter(d => d.status !== 'rejected');
        const vehicle = insp.vehicle || {};
        const inspector = insp.inspector || {};

        const severityCounts = { severe: 0, moderate: 0, minor: 0 };
        defects.forEach(d => {
            if (d.severity && severityCounts[d.severity] !== undefined) {
                severityCounts[d.severity]++;
            }
        });

        preview.innerHTML = `
            <div style="font-family:'Inter',sans-serif; color:#1a1a2e;">
                <div style="background:linear-gradient(135deg,#0a0a1a,#1a1a3e); color:white; padding:24px 32px; border-radius:8px; margin-bottom:24px;">
                    <h1 style="font-size:22pt; color:#00E5FF; margin:0;">AutoScan Pro</h1>
                    <p style="color:#aab; font-size:10pt; margin:4px 0 12px;">Professional Vehicle Inspection System</p>
                    <p style="font-size:14pt; font-weight:600; margin:0;">🔍 VEHICLE INSPECTION REPORT</p>
                </div>

                <h3 style="border-bottom:2px solid #00E5FF; padding-bottom:4px; margin-bottom:12px;">Vehicle Information</h3>
                <table style="width:100%; margin-bottom:20px; font-size:10pt;">
                    <tr><td style="font-weight:600; color:#555; width:140px;">Make:</td><td>${vehicle.make || 'N/A'}</td>
                        <td style="font-weight:600; color:#555; width:140px;">Model:</td><td>${vehicle.model || 'N/A'}</td></tr>
                    <tr><td style="font-weight:600; color:#555;">Year:</td><td>${vehicle.year || 'N/A'}</td>
                        <td style="font-weight:600; color:#555;">Color:</td><td>${vehicle.color || 'N/A'}</td></tr>
                    <tr><td style="font-weight:600; color:#555;">License Plate:</td><td>${vehicle.license_plate || 'N/A'}</td>
                        <td style="font-weight:600; color:#555;">VIN:</td><td>${vehicle.vin || 'N/A'}</td></tr>
                </table>

                <h3 style="border-bottom:2px solid #00E5FF; padding-bottom:4px; margin-bottom:12px;">Inspection Details</h3>
                <table style="width:100%; margin-bottom:20px; font-size:10pt;">
                    <tr><td style="font-weight:600; color:#555; width:140px;">Inspector:</td><td>${inspector.name || 'N/A'}</td>
                        <td style="font-weight:600; color:#555; width:140px;">Date:</td><td>${formatDate(insp.started_at)}</td></tr>
                    <tr><td style="font-weight:600; color:#555;">Status:</td><td>${insp.status || 'N/A'}</td>
                        <td style="font-weight:600; color:#555;">Owner:</td><td>${vehicle.owner_name || 'N/A'}</td></tr>
                </table>

                <h3 style="border-bottom:2px solid #00E5FF; padding-bottom:4px; margin-bottom:12px;">Defect Summary</h3>
                ${defects.length > 0 ? `
                    <div style="display:flex; gap:12px; margin:12px 0;">
                        <span style="background:#dc3545; color:white; padding:6px 16px; border-radius:6px; font-weight:700;">🔴 Severe: ${severityCounts.severe}</span>
                        <span style="background:#ff8c00; color:white; padding:6px 16px; border-radius:6px; font-weight:700;">🟠 Moderate: ${severityCounts.moderate}</span>
                        <span style="background:#ffc107; color:#333; padding:6px 16px; border-radius:6px; font-weight:700;">🟡 Minor: ${severityCounts.minor}</span>
                    </div>
                    <p><strong>Total Confirmed Defects:</strong> ${defects.length}</p>

                    <table style="width:100%; border-collapse:collapse; margin-top:12px;">
                        <thead>
                            <tr style="background:#1a1a3e; color:white;">
                                <th style="padding:8px 12px; text-align:left;">#</th>
                                <th style="padding:8px 12px; text-align:left;">Fault Type</th>
                                <th style="padding:8px 12px; text-align:left;">Severity</th>
                                <th style="padding:8px 12px; text-align:left;">Confidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${defects.map((d, i) => `
                                <tr style="border-bottom:1px solid #e0e0e0;${i % 2 === 0 ? '' : 'background:#f8f9fa;'}">
                                    <td style="padding:8px 12px;">${i + 1}</td>
                                    <td style="padding:8px 12px;">${formatFaultType(d.fault_type)}</td>
                                    <td style="padding:8px 12px; font-weight:700; color:${d.severity === 'severe' ? '#dc3545' : d.severity === 'moderate' ? '#ff8c00' : '#c8a000'};">${(d.severity || 'Moderate').charAt(0).toUpperCase() + (d.severity || 'moderate').slice(1)}</td>
                                    <td style="padding:8px 12px;">${Math.round(d.confidence * 100)}%</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                ` : `
                    <div style="text-align:center; padding:32px; color:#28a745; font-size:14pt; font-weight:600;">
                        ✅ No defects found — Vehicle passed inspection
                    </div>
                `}

                ${insp.notes ? `
                    <h3 style="border-bottom:2px solid #00E5FF; padding-bottom:4px; margin:20px 0 12px;">Inspector Notes</h3>
                    <p>${insp.notes}</p>
                ` : ''}

                <div style="margin-top:32px; padding-top:12px; border-top:1px solid #ddd; font-size:9pt; color:#888; text-align:center;">
                    Report generated by AutoScan Pro on ${new Date().toLocaleDateString()}
                </div>
            </div>
        `;
    } catch (err) {
        preview.innerHTML = `<div class="report-loading"><p>Failed to load report preview.</p></div>`;
    }
}

function downloadReport() {
    if (!currentInspectionId) return;
    const token = api.getToken();
    window.open(`/api/reports/${currentInspectionId}/download?token=${token}`, '_blank');
}

async function sendReport() {
    if (!currentInspectionId) return;

    const btn = document.getElementById('send-report-btn');
    btn.disabled = true;

    const clientEmail = document.getElementById('send-client-email').value.trim();
    const managerEmail = document.getElementById('send-manager-email').value.trim();
    const note = document.getElementById('send-note').value.trim();

    if (!clientEmail && !managerEmail) {
        showToast('Please enter at least one email address', 'error');
        btn.disabled = false;
        return;
    }

    try {
        await api.post(`/api/reports/${currentInspectionId}/send`, {
            client_email: clientEmail || null,
            manager_email: managerEmail || null,
            note: note || null,
        });
        showToast('Report sent successfully!', 'success');
    } catch (err) {
        showToast(`Failed to send: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function completeInspection() {
    if (!currentInspectionId) return;

    try {
        await api.patch(`/api/inspections/${currentInspectionId}/phase`, { phase: 5 });
        showToast('Inspection completed! 🎉', 'success');

        // Hide phase-specific nav items
        document.getElementById('nav-detection').style.display = 'none';
        document.getElementById('nav-review').style.display = 'none';
        document.getElementById('nav-report').style.display = 'none';

        currentInspectionId = null;
        navigateTo('dashboard');
    } catch (err) {
        showToast(`Failed to complete: ${err.message}`, 'error');
    }
}

async function goBackToReview() {
    if (!currentInspectionId) return;

    try {
        await api.patch(`/api/inspections/${currentInspectionId}/phase`, { phase: 3 });
        showToast('Returning to review phase...', 'info');

        // Show review nav item, hide report nav item
        document.getElementById('nav-review').style.display = '';
        document.getElementById('nav-report').style.display = 'none';
        navigateTo('review');
    } catch (err) {
        showToast(`Failed to go back: ${err.message}`, 'error');
    }
}
