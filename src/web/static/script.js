let messages = [];
let isLoading = false;

const welcomeScreen = document.getElementById('welcomeScreen');
const messagesArea = document.getElementById('messagesArea');
const messagesContainer = document.getElementById('messagesContainer');
const loadingIndicator = document.getElementById('loadingIndicator');
const clearBtn = document.getElementById('clearBtn');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const modelSelect = document.getElementById('modelSelect');
const sendButton = document.getElementById('sendButton');
const sendIcon = document.getElementById('sendIcon');
const loadingSpinner = document.getElementById('loadingSpinner');
const inputArea = document.querySelector('.input-area');
const tabs = document.querySelectorAll('.tab-btn');
const panels = document.querySelectorAll('.panel');
const chips = document.querySelectorAll('.chip');
let fleetMap = null;
let fleetMarkers = [];

document.addEventListener('DOMContentLoaded', function () {
    modelSelect.value = 'demo';
    setupEventListeners();
    selectTab('overviewTab');
    updateSendButton();
    loadDashboard();
});

function setupEventListeners() {
    chatForm.addEventListener('submit', handleSubmit);
    clearBtn.addEventListener('click', clearChat);
    messageInput.addEventListener('input', handleInputChange);
    messageInput.addEventListener('keydown', handleKeyDown);
    tabs.forEach(btn => btn.addEventListener('click', () => selectTab(btn.dataset.tab)));
    chips.forEach(btn => btn.addEventListener('click', () => {
        selectTab('chatTab');
        messageInput.value = btn.dataset.prompt || '';
        messageInput.focus();
        updateSendButton();
    }));
}

function selectTab(tabId) {
    tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
    panels.forEach(p => p.classList.toggle('active', p.id === tabId));
    if (tabId === 'mapTab') {
        setTimeout(() => {
            if (fleetMap) fleetMap.invalidateSize();
        }, 20);
    }
    if (inputArea) {
        inputArea.style.display = tabId === 'chatTab' ? '' : 'none';
    }
}

function handleSubmit(e) {
    e.preventDefault();
    const content = messageInput.value.trim();
    const model = modelSelect.value;
    if (!content || isLoading) return;
    sendMessage(content, model);
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
    }
}

function handleInputChange() {
    autoResizeTextarea();
    updateSendButton();
}

function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    const newHeight = Math.min(messageInput.scrollHeight, 128);
    messageInput.style.height = newHeight + 'px';
}

function updateSendButton() {
    const hasContent = messageInput.value.trim().length > 0;
    sendButton.disabled = !hasContent || isLoading;
}

async function sendMessage(content, model) {
    selectTab('chatTab');
    const userMessage = {
        id: Date.now().toString(),
        content: content,
        type: 'user',
        timestamp: new Date()
    };
    messages.push(userMessage);
    displayMessage(userMessage);

    messageInput.value = '';
    messageInput.style.height = 'auto';
    hideWelcomeScreen();
    showClearButton();
    setLoadingState(true);

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: content, model: model })
        });

        const data = await response.json();

        let aiMessage;
        if (data.error && !data.response) {
            aiMessage = {
                id: (Date.now() + 1).toString(),
                content: `Error: ${data.error}`,
                type: 'ai',
                model: data.mode || model,
                timestamp: new Date()
            };
        } else {
            aiMessage = {
                id: (Date.now() + 1).toString(),
                content: data.response,
                type: 'ai',
                model: data.mode || model,
                duration: data.duration,
                timestamp: new Date()
            };
        }

        messages.push(aiMessage);
        displayMessage(aiMessage);
    } catch (error) {
        messages.push({
            id: (Date.now() + 1).toString(),
            content: `Error: ${error.message}`,
            type: 'ai',
            model: model,
            timestamp: new Date()
        });
        displayMessage(messages[messages.length - 1]);
    } finally {
        setLoadingState(false);
    }
}

function displayMessage(message) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${message.type}`;

    const time = message.timestamp.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    const avatarIcon =
        message.type === 'user'
            ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
            : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/></svg>';

    const modelBadge = message.model
        ? `<span class="message-model">${message.model}</span>`
        : '';

    const duration =
        message.duration !== undefined
            ? `<span>${message.duration.toFixed(2)}s</span>`
            : '';

    const safeText = String(message.content)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br/>');

    messageEl.innerHTML = `
        <div class="message-wrapper">
            <div class="message-header">
                <div class="message-avatar">${avatarIcon}</div>
                <div class="message-info">
                    <span class="message-sender">${message.type === 'user' ? 'You' : 'Assistant'}</span>
                    ${modelBadge}
                </div>
            </div>
            <div class="message-bubble">
                <div class="message-text">${safeText}</div>
            </div>
            <div class="message-footer">
                <span>${time}</span>
                ${duration}
            </div>
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

