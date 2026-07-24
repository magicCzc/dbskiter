/* DBSKiter Web UI - 共享 JS 工具 */

const API_BASE = '/api';

async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        headers: { 'Accept': 'application/json' },
        ...options,
    };

    try {
        const response = await fetch(url, config);
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || `HTTP ${response.status}`);
        }
        return await response.json();
    } catch (err) {
        if (err.message.includes('Failed to fetch')) {
            throw new Error('无法连接到服务器，请确认 dbskiter Web 服务已启动');
        }
        throw err;
    }
}

function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) {
        size /= 1024;
        i++;
    }
    return `${size.toFixed(1)} ${units[i]}`;
}

function formatDuration(ms) {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}min`;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showError(message) {
    const el = document.getElementById('error');
    if (!el) return;
    el.textContent = message;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 8000);
}

function showLoading(show = true) {
    const el = document.getElementById('loading');
    if (el) el.style.display = show ? 'block' : 'none';
}

function setStatusBadge(text) {
    const el = document.getElementById('status-text');
    if (el) el.textContent = text;
    const cls = document.getElementById('status-class');
    if (cls) cls.className = text.includes('HEALTHY') || text === 'ok' ? 'status status-healthy'
        : text.includes('WARNING') ? 'status status-warning'
        : 'status status-critical';
}