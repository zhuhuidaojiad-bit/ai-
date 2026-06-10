// ── State ────────────────────────────────────────────────────────────
let currentSessionId = null;
let currentEventSource = null;
let referenceUrls = [];  // uploaded reference image URLs
let videoUrl = null;     // uploaded video URL
const agentResults = {};
const agentStreamingContent = {};  // accumulate streaming chunks per agent
const agentIcons = {
    copywriting: '📝',
    cover_image: '🎨',
    data_analysis: '📊',
    orders: '📦',
    video_script: '🎬',
    video_analysis: '📈',
    video_breakdown: '🔍',
    compliance_check: '🛡️',
    video_review: '🔎',
};
const agentNames = {
    copywriting: '文案生成',
    cover_image: '封面图片',
    data_analysis: '数据分析',
    orders: '订单查询',
    video_script: '视频脚本',
    video_analysis: '视频分析',
    video_breakdown: '爆款拆解',
    compliance_check: '合规检测',
    video_review: '视频审阅',
};

// ── DOM Elements ─────────────────────────────────────────────────────
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const progressPanel = document.getElementById('progressPanel');
const agentProgressList = document.getElementById('agentProgressList');
const resultsPanel = document.getElementById('resultsPanel');
const resultTabs = document.getElementById('resultTabs');
const tabContent = document.getElementById('tabContent');
const summaryPanel = document.getElementById('summaryPanel');
const summaryContent = document.getElementById('summaryContent');
const sessionList = document.getElementById('sessionList');
const imageDropZone = document.getElementById('imageDropZone');
const imageFileInput = document.getElementById('imageFileInput');
const referencePreviews = document.getElementById('referencePreviews');
const videoDropZone = document.getElementById('videoDropZone');
const videoFileInput = document.getElementById('videoFileInput');
const videoPreview = document.getElementById('videoPreview');

// ── Send Message ─────────────────────────────────────────────────────
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
});

function quickSend(text) {
    userInput.value = text;
    sendMessage();
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // Capture reference URLs BEFORE reset (reset clears them)
    const refs = [...referenceUrls];

    // Reset main area only (not sidebar, not references)
    resetMainArea();
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner"></span> 执行中...';
    userInput.disabled = true;

    progressPanel.style.display = 'block';

    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_input: text,
                session_id: currentSessionId,
                reference_urls: refs.length > 0 ? refs : undefined,
                video_url: videoUrl || undefined,
            }),
        });
        const data = await resp.json();
        currentSessionId = data.session_id;

        startSSEStream(currentSessionId);
    } catch (err) {
        console.error('Send error:', err);
        resetSendButton();
        alert('发送失败: ' + err.message);
    }
}

function resetMainArea() {
    agentProgressList.innerHTML = '';
    resultTabs.innerHTML = '';
    tabContent.innerHTML = '';
    summaryContent.innerHTML = '';
    summaryPanel.style.display = 'none';
    Object.keys(agentResults).forEach(k => delete agentResults[k]);
    Object.keys(agentStreamingContent).forEach(k => delete agentStreamingContent[k]);
    resultsPanel.style.display = 'none';
    resetAllMiniCards();
    // Note: reference previews persist until user removes them
}

function resetSendButton() {
    sendBtn.disabled = false;
    sendBtn.innerHTML = '<span style="margin-right:2px">▶</span> 发送';
    userInput.disabled = false;
    userInput.focus();
}

// ── Mini Card & Nav Dot Status ───────────────────────────────────────
function updateMiniCardStatus(agent, status) {
    const miniCard = document.querySelector(`.agent-mini-card[data-agent="${agent}"]`);
    if (miniCard) {
        miniCard.classList.remove('running', 'completed', 'error');
        if (status === 'running') miniCard.classList.add('running');
        else if (status === 'completed') miniCard.classList.add('completed');
        else if (status === 'error') miniCard.classList.add('error');
    }
    const navDot = document.getElementById(`navDot-${agent}`);
    if (navDot) {
        navDot.classList.remove('running', 'completed', 'error');
        if (status === 'running') navDot.classList.add('running');
        else if (status === 'completed') navDot.classList.add('completed');
        else if (status === 'error') navDot.classList.add('error');
    }
}

