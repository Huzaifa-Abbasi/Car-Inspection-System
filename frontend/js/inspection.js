/**
 * New Inspection — multi-step form and creation logic.
 */

let currentStep = 1;

function resetInspectionForm() {
    currentStep = 1;
    document.getElementById('inspection-form').reset();
    updateStepperUI();
}

function goToStep(step) {
    // Validate current step before advancing
    if (step > currentStep) {
        if (!validateStep(currentStep)) return;
    }

    currentStep = step;
    updateStepperUI();

    // If going to step 3 (confirm), populate the summary
    if (step === 3) {
        populateConfirmSummary();
    }
}

function validateStep(step) {
    if (step === 1) {
        const make = document.getElementById('v-make').value.trim();
        const model = document.getElementById('v-model').value.trim();
        if (!make || !model) {
            showToast('Please enter vehicle make and model', 'error');
            return false;
        }
    }
    return true;
}

function updateStepperUI() {
    // Update stepper dots
    document.querySelectorAll('.stepper .step').forEach(el => {
        const s = parseInt(el.dataset.step);
        el.classList.remove('active', 'completed');
        if (s === currentStep) el.classList.add('active');
        else if (s < currentStep) el.classList.add('completed');
    });

    // Show/hide form steps
    document.querySelectorAll('.form-step').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`step-${currentStep}`);
    if (target) target.classList.add('active');
}

function populateConfirmSummary() {
    const summary = document.getElementById('confirm-summary');
    const fields = [
        ['Make', document.getElementById('v-make').value],
        ['Model', document.getElementById('v-model').value],
        ['Year', document.getElementById('v-year').value],
        ['Color', document.getElementById('v-color').value],
        ['License Plate', document.getElementById('v-plate').value],
        ['VIN', document.getElementById('v-vin').value],
        ['Mileage', document.getElementById('v-mileage').value ? `${document.getElementById('v-mileage').value} km` : ''],
        ['Owner', document.getElementById('o-name').value],
        ['Email', document.getElementById('o-email').value],
        ['Phone', document.getElementById('o-phone').value],
    ];

    summary.innerHTML = fields
        .filter(([, val]) => val)
        .map(([label, val]) => `
            <div class="summary-row">
                <span class="summary-label">${label}</span>
                <span class="summary-value">${val}</span>
            </div>
        `).join('');
}

async function startInspection() {
    const btn = document.getElementById('start-inspection-btn');
    btn.disabled = true;

    const payload = {
        vehicle: {
            make: document.getElementById('v-make').value.trim(),
            model: document.getElementById('v-model').value.trim(),
            year: parseInt(document.getElementById('v-year').value) || null,
            color: document.getElementById('v-color').value.trim() || null,
            license_plate: document.getElementById('v-plate').value.trim() || null,
            vin: document.getElementById('v-vin').value.trim() || null,
            mileage: parseInt(document.getElementById('v-mileage').value) || null,
            owner_name: document.getElementById('o-name').value.trim() || null,
            owner_email: document.getElementById('o-email').value.trim() || null,
            owner_phone: document.getElementById('o-phone').value.trim() || null,
        },
        notes: document.getElementById('i-notes').value.trim() || null,
    };

    try {
        const inspection = await api.post('/api/inspections', payload);
        currentInspectionId = inspection.id;

        // Advance to scanning phase
        await api.patch(`/api/inspections/${inspection.id}/phase`, { phase: 2 });

        showToast('Inspection created! Starting scan...', 'success');

        // Show live scan nav item and navigate
        document.getElementById('nav-detection').style.display = '';
        navigateTo('detection');
        startDetectionStream();

    } catch (err) {
        showToast(`Failed to create inspection: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
    }
}
