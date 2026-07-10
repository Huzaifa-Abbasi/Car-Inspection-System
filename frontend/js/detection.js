/**
 * Live Detection — WebSocket video stream and real-time defect tracking.
 */

let ws = null;
let isPaused = false;
let detectedDefects = [];
let videoCanvas = null;
let videoCtx = null;
let localStream = null;
let captureInterval = null;

function toggleBrowserCamera(checked) {
    const panel = document.querySelector('.camera-manager-panel');
    if (panel) {
        panel.style.display = checked ? 'none' : 'flex';
    }
}

const defaultDevices = [
    { label: 'Default Camera (Webcam)', value: '0', _isDefault: true },
    { label: 'OBS/DroidCam Virtual Camera', value: '1', _isDefault: true }
];

function toggleAddDeviceForm(show) {
    const form = document.getElementById('add-device-form');
    if (form) {
        form.style.display = show ? 'grid' : 'none';
    }
    if (show) {
        document.getElementById('new-device-label').value = '';
        document.getElementById('new-device-value').value = '';
    }
}

function loadCameraDevices() {
    let devicesRaw = localStorage.getItem('car_inspection_cameras');
    let customDevices = [];
    if (devicesRaw) {
        try {
            customDevices = JSON.parse(devicesRaw);
            // Migrate: filter out default devices from custom device list
            customDevices = customDevices.filter(d => d.value !== '0' && d.value !== '1');
        } catch (e) {
            console.error('[Camera] Error parsing custom devices:', e);
        }
    }

    let deviceList = [...defaultDevices, ...customDevices];
    
    // Normalize comparison of camera values / URLs to check for duplicates
    const hasUrlOrValue = (val) => {
        return deviceList.some(d => {
            const v1 = d.value.replace(/\/+$/, '').toLowerCase();
            const v2 = val.replace(/\/+$/, '').toLowerCase();
            return v1 === v2 || v1 + '/video' === v2 || v1 === v2 + '/video';
        });
    };

    // Populate select dropdown
    const populateSelect = () => {
        const selectEl = document.getElementById('sel-camera-source');
        if (!selectEl) return;
        const prevValue = selectEl.value;

        if (deviceList.length === 0) {
            selectEl.innerHTML = '<option value="" disabled selected>No cameras found — add an IP stream below</option>';
            return;
        }

        selectEl.innerHTML = deviceList.map(d => `<option value="${d.value}">${d.label}</option>`).join('');
        if (prevValue && deviceList.some(d => d.value === prevValue)) {
            selectEl.value = prevValue;
        } else {
            selectEl.value = deviceList[0].value;
        }
    };

    // Populate custom devices list with delete buttons
    const populateCustomList = () => {
        const customListEl = document.getElementById('custom-devices-list');
        if (!customListEl) return;
        
        // Only show actual user-added custom streams in the Saved Devices list (exclude defaults and auto-detected)
        const savedCustomDevices = deviceList.filter(d => !d._isDefault && !d._autoDetected);
        
        if (savedCustomDevices.length === 0) {
            customListEl.innerHTML = '';
        } else {
            customListEl.innerHTML = '<span style="font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); width: 100%; margin-top: 6px;">Saved Devices:</span>' + 
            savedCustomDevices.map(d => `
                <span class="custom-device-tag" style="display: inline-flex; align-items: center; gap: 6px; background: rgba(0, 229, 255, 0.08); border: 1px solid var(--accent-cyan-glow); padding: 4px 10px; border-radius: 12px; color: var(--accent-cyan); font-size: 0.75rem;">
                    ${d.label}
                    <span onclick="removeCameraDevice('${d.value}')" style="cursor: pointer; font-weight: bold; color: var(--accent-red); margin-left: 4px; font-size: 0.95rem; line-height: 1;" title="Remove device">&times;</span>
                </span>
            `).join('');
        }
    };

    populateSelect();
    populateCustomList();

    // Asynchronously detect local cameras and DroidCam streams
    fetch('/api/cameras/detect')
        .then(res => res.json())
        .then(data => {
            let updated = false;

            // Add detected local cameras
            if (data.cameras && data.cameras.length > 0) {
                data.cameras.forEach(idx => {
                    const idxStr = String(idx);
                    if (!hasUrlOrValue(idxStr)) {
                        deviceList.push({ label: `Local Camera ${idx}`, value: idxStr, _autoDetected: true });
                        updated = true;
                    }
                });
            }

            // Add discovered DroidCam streams
            if (data.streams && data.streams.length > 0) {
                data.streams.forEach(stream => {
                    if (!hasUrlOrValue(stream.url)) {
                        deviceList.push({ label: stream.label, value: stream.url, _autoDetected: true });
                        updated = true;
                    }
                });
            }

            if (updated) {
                populateSelect();
                populateCustomList();
            }
        })
        .catch(err => console.error('[Camera Detection] Async scan error:', err));
}