function resetAllMiniCards() {
    document.querySelectorAll('.agent-mini-card').forEach(card => {
        card.classList.remove('running', 'completed', 'error');
    });
    document.querySelectorAll('.nav-dot').forEach(dot => {
        dot.classList.remove('running', 'completed', 'error');
    });
}

// ── SSE Stream ───────────────────────────────────────────────────────
function startSSEStream(sessionId) {
    if (currentEventSource) currentEventSource.close();

    currentEventSource = new EventSource(`/api/chat/${sessionId}/stream`);

    currentEventSource.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleSSEEvent(msg.event, msg.data);
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };

    currentEventSource.onerror = () => {
        console.error('SSE connection error');
        currentEventSource.close();
        resetSendButton();
        refreshSessionList();
    };
}

function handleSSEEvent(eventType, data) {
    switch (eventType) {
        case 'agent_start':
            agentStreamingContent[data.agent] = '';
            addAgentProgress(data.agent);
            updateAgentProgress(data.agent, 'running', 10);
            updateMiniCardStatus(data.agent, 'running');
            resultsPanel.style.display = 'block';
            renderTabs();
            switchTab(data.agent);
            break;
        case 'agent_chunk':
            if (!agentStreamingContent[data.agent]) {
                agentStreamingContent[data.agent] = '';
            }
            agentStreamingContent[data.agent] += data.chunk;
            renderTabs();
            updateLiveTabContent(data.agent);
            updateAgentProgress(data.agent, 'running', Math.min(90, 10 + (agentStreamingContent[data.agent]?.length || 0) / 10));
            break;
        case 'agent_complete':
            agentResults[data.agent] = {
                agent_name: data.agent,
                status: 'completed',
                content: data.result,
            };
            agentStreamingContent[data.agent] = data.result;
            updateAgentProgress(data.agent, 'completed', 100);
            updateMiniCardStatus(data.agent, 'completed');
            renderTabs();
            updateLiveTabContent(data.agent);
            break;
        case 'agent_error':
            agentResults[data.agent] = {
                agent_name: data.agent,
                status: 'failed',
                content: data.error,
            };
            updateAgentProgress(data.agent, 'failed', 100);
            updateMiniCardStatus(data.agent, 'error');
            renderTabs();
            break;
        case 'aggregate_complete':
            summaryPanel.style.display = 'block';
            summaryContent.textContent = data.summary || '所有 Agent 已完成。';
            setTimeout(() => { summaryPanel.style.display = 'none'; }, 6000);
            break;
        case 'done':
            resetSendButton();
            if (currentEventSource) currentEventSource.close();
            refreshSessionList();
            break;
        case 'error':
            summaryPanel.style.display = 'block';
            summaryContent.innerHTML = `<span style="color:var(--error)">❌ 执行出错: ${data.error}</span>`;
            resetSendButton();
            if (currentEventSource) currentEventSource.close();
            break;
    }
}

// ── Agent Progress Cards ─────────────────────────────────────────────
function addAgentProgress(agent) {
    const icon = agentIcons[agent] || '🤖';
    const name = agentNames[agent] || agent;
    const row = document.createElement('div');
    row.className = 'agent-progress-row';
    row.id = `progress-${agent}`;
    row.innerHTML = `
        <div class="agent-header">
            <span class="agent-icon">${icon}</span>
            <span class="agent-name">${name}</span>
            <span class="agent-status pending" id="status-${agent}">等待中 ⏸</span>
        </div>
        <div class="progress-bar-container">
            <div class="progress-bar-fill" id="bar-${agent}"></div>
        </div>
    `;
    agentProgressList.appendChild(row);
}

function updateAgentProgress(agent, status, width) {
    const bar = document.getElementById(`bar-${agent}`);
    const statusEl = document.getElementById(`status-${agent}`);
    const row = document.getElementById(`progress-${agent}`);

    if (bar) bar.style.width = `${width}%`;

    if (row) {
        row.classList.remove('running-card', 'completed-card', 'error-card');
        if (status === 'running') row.classList.add('running-card');
        else if (status === 'completed') row.classList.add('completed-card');
        else if (status === 'failed') row.classList.add('error-card');
    }

    const statusText = { pending: '等待中 ⏸', running: '运行中 ⏳', completed: '完成 ✅', failed: '失败 ❌' };
    if (statusEl) {
        statusEl.textContent = statusText[status] || status;
        statusEl.className = `agent-status ${status}`;
    }
}

