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
    const token = api.getToken();

    try {
        const url = `/api/reports/${currentInspectionId}/html?token=${token}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const htmlText = await resp.text();

        const iframe = document.createElement('iframe');
        iframe.style.width = '100%';
        iframe.style.minHeight = '750px';
        iframe.style.border = 'none';
        iframe.style.background = '#ffffff';
        iframe.style.borderRadius = '8px';
        iframe.style.boxShadow = '0 4px 16px rgba(0,0,0,0.1)';

        preview.innerHTML = '';
        preview.appendChild(iframe);

        const iframeDoc = iframe.contentWindow.document;
        iframeDoc.open();
        iframeDoc.write(htmlText);
        iframeDoc.close();

        // Adjust iframe height dynamically to fit content
        const updateHeight = () => {
            try {
                if (iframe.contentWindow && iframe.contentWindow.document.body) {
                    const scrollHeight = iframe.contentWindow.document.body.scrollHeight;
                    if (scrollHeight > 200) {
                        iframe.style.height = (scrollHeight + 40) + 'px';
                    }
                }
            } catch (e) {}
        };

        iframe.onload = updateHeight;
        setTimeout(updateHeight, 300);
        setTimeout(updateHeight, 1000);

    } catch (err) {
        console.error('Failed to load report preview:', err);
        preview.innerHTML = `<div class="report-loading"><p style="color:#FF1744;">Failed to load report preview: ${err.message}</p></div>`;
    }
}

async function downloadReport() {
    if (!currentInspectionId) return null;
    const token = api.getToken();

    // Check if running in PyWebView desktop app
    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_report_pdf) {
        showToast('Opening file save dialog...', 'info');
        try {
            const res = await window.pywebview.api.save_report_pdf(currentInspectionId, token);
            if (res && res.success) {
                showToast(`PDF report saved successfully to your PC!`, 'success');
                return res.saved_path;
            } else if (res && res.error) {
                showToast(`Failed to save PDF: ${res.error}`, 'error');
            }
        } catch (err) {
            console.error('PyWebView desktop save error:', err);
        }
    }

    // Web browser fallback: Fetch blob and trigger download via Blob URL
    try {
        showToast('Downloading PDF report...', 'info');
        const url = `/api/reports/${currentInspectionId}/download?token=${token}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP error ${resp.status}`);

        const blob = await resp.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `inspection_report_${currentInspectionId.slice(0, 8)}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
        showToast('PDF report downloaded to your PC!', 'success');
        return true;
    } catch (err) {
        showToast(`Download failed: ${err.message}`, 'error');
        return null;
    }
}

async function sendWhatsAppReport() {
    if (!currentInspectionId) return;

    const phoneInput = document.getElementById('send-client-phone');
    const rawPhone = phoneInput ? phoneInput.value.trim() : '';
    const noteInput = document.getElementById('send-note');
    const note = noteInput ? noteInput.value.trim() : '';

    if (!rawPhone) {
        showToast('Please enter a WhatsApp phone number', 'error');
        return;
    }

    // Clean phone number (keep digits only)
    let cleanPhone = rawPhone.replace(/[^0-9]/g, '');

    // Format local zero prefixes (e.g. 03001234567 -> 923001234567)
    if (cleanPhone.startsWith('0')) {
        cleanPhone = '92' + cleanPhone.substring(1);
    }

    // Step 1: Save/Download PDF report directly to device
    await downloadReport();

    // Step 2: Build PDF report download URL
    const token = api.getToken();
    const pdfUrl = `${window.location.origin}/api/reports/${currentInspectionId}/download?token=${token}`;

    let vehicleInfo = '';
    try {
        const insp = await api.get(`/api/inspections/${currentInspectionId}`);
        if (insp && insp.vehicle) {
            vehicleInfo = `${insp.vehicle.make || ''} ${insp.vehicle.model || ''} (${insp.vehicle.license_plate || 'N/A'})`.trim();
        }
    } catch (err) {
        // Non-critical
    }

    // Step 3: Construct formatted WhatsApp message
    let messageText = `🚗 *Vehicle Inspection Report*\n`;
    if (vehicleInfo) {
        messageText += `*Vehicle:* ${vehicleInfo}\n`;
    }
    messageText += `\nDear Client,\nYour vehicle inspection report PDF has been downloaded to your device.\n\n`;
    messageText += `📄 *Download PDF Report:* ${pdfUrl}\n`;

    if (note) {
        messageText += `\n*Note:* ${note}\n`;
    }

    messageText += `\nThank you for choosing our inspection service!`;

    // Step 4: Check for Web Share API with PDF file (for mobile browsers)
    let sharedViaWebShare = false;
    if (navigator.share && navigator.canShare) {
        try {
            const resp = await fetch(pdfUrl);
            const blob = await resp.blob();
            const pdfFile = new File([blob], `inspection_report_${currentInspectionId.slice(0, 8)}.pdf`, { type: 'application/pdf' });
            if (navigator.canShare({ files: [pdfFile] })) {
                await navigator.share({
                    title: 'Vehicle Inspection Report PDF',
                    text: messageText,
                    files: [pdfFile]
                });
                sharedViaWebShare = true;
                showToast('PDF report shared to WhatsApp!', 'success');
            }
        } catch (shareErr) {
            console.log('Web Share fallback to WhatsApp link:', shareErr);
        }
    }

    if (!sharedViaWebShare) {
        // Open WhatsApp Web or Mobile app deep link in default system browser
        const waUrl = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(messageText)}`;

        if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external_url) {
            window.pywebview.api.open_external_url(waUrl);
        } else {
            window.open(waUrl, '_blank');
        }
        showToast('PDF downloaded! Opening WhatsApp to send report...', 'success');
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