function addCameraDevice() {
    const label = document.getElementById('new-device-label').value.trim();
    const value = document.getElementById('new-device-value').value.trim();

    if (!label || !value) {
        showToast('Please fill out both fields', 'error');
        return;
    }

    let devicesRaw = localStorage.getItem('car_inspection_cameras');
    let customDevices = [];
    if (devicesRaw) {
        try {
            customDevices = JSON.parse(devicesRaw).filter(d => d.value !== '0' && d.value !== '1');
        } catch (e) {}
    }

    // Check duplicate value (against defaults + current custom devices)
    const currentList = [...defaultDevices, ...customDevices];
    const isDuplicate = currentList.some(d => {
        const v1 = d.value.replace(/\/+$/, '').toLowerCase();
        const v2 = value.replace(/\/+$/, '').toLowerCase();
        return v1 === v2 || v1 + '/video' === v2 || v1 === v2 + '/video';
    });

    if (isDuplicate) {
        showToast('Device source or URL already exists', 'error');
        return;
    }

    customDevices.push({ label, value });
    localStorage.setItem('car_inspection_cameras', JSON.stringify(customDevices));
    showToast(`Device "${label}" added successfully`, 'success');

    loadCameraDevices();
    toggleAddDeviceForm(false);

    // Select the newly added device
    const selectEl = document.getElementById('sel-camera-source');
    if (selectEl) {
        selectEl.value = value;
        onCameraSourceChange(value);
    }
}

function removeCameraDevice(value) {
    let devicesRaw = localStorage.getItem('car_inspection_cameras');
    if (!devicesRaw) return;

    try {
        let customDevices = JSON.parse(devicesRaw);
        customDevices = customDevices.filter(d => d.value !== value);
        localStorage.setItem('car_inspection_cameras', JSON.stringify(customDevices));
        showToast('Device removed', 'info');
    } catch (e) {
        console.error('[Camera] Error removing device:', e);
    }

    // If the removed device was selected, reset to '0'
    const selectEl = document.getElementById('sel-camera-source');
    if (selectEl && selectEl.value === value) {
        selectEl.value = '0';
    }

    loadCameraDevices();
}

function onCameraSourceChange(value) {
    console.log('[Camera] Source selected:', value);
    // If a scan is currently active, restart the stream with the new camera
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('[Camera] Live-switching camera to:', value);
        stopDetectionStream();
        // Small delay to allow cleanup before reconnecting
        setTimeout(() => {
            startDetectionStream();
        }, 300);
    }
}

function stopBrowserCamera() {
    if (captureInterval) {
        clearInterval(captureInterval);
        captureInterval = null;
    }
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }
}

function stopDetectionStream() {
    stopBrowserCamera();
    if (ws) {
        try {
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
                ws.close();
            }
        } catch (e) {
            console.error('[WS] Error closing socket:', e);
        }
        ws = null;
    }
}

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

    // Setup camera manager
    loadCameraDevices();

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const requireVehicle = document.getElementById('chk-require-vehicle').checked;
    const confThreshold = document.getElementById('rng-conf-threshold').value;
    const iouThreshold = document.getElementById('rng-iou-threshold').value;
    const useBrowserCamera = document.getElementById('chk-use-browser-camera').checked;
    
    const selectEl = document.getElementById('sel-camera-source');
    const cameraSrc = selectEl ? selectEl.value : '0';

    const wsUrl = `${protocol}//${window.location.host}/ws/inspect/${currentInspectionId}?require_vehicle=${requireVehicle}&conf_threshold=${confThreshold}&iou_threshold=${iouThreshold}&use_client_camera=${useBrowserCamera}&camera_src=${encodeURIComponent(cameraSrc)}`;

    try {
        ws = new WebSocket(wsUrl);
    } catch (err) {
        showToast('Failed to connect to camera', 'error');
        return;
    }

    ws.onopen = async () => {
        console.log('[WS] Connected to inspection stream');
        showToast('Camera connected. Scanning...', 'success');

        if (useBrowserCamera) {
            try {
                // Initialize browser camera stream
                localStream = await navigator.mediaDevices.getUserMedia({
                    video: { width: 640, height: 480 }
                });

                // Create a temporary video element to play the stream so we can draw it on canvas
                const videoEl = document.createElement('video');
                videoEl.srcObject = localStream;
                videoEl.autoplay = true;
                videoEl.playsInline = true;

                // Wait for video metadata to load so we know its size
                await new Promise((resolve) => {
                    videoEl.onloadedmetadata = () => {
                        resolve();
                    };
                });

                // Create offscreen canvas for capturing frames
                const offscreenCanvas = document.createElement('canvas');
                offscreenCanvas.width = 640;
                offscreenCanvas.height = 480;
                const offscreenCtx = offscreenCanvas.getContext('2d');

                // Start capture interval (~100ms)
                captureInterval = setInterval(() => {
                    if (isPaused) return;
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        // Draw current frame to offscreen canvas
                        offscreenCtx.drawImage(videoEl, 0, 0, offscreenCanvas.width, offscreenCanvas.height);
                        
                        // Convert to base64 JPEG
                        const dataUrl = offscreenCanvas.toDataURL('image/jpeg', 0.75);
                        
                        // Send through WebSocket
                        ws.send(JSON.stringify({
                            type: 'frame',
                            data: dataUrl
                        }));
                    }
                }, 100);

            } catch (err) {
                console.error('[Browser Camera] Error initializing:', err);
                showToast('Failed to access browser camera: ' + err.message, 'error');
                stopDetectionStream();
            }
        }
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
        stopBrowserCamera();
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
        try {
            ws.send(JSON.stringify({ command: 'end_scan' }));
        } catch (e) {
            console.error('[WS] Error sending end_scan:', e);
        }
    }
    stopDetectionStream();

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