// ── Tabs ─────────────────────────────────────────────────────────────
function renderTabs() {
    resultTabs.innerHTML = '';
    const agents = Object.keys(agentResults);
    if (agents.length === 0) return;

    agents.forEach(agent => {
        const btn = document.createElement('button');
        btn.className = 'tab-btn';
        btn.textContent = `${agentIcons[agent] || ''} ${agentNames[agent] || agent}`;
        btn.onclick = () => switchTab(agent);
        resultTabs.appendChild(btn);
    });

    // Activate first tab if nothing active
    const active = resultTabs.querySelector('.tab-btn.active');
    if (!active && resultTabs.firstChild) {
        resultTabs.firstChild.classList.add('active');
        showTabContent(agents[0]);
    }
}

function switchTab(agent) {
    resultTabs.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const buttons = resultTabs.querySelectorAll('.tab-btn');
    const agentKeys = Object.keys(agentResults);
    const idx = agentKeys.indexOf(agent);
    if (idx >= 0 && buttons[idx]) buttons[idx].classList.add('active');

    showTabContent(agent);
}

function showTabContent(agent) {
    const result = agentResults[agent];
    const streaming = agentStreamingContent[agent];
    const content = (result && result.content) || streaming || '';

    if (result && result.status === 'failed') {
        tabContent.innerHTML = `<span style="color:var(--error)">❌ 执行失败: ${escapeHtml(result.content)}</span>`;
    } else if (agent === 'cover_image') {
        // Extract image URL from content
        const urlMatch = content.match(/https?:\/\/[^\s"'<>]+\.(png|jpg|jpeg|gif|webp)(\?[^\s"'<>]*)?/i);
        if (urlMatch) {
            const imgUrl = urlMatch[0];
            const textContent = content.replace(imgUrl, '').trim();
            tabContent.innerHTML = `
                <div class="image-container">
                    <img src="${imgUrl}" alt="封面图片" class="fade-in-image" onload="this.classList.add('loaded')" />
                    <div class="image-placeholder">🖼️ 图片加载中...</div>
                </div>
                <div class="image-text">${formatContent(textContent)}</div>
            `;
        } else {
            tabContent.innerHTML = formatContent(content);
        }
    } else {
        tabContent.innerHTML = formatContent(content);
    }
}

function formatContent(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
}

// Update tab content while streaming
function updateLiveTabContent(agent) {
    const activeTab = resultTabs.querySelector('.tab-btn.active');
    if (activeTab && activeTab.textContent.includes(agentNames[agent] || agent)) {
        showTabContent(agent);
        tabContent.scrollTop = tabContent.scrollHeight;
    }
}

// ── Session History ──────────────────────────────────────────────────
async function refreshSessionList() {
    try {
        const resp = await fetch('/api/sessions');
        const data = await resp.json();
        renderSessionList(data.sessions || []);
    } catch (err) {
        console.error('Load sessions error:', err);
    }
}

function renderSessionList(sessions) {
    if (sessions.length === 0) {
        sessionList.innerHTML = '<p class="empty-hint">暂无历史会话</p>';
        return;
    }

    sessionList.innerHTML = sessions.map(s => {
        const time = s.created_at ? new Date(s.created_at).toLocaleString('zh-CN') : '';
        const text = s.user_input.length > 25 ? s.user_input.slice(0, 25) + '...' : s.user_input;
        const active = s.id === currentSessionId ? ' active' : '';
        return `<div class="session-item${active}" onclick="loadSession('${s.id}')">
            ${escapeHtml(text)}
            <span class="time">${time}</span>
        </div>`;
    }).join('');
}

async function loadSession(sessionId) {
    if (sessionId === currentSessionId) return; // Don't reload same session

    try {
        const resp = await fetch(`/api/sessions/${sessionId}`);
        const session = await resp.json();

        // Update current session ID first
        currentSessionId = sessionId;

        // Reset main area (not sidebar)
        resetMainArea();

        // Populate results
        const results = session.results || {};
        Object.assign(agentResults, results);

        if (Object.keys(results).length > 0) {
            resultsPanel.style.display = 'block';
            progressPanel.style.display = 'block';

            Object.entries(results).forEach(([agent, result]) => {
                addAgentProgress(agent);
                const status = result.status || 'completed';
                updateAgentProgress(agent, status, 100);
                updateMiniCardStatus(agent, status);
            });

            renderTabs();
        }

        // Update sidebar active state without full re-render
        updateSessionActiveState();

    } catch (err) {
        console.error('Load session error:', err);
    }
}

// Update only the active state in session list (no full re-render)
function updateSessionActiveState() {
    sessionList.querySelectorAll('.session-item').forEach(item => {
        const onclick = item.getAttribute('onclick') || '';
        if (onclick.includes(`'${currentSessionId}'`)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// ── Sidebar Mobile ──────────────────────────────────────────────────
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
}

function scrollToInput() {
    userInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    userInput.focus();
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
}

// ── Image Upload ────────────────────────────────────────────────────
imageDropZone.addEventListener('dragover', (e) => { e.preventDefault(); imageDropZone.classList.add('drag-over'); });
imageDropZone.addEventListener('dragleave', () => { imageDropZone.classList.remove('drag-over'); });
imageDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    imageDropZone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    if (files.length > 0) uploadImageFiles(files);
});
imageDropZone.addEventListener('click', () => imageFileInput.click());
imageFileInput.addEventListener('change', () => {
    const files = Array.from(imageFileInput.files).filter(f => f.type.startsWith('image/'));
    if (files.length > 0) uploadImageFiles(files);
    imageFileInput.value = '';
});

async function uploadImageFiles(files) {
    for (const file of files) {
        const preview = document.createElement('div');
        preview.className = 'upload-preview-item uploading';
        preview.innerHTML = '<span class="spinner" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%)"></span>';
        referencePreviews.appendChild(preview);
        try {
            const fd = new FormData(); fd.append('file', file);
            const resp = await fetch('/api/upload/reference', { method: 'POST', body: fd });
            if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
            const data = await resp.json();
            referenceUrls.push(data.url);
            preview.classList.remove('uploading');
            preview.innerHTML = `<img src="${data.url}" alt="参考图" /><button class="preview-remove" onclick="removeImageRef('${data.url}', this.parentElement)">✕</button>`;
        } catch (err) {
            preview.remove();
            alert('图片上传失败: ' + err.message);
        }
    }
}

function removeImageRef(url, el) {
    referenceUrls = referenceUrls.filter(u => u !== url);
    el.remove();
}

// ── Video Upload ─────────────────────────────────────────────────────
videoDropZone.addEventListener('dragover', (e) => { e.preventDefault(); videoDropZone.classList.add('drag-over'); });
videoDropZone.addEventListener('dragleave', () => { videoDropZone.classList.remove('drag-over'); });
videoDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    videoDropZone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('video/'));
    if (files.length > 0) uploadVideoFile(files[0]);
});
videoDropZone.addEventListener('click', () => videoFileInput.click());
videoFileInput.addEventListener('change', () => {
    const files = Array.from(videoFileInput.files).filter(f => f.type.startsWith('video/'));
    if (files.length > 0) uploadVideoFile(files[0]);
    videoFileInput.value = '';
});

async function uploadVideoFile(file) {
    videoPreview.innerHTML = '<span class="video-preview-name uploading">⏳ 上传中...</span>';
    try {
        const fd = new FormData(); fd.append('file', file);
        const resp = await fetch('/api/upload/reference', { method: 'POST', body: fd });
        if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
        const data = await resp.json();
        videoUrl = data.url;
        const name = file.name.length > 20 ? file.name.slice(0, 18) + '...' : file.name;
        videoPreview.innerHTML = `<span class="video-preview-name">📹 ${name}</span><button class="preview-remove" onclick="removeVideo()" style="position:static;margin-left:4px;">✕</button>`;
    } catch (err) {
        videoPreview.innerHTML = '';
        alert('视频上传失败: ' + err.message);
    }
}

function removeVideo() {
    videoUrl = null;
    videoPreview.innerHTML = '';
}

// ── Init ─────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
    refreshSessionList();
    userInput.focus();
});
