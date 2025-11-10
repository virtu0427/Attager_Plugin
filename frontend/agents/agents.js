// Agents Management JavaScript
const API_BASE = window.location.origin;

// Load agents on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAgents();
});

async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE}/api/agents`);
        const agents = await response.json();
        
        displayAgentsList(agents);
    } catch (error) {
        console.error('Failed to load agents:', error);
        showError('Failed to load agents');
    }
}

function displayAgentsList(agents) {
    const container = document.querySelector('.agent-list-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    agents.forEach(agent => {
        const agentItem = document.createElement('div');
        agentItem.className = 'agent-list-item';
        agentItem.style.cursor = 'pointer';
        agentItem.onclick = () => showAgentDetails(agent.agent_id);
        
        agentItem.innerHTML = `
            <div>
                <strong>${agent.name || agent.agent_id}</strong>
                <br>
                <small style="color: var(--text-secondary)">${agent.description || ''}</small>
            </div>
            <span class="status-${agent.status || 'active'}">${agent.status || 'Active'}</span>
        `;
        
        container.appendChild(agentItem);
    });
}

async function showAgentDetails(agentId) {
    try {
        const response = await fetch(`${API_BASE}/api/agents/${agentId}`);
        const agent = await response.json();
        
        // Display modal with agent details and policy configuration
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        `;
        
        const policy = agent.policy || {};
        
        modal.innerHTML = `
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--ring);
                border-radius: 14px;
                padding: 24px;
                max-width: 600px;
                max-height: 80vh;
                overflow-y: auto;
                color: var(--fg);
            ">
                <h2>${agent.name || agent.agent_id}</h2>
                <p style="color: var(--text-secondary)">${agent.description || ''}</p>
                
                <h3 style="margin-top: 20px;">Policy Information</h3>
                <p><strong>Policy ID:</strong> ${policy.policy_id || 'N/A'}</p>
                <p><strong>Enabled:</strong> ${policy.enabled ? 'Yes' : 'No'}</p>
                
                <h4>Prompt Validation Rulesets:</h4>
                <ul>
                    ${(policy.prompt_validation_rulesets || []).map(r => `<li>${r}</li>`).join('')}
                </ul>
                
                <h4>Tool Validation Rulesets:</h4>
                <ul>
                    ${(policy.tool_validation_rulesets || []).map(r => `<li>${r}</li>`).join('')}
                </ul>
                
                <button onclick="this.closest('.modal-overlay').remove()" style="
                    margin-top: 20px;
                    padding: 10px 20px;
                    background: var(--primary);
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    color: #000;
                    font-weight: bold;
                ">Close</button>
            </div>
        `;
        
        document.body.appendChild(modal);
        modal.onclick = (e) => {
            if (e.target === modal) modal.remove();
        };
        
    } catch (error) {
        console.error('Failed to load agent details:', error);
        showError('Failed to load agent details');
    }
}

function showError(message) {
    alert(message);
}

