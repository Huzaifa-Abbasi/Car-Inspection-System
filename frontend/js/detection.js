/**
 * Live Detection — WebSocket video stream and real-time defect tracking.
 */

let ws = null;
let isPaused = false;
let detectedDefects = [];
let videoCanvas = null;
let videoCtx = null;

function startDetectionStream() {
    if (!currentInspectionId) {
        showToast('No active inspection', 'error');
        return;
    }

    // Setup canvas
    videoCanvas = document.getElementById('video-canvas');
    videoCtx = videoCanvas.getContext('2d');

    // Reset state
    isPaused = false;
    detectedDefects = [];
    updateDetectionList();
    updatePauseButton();

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const requireVehicle = document.getElementById('chk-require-vehicle').checked;
    const confThreshold = document.getElementById('rng-conf-threshold').value;
    const iouThreshold = document.getElementById('rng-iou-threshold').value;
    const wsUrl = `${protocol}//${window.location.host}/ws/inspect/${currentInspectionId}?require_vehicle=${requireVehicle}&conf_threshold=${confThreshold}&iou_threshold=${iouThreshold}`;

    try {
        ws = new WebSocket(wsUrl);
    } catch (err) {
        showToast('Failed to connect to camera', 'error');
        return;
    }

    ws.onopen = () => {
        console.log('[WS] Connected to inspection stream');
        showToast('Camera connected. Scanning...', 'success');
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWSMessage(msg);
        } catch (err) {
            console.error('[WS] Parse error:', err);
        }
    };

    ws.onerror = (err) => {
        console.error('[WS] Error:', err);
        showToast('Camera connection error', 'error');
    };

    ws.onclose = () => {
        console.log('[WS] Disconnected');
    };
}

function handleWSMessage(msg) {
    switch (msg.type) {
        case 'frame':
            renderFrame(msg.data);
            break;

        case 'detections':
            // Update the live detection counter but don't duplicate saved ones
            break;

        case 'defect_saved':
            addDetectedDefect(msg);
            break;

        case 'status':
            if (msg.message === 'Paused') {
                document.getElementById('scanning-indicator').querySelector('span').textContent = 'PAUSED';
            } else if (msg.message.includes('scanning') || msg.message.includes('Resumed')) {
                document.getElementById('scanning-indicator').querySelector('span').textContent = 'SCANNING...';
            }
            break;

        case 'error':
            showToast(`Detection error: ${msg.message}`, 'error');
            break;
    }
}

function renderFrame(base64Data) {
    const img = new Image();
    img.onload = () => {
        // Resize canvas to match image aspect ratio
        const container = videoCanvas.parentElement;
        const containerW = container.clientWidth;
        const containerH = container.clientHeight;

        const scale = Math.min(containerW / img.width, containerH / img.height);
        videoCanvas.width = img.width * scale;
        videoCanvas.height = img.height * scale;

        videoCtx.drawImage(img, 0, 0, videoCanvas.width, videoCanvas.height);
    };
    img.src = `data:image/jpeg;base64,${base64Data}`;
}

function addDetectedDefect(defectMsg) {
    detectedDefects.push({
        id: defectMsg.defect_id,
        fault_type: defectMsg.fault_type,
        confidence: defectMsg.confidence,
        time: new Date().toLocaleTimeString(),
    });

    updateDetectionList();
}

function updateDetectionList() {
    const listEl = document.getElementById('detection-list');
    const countEl = document.getElementById('defect-count');

    countEl.textContent = `${detectedDefects.length} found`;

    if (detectedDefects.length === 0) {
        listEl.innerHTML = `
            <div class="empty-detection">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <p>Scanning for defects...</p>
            </div>
        `;
        return;
    }

    // Show most recent first
    listEl.innerHTML = [...detectedDefects].reverse().map(d => {
        const color = getFaultColor(d.fault_type);
        return `
            <div class="detection-item">
                <div class="detection-dot" style="background:${color}"></div>
                <div class="detection-info">
                    <div class="detection-type">${formatFaultType(d.fault_type)}</div>
                    <div class="detection-conf">${Math.round(d.confidence * 100)}% • ${d.time}</div>
                </div>
            </div>
        `;
    }).join('');
}

function getFaultColor(faultType) {
    const colors = {
        'front-windscreen-damage': '#FF8000',
        'headlight-damage': '#00FFFF',
        'rear-windscreen-damage': '#FF00FF',
        'runningboard-damage': '#FFA500',
        'sidemirror-damage': '#FF0080',
        'taillight-damage': '#00FF80',
        'bonnet-dent': '#FF0000',
        'boot-dent': '#0080FF',
        'doorouter-dent': '#0000FF',
        'fender-dent': '#8000FF',
        'front-bumper-dent': '#00FF00',
        'quaterpanel-dent': '#FFFF00',
        'rear-bumper-dent': '#80FF00',
        'roof-dent': '#FFC0CB',
        'scratch': '#FFC81E',
    };
    return colors[faultType] || '#00E5FF';
}

function togglePause() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    isPaused = !isPaused;
    ws.send(JSON.stringify({ command: isPaused ? 'pause' : 'resume' }));
    updatePauseButton();
}

function updatePauseButton() {
    const btn = document.getElementById('btn-pause');
    if (isPaused) {
        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Resume
        `;
    } else {
        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
            Pause
        `;
    }
}

async function endScan() {
    // Send end command via WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: 'end_scan' }));
        ws.close();
        ws = null;
    }

    // Advance to review phase
    if (currentInspectionId) {
        try {
            await api.patch(`/api/inspections/${currentInspectionId}/phase`, { phase: 3 });
            showToast('Scan complete! Review detected defects.', 'success');

            // Show review nav and navigate
            document.getElementById('nav-review').style.display = '';
            navigateTo('review');
        } catch (err) {
            showToast(`Failed to advance phase: ${err.message}`, 'error');
        }
    }
}

function toggleRequireVehicle(checked) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            command: 'set_require_vehicle',
            value: checked
        }));
    }
}

function updateConfThreshold(val) {
    document.getElementById('lbl-conf-threshold').textContent = val;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            command: 'set_conf_threshold',
            value: parseFloat(val)
        }));
    }
}

function updateIouThreshold(val) {
    document.getElementById('lbl-iou-threshold').textContent = val;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            command: 'set_iou_threshold',
            value: parseFloat(val)
        }));
    }
}
