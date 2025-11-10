// Ruleset Management JavaScript
const API_BASE = window.location.origin;

// Load rulesets on page load
document.addEventListener('DOMContentLoaded', () => {
    loadRulesets();
    
    // Setup Add New Rule button
    const addBtn = document.getElementById('openModalBtn');
    if (addBtn) {
        addBtn.onclick = showAddRulesetModal;
    }
});

async function loadRulesets() {
    try {
        const response = await fetch(`${API_BASE}/api/rulesets`);
        const rulesets = await response.json();
        
        displayRulesets(rulesets);
    } catch (error) {
        console.error('Failed to load rulesets:', error);
        showError('Failed to load rulesets');
    }
}

function displayRulesets(rulesets) {
    const tbody = document.querySelector('.ruleset-table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (rulesets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No rulesets found</td></tr>';
        return;
    }
    
    rulesets.forEach(ruleset => {
        const row = document.createElement('tr');
        
        const statusClass = ruleset.enabled ? 'status-active' : 'status-inactive';
        const statusText = ruleset.enabled ? 'Active' : 'Inactive';
        
        row.innerHTML = `
            <td>${ruleset.ruleset_id}</td>
            <td>${ruleset.name || ruleset.ruleset_id}</td>
            <td>${formatType(ruleset.type)}</td>
            <td><span class="${statusClass}">${statusText}</span></td>
            <td>
                <button onclick="showRulesetDetails('${ruleset.ruleset_id}')" 
                    style="padding: 5px 10px; margin-right: 5px; cursor: pointer; background: var(--primary); border: none; border-radius: 4px; color: #000;">View</button>
                <button onclick="editRuleset('${ruleset.ruleset_id}')" 
                    style="padding: 5px 10px; margin-right: 5px; cursor: pointer; background: #66aaff; border: none; border-radius: 4px; color: #000;">Edit</button>
                <button onclick="deleteRuleset('${ruleset.ruleset_id}')"
                    style="padding: 5px 10px; cursor: pointer; background: #ff4444; border: none; border-radius: 4px; color: #fff;">Delete</button>
            </td>
        `;
        
        tbody.appendChild(row);
    });
}

function formatType(type) {
    const typeMap = {
        'prompt_validation': 'Prompt Validation',
        'tool_validation': 'Tool Validation',
        'response_filtering': 'Response Filtering'
    };
    return typeMap[type] || type || 'N/A';
}

