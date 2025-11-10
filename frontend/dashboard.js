// Dashboard JavaScript
const API_BASE = window.location.origin;

// Load dashboard data on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    loadRecentLogs();
    
    // Refresh every 30 seconds
    setInterval(() => {
        loadDashboardStats();
        loadRecentLogs();
    }, 30000);
});

async function loadDashboardStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const stats = await response.json();
        
        // Update stat cards if they exist
        updateStatCard('total-agents', stats.total_agents || 0);
        updateStatCard('total-rulesets', stats.total_rulesets || 0);
        updateStatCard('total-violations', stats.recent_violations || 0);
        updateStatCard('total-events', stats.total_events || 0);
        
    } catch (error) {
        console.error('Failed to load dashboard stats:', error);
    }
}

function updateStatCard(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

async function loadRecentLogs() {
    try {
        const response = await fetch(`${API_BASE}/api/logs?limit=10`);
        const logs = await response.json();
        
        displayRecentLogs(logs);
    } catch (error) {
        console.error('Failed to load recent logs:', error);
    }
}

function displayRecentLogs(logs) {
    // Find log container on dashboard
    const logContainer = document.querySelector('.widget-recent-logs .log-list');
    if (!logContainer) return;
    
    logContainer.innerHTML = '';
    
    if (logs.length === 0) {
        logContainer.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No recent logs</p>';
        return;
    }
    
    logs.slice(0, 5).forEach(log => {
        const logItem = document.createElement('div');
        logItem.style.cssText = `
            padding: 10px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
            border-left: 3px solid ${log.verdict === 'VIOLATION' || log.verdict === 'BLOCKED' ? '#ff4444' : '#4ef6b2'};
        `;
        
        const timestamp = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : 'N/A';
        
        logItem.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>${log.agent_id || 'Unknown'}</strong>
                    <span style="color: var(--text-secondary); margin-left: 10px;">${log.policy_type || ''}</span>
                </div>
                <span style="color: ${log.verdict === 'VIOLATION' || log.verdict === 'BLOCKED' ? '#ff4444' : '#4ef6b2'}">
                    ${log.verdict || 'N/A'}
                </span>
            </div>
            <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 5px;">
                ${timestamp}
            </div>
        `;
        
        logContainer.appendChild(logItem);
    });
}