function setLoadingState(loading) {
    isLoading = loading;
    updateSendButton();
    messageInput.disabled = loading;
    if (loading) {
        loadingIndicator.style.display = 'block';
        sendIcon.style.display = 'none';
        loadingSpinner.style.display = 'block';
    } else {
        loadingIndicator.style.display = 'none';
        sendIcon.style.display = 'block';
        loadingSpinner.style.display = 'none';
    }
    if (loading) scrollToBottom();
}

function hideWelcomeScreen() {
    welcomeScreen.style.display = 'none';
}

function showClearButton() {
    clearBtn.style.display = 'flex';
}

function hideClearButton() {
    clearBtn.style.display = 'none';
}

function clearChat() {
    messages = [];
    messagesContainer.innerHTML = '';
    welcomeScreen.style.display = 'flex';
    hideClearButton();
    setLoadingState(false);
    updateSendButton();
}

function scrollToBottom() {
    if (!messagesArea) return;
    messagesArea.scrollTo({
        top: messagesArea.scrollHeight,
        behavior: 'smooth'
    });
}

async function loadDashboard() {
    try {
        const [overview, vehicles, mapPoints, approvals, audit] = await Promise.all([
            fetch('/api/fleet_overview').then(r => r.json()),
            fetch('/api/vehicles').then(r => r.json()),
            fetch('/api/map_points').then(r => r.json()),
            fetch('/api/approvals').then(r => r.json()),
            fetch('/api/audit').then(r => r.json()),
        ]);
        renderOverview(overview);
        renderVehicles(vehicles.rows || []);
        renderApprovals(approvals.rows || []);
        renderAudit(audit.rows || []);
        renderMap(mapPoints.rows || []);
    } catch (e) {
        console.error('dashboard load failed', e);
    }
}

function renderOverview(o) {
    document.getElementById('kpiVehicles').textContent = o.vehicles_in_view ?? '-';
    document.getElementById('kpiHighRisk').textContent = o.high_risk_vehicles ?? '-';
    document.getElementById('kpiWorkOrders').textContent = o.open_work_orders ?? '-';
    document.getElementById('kpiApprovals').textContent = o.pending_approvals ?? '-';
}

function renderVehicles(rows) {
    const tbody = document.querySelector('#vehiclesTable tbody');
    if (!tbody) return;
    tbody.innerHTML = rows.map(r => `
        <tr>
            <td>${escapeHtml(r.vehicle_id)}</td>
            <td>${Number(r.maintenance_need_probability || 0).toFixed(3)}</td>
            <td>${escapeHtml(r.severity_label || '')}</td>
            <td>${escapeHtml(String(r.deliveries_at_risk_72h ?? 0))}</td>
            <td>${escapeHtml(r.last_event_date || '')}</td>
        </tr>
    `).join('');
}

function renderApprovals(rows) {
    const tbody = document.querySelector('#approvalsTable tbody');
    if (!tbody) return;
    tbody.innerHTML = rows.map(r => `
        <tr>
            <td>${escapeHtml(r.approval_id || '')}</td>
            <td>${escapeHtml(r.action_type || '')}</td>
            <td>${escapeHtml(r.status || '')}</td>
            <td>${escapeHtml(String(r.estimated_cost ?? ''))}</td>
            <td>${escapeHtml(r.created_at || '')}</td>
        </tr>
    `).join('');
}

function renderAudit(rows) {
    const box = document.getElementById('auditLines');
    if (!box) return;
    box.innerHTML = rows.map(r => `<div>${escapeHtml(r.line || '')}</div>`).join('');
}

function renderMap(rows) {
    const mapEl = document.getElementById('fleetMap');
    if (!mapEl || typeof L === 'undefined') return;
    if (!fleetMap) {
        fleetMap = L.map('fleetMap').setView([39.5, -98.35], 4);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap'
        }).addTo(fleetMap);
    }
    fleetMarkers.forEach(m => fleetMap.removeLayer(m));
    fleetMarkers = [];
    rows.forEach(r => {
        const color = r.severity === 'high' ? '#dc2626' : r.severity === 'medium' ? '#d97706' : '#16a34a';
        const marker = L.circleMarker([r.lat, r.lon], { radius: 6, color, fillColor: color, fillOpacity: 0.7 })
            .addTo(fleetMap)
            .bindPopup(`<strong>Vehicle ${escapeHtml(r.vehicle_id)}</strong><br/>Severity: ${escapeHtml(r.severity)}<br/>Need: ${r.maintenance_need_probability}`);
        fleetMarkers.push(marker);
    });
}

function escapeHtml(v) {
    return String(v || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