async function showRulesetDetails(rulesetId) {
    try {
        const response = await fetch(`${API_BASE}/api/rulesets/${rulesetId}`);
        const ruleset = await response.json();
        
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
        
        let rulesHtml = '';
        if (ruleset.type === 'prompt_validation') {
            rulesHtml = `
                <h4>System Prompt:</h4>
                <pre style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;">${ruleset.system_prompt || ''}</pre>
                <p><strong>Model:</strong> ${ruleset.model || 'gemini-2.0-flash-exp'}</p>
            `;
        } else if (ruleset.type === 'tool_validation') {
            rulesHtml = `
                <h4>Tool Name:</h4>
                <p>${ruleset.tool_name || 'N/A'}</p>
                <h4>Validation Rules:</h4>
                <pre style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 4px; overflow-x: auto;">${JSON.stringify(ruleset.rules, null, 2)}</pre>
            `;
        } else if (ruleset.type === 'response_filtering') {
            rulesHtml = `
                <h4>Blocked Keywords:</h4>
                <pre style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 4px; overflow-x: auto;">${JSON.stringify(ruleset.blocked_keywords || [], null, 2)}</pre>
            `;
        }
        
        modal.innerHTML = `
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--ring);
                border-radius: 14px;
                padding: 24px;
                max-width: 700px;
                max-height: 80vh;
                overflow-y: auto;
                color: var(--fg);
            ">
                <h2>${ruleset.name || ruleset.ruleset_id}</h2>
                <p style="color: var(--text-secondary)">${ruleset.description || ''}</p>
                <p><strong>Type:</strong> ${formatType(ruleset.type)}</p>
                <p><strong>Enabled:</strong> ${ruleset.enabled ? 'Yes' : 'No'}</p>
                
                ${rulesHtml}
                
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
        console.error('Failed to load ruleset details:', error);
        showError('Failed to load ruleset details');
    }
}

function showAddRulesetModal() {
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
    
    modal.innerHTML = `
        <div style="
            background: var(--card-bg);
            border: 1px solid var(--ring);
            border-radius: 14px;
            padding: 24px;
            max-width: 700px;
            max-height: 85vh;
            overflow-y: auto;
            color: var(--fg);
        ">
            <h2>Add New Ruleset</h2>
            <form id="addRulesetForm">
                <div style="margin-bottom: 15px;">
                    <label><strong>Ruleset ID:</strong></label><br>
                    <input type="text" name="ruleset_id" required placeholder="e.g., ruleset_my_custom_rule" 
                        style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">
                </div>
                
                <div style="margin-bottom: 15px;">
                    <label><strong>Name:</strong></label><br>
                    <input type="text" name="name" required placeholder="Human-readable name" 
                        style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">
                </div>
                
                <div style="margin-bottom: 15px;">
                    <label><strong>Type:</strong></label><br>
                    <select name="type" id="rulesetType" required onchange="updateRulesetFields(this.value, 'add')" 
                        style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">
                        <option value="prompt_validation">Prompt Validation</option>
                        <option value="tool_validation">Tool Validation</option>
                        <option value="response_filtering">Response Filtering</option>
                    </select>
                </div>
                
                <div style="margin-bottom: 15px;">
                    <label><strong>Description:</strong></label><br>
                    <textarea name="description" rows="2" placeholder="Describe what this ruleset does" 
                        style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;"></textarea>
                </div>
                
                <div id="dynamicFields"></div>
                
                <div style="margin-bottom: 15px;">
                    <label>
                        <input type="checkbox" name="enabled" checked style="margin-right: 5px;">
                        <strong>Enabled</strong>
                    </label>
                </div>
                
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button type="submit" style="
                        padding: 10px 20px;
                        background: var(--primary);
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        color: #000;
                        font-weight: bold;
                    ">Create Ruleset</button>
                    <button type="button" onclick="this.closest('.modal-overlay').remove()" style="
                        padding: 10px 20px;
                        background: #666;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        color: #fff;
                    ">Cancel</button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Initialize with prompt_validation fields
    updateRulesetFields('prompt_validation', 'add');
    
    const form = modal.querySelector('#addRulesetForm');
    form.onsubmit = async (e) => {
        e.preventDefault();
        await handleRulesetSubmit(e, 'create');
    };
}

async function editRuleset(rulesetId) {
    try {
        const response = await fetch(`${API_BASE}/api/rulesets/${rulesetId}`);
        const ruleset = await response.json();
        
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
        
        const enabledChecked = ruleset.enabled ? 'checked' : '';
        
        modal.innerHTML = `
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--ring);
                border-radius: 14px;
                padding: 24px;
                max-width: 700px;
                max-height: 85vh;
                overflow-y: auto;
                color: var(--fg);
            ">
                <h2>Edit Ruleset: ${ruleset.name}</h2>
                <form id="editRulesetForm" data-ruleset-id="${rulesetId}">
                    <div style="margin-bottom: 15px;">
                        <label><strong>Ruleset ID:</strong></label><br>
                        <input type="text" value="${ruleset.ruleset_id}" disabled 
                            style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(100,100,100,0.3); border: 1px solid var(--ring); color: var(--muted); border-radius: 4px;">
                        <small style="color: var(--text-secondary);">ID cannot be changed</small>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label><strong>Name:</strong></label><br>
                        <input type="text" name="name" value="${ruleset.name || ''}" required 
                            style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label><strong>Type:</strong></label><br>
                        <select name="type" id="editRulesetType" required onchange="updateRulesetFields(this.value, 'edit', ${JSON.stringify(ruleset).replace(/"/g, '&quot;')})" 
                            style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">
                            <option value="prompt_validation" ${ruleset.type === 'prompt_validation' ? 'selected' : ''}>Prompt Validation</option>
                            <option value="tool_validation" ${ruleset.type === 'tool_validation' ? 'selected' : ''}>Tool Validation</option>
                            <option value="response_filtering" ${ruleset.type === 'response_filtering' ? 'selected' : ''}>Response Filtering</option>
                        </select>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label><strong>Description:</strong></label><br>
                        <textarea name="description" rows="2" 
                            style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">${ruleset.description || ''}</textarea>
                    </div>
                    
                    <div id="dynamicFields"></div>
                    
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" name="enabled" ${enabledChecked} style="margin-right: 5px;">
                            <strong>Enabled</strong>
                        </label>
                    </div>
                    
                    <div style="display: flex; gap: 10px; margin-top: 20px;">
                        <button type="submit" style="
                            padding: 10px 20px;
                            background: var(--primary);
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            color: #000;
                            font-weight: bold;
                        ">Update Ruleset</button>
                        <button type="button" onclick="this.closest('.modal-overlay').remove()" style="
                            padding: 10px 20px;
                            background: #666;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            color: #fff;
                        ">Cancel</button>
                    </div>
                </form>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Initialize with current ruleset type and data
        updateRulesetFields(ruleset.type, 'edit', ruleset);
        
        const form = modal.querySelector('#editRulesetForm');
        form.onsubmit = async (e) => {
            e.preventDefault();
            await handleRulesetSubmit(e, 'update', rulesetId);
        };
        
    } catch (error) {
        console.error('Failed to load ruleset for editing:', error);
        showError('Failed to load ruleset for editing');
    }
}

function updateRulesetFields(type, mode, existingData = null) {
    const container = document.getElementById('dynamicFields');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (type === 'prompt_validation') {
        const systemPrompt = existingData?.system_prompt || '';
        const model = existingData?.model || 'gemini-2.0-flash-exp';
        
        container.innerHTML = `
            <div style="margin-bottom: 15px;">
                <label><strong>System Prompt:</strong></label><br>
                <textarea name="system_prompt" rows="10" required placeholder="Enter the system prompt for validation..." 
                    style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px; font-family: monospace; font-size: 13px;">${systemPrompt}</textarea>
                <small style="color: var(--text-secondary);">Use {prompt} placeholder for user input</small>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label><strong>Model:</strong></label><br>
                <select name="model" style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">
                    <option value="gemini-2.0-flash-exp" ${model === 'gemini-2.0-flash-exp' ? 'selected' : ''}>gemini-2.0-flash-exp</option>
                    <option value="gemini-1.5-flash" ${model === 'gemini-1.5-flash' ? 'selected' : ''}>gemini-1.5-flash</option>
                    <option value="gemini-1.5-pro" ${model === 'gemini-1.5-pro' ? 'selected' : ''}>gemini-1.5-pro</option>
                </select>
            </div>
        `;
    } else if (type === 'tool_validation') {
        const toolName = existingData?.tool_name || '';
        const rules = existingData?.rules ? JSON.stringify(existingData.rules, null, 2) : '{\n  "allowed_values": [],\n  "max_length": 100\n}';
        
        container.innerHTML = `
            <div style="margin-bottom: 15px;">
                <label><strong>Tool Name:</strong></label><br>
                <input type="text" name="tool_name" value="${toolName}" required placeholder="e.g., call_remote_agent" 
                    style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px;">
            </div>
            
            <div style="margin-bottom: 15px;">
                <label><strong>Validation Rules (JSON):</strong></label><br>
                <textarea name="rules" rows="10" required placeholder='{"allowed_values": [], "max_length": 100}' 
                    style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px; font-family: monospace; font-size: 13px;">${rules}</textarea>
                <small style="color: var(--text-secondary);">Enter validation rules as JSON</small>
            </div>
        `;
    } else if (type === 'response_filtering') {
        const blockedKeywords = existingData?.blocked_keywords ? JSON.stringify(existingData.blocked_keywords, null, 2) : '["password", "credit_card", "ssn"]';
        
        container.innerHTML = `
            <div style="margin-bottom: 15px;">
                <label><strong>Blocked Keywords (JSON Array):</strong></label><br>
                <textarea name="blocked_keywords" rows="8" required placeholder='["keyword1", "keyword2"]' 
                    style="width: 100%; padding: 8px; margin-top: 5px; background: rgba(255,255,255,0.1); border: 1px solid var(--ring); color: var(--fg); border-radius: 4px; font-family: monospace; font-size: 13px;">${blockedKeywords}</textarea>
                <small style="color: var(--text-secondary);">List of keywords to block in responses</small>
            </div>
        `;
    }
}

async function handleRulesetSubmit(event, action, rulesetId = null) {
    const form = event.target;
    const formData = new FormData(form);
    
    const data = {
        name: formData.get('name'),
        type: formData.get('type'),
        description: formData.get('description') || '',
        enabled: formData.get('enabled') === 'on'
    };
    
    // Add ruleset_id for creation
    if (action === 'create') {
        data.ruleset_id = formData.get('ruleset_id');
    }
    
    // Add type-specific fields
    if (data.type === 'prompt_validation') {
        data.system_prompt = formData.get('system_prompt');
        data.model = formData.get('model');
    } else if (data.type === 'tool_validation') {
        data.tool_name = formData.get('tool_name');
        try {
            data.rules = JSON.parse(formData.get('rules'));
        } catch (e) {
            showError('Invalid JSON in rules field');
            return;
        }
    } else if (data.type === 'response_filtering') {
        try {
            data.blocked_keywords = JSON.parse(formData.get('blocked_keywords'));
        } catch (e) {
            showError('Invalid JSON in blocked_keywords field');
            return;
        }
    }
    
    try {
        let url = `${API_BASE}/api/rulesets`;
        let method = 'POST';
        
        if (action === 'update') {
            url = `${API_BASE}/api/rulesets/${rulesetId}`;
            method = 'PUT';
        }
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            // Close modal
            const modal = form.closest('.modal-overlay');
            if (modal) modal.remove();
            
            // Reload rulesets
            loadRulesets();
            
            const successMsg = action === 'create' ? 'Ruleset created successfully' : 'Ruleset updated successfully';
            showSuccess(successMsg);
        } else {
            const error = await response.json();
            showError(`Failed to ${action} ruleset: ` + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error(`Failed to ${action} ruleset:`, error);
        showError(`Failed to ${action} ruleset`);
    }
}

async function deleteRuleset(rulesetId) {
    if (!confirm(`Are you sure you want to delete ruleset: ${rulesetId}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/rulesets/${rulesetId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadRulesets();
            showSuccess('Ruleset deleted successfully');
        } else {
            const error = await response.json();
            showError('Failed to delete ruleset: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to delete ruleset:', error);
        showError('Failed to delete ruleset');
    }
}

function showError(message) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ff4444;
        color: #fff;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function showSuccess(message) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--kinic, #4ef6b2);
        color: #000;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
