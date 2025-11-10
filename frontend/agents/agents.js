const API_BASE = window.location.origin;

const state = {
  agents: [],
  rulesets: {
    prompt_validation: [],
    tool_validation: [],
    response_filtering: [],
  },
  selectedAgentId: null,
  agentCache: new Map(),
};

window.addEventListener('DOMContentLoaded', () => {
  initialise();
});

async function initialise() {
  await Promise.all([loadAgents(), loadRulesets()]);
  bindSearch();
}

function bindSearch() {
  const searchInput = document.getElementById('agent-search');
  if (!searchInput) return;

  searchInput.addEventListener('input', (event) => {
    renderAgentList(event.target.value.trim().toLowerCase());
  });
}

async function loadAgents() {
  try {
    const response = await fetch(`${API_BASE}/api/agents`);
    if (!response.ok) throw new Error('Failed to load agents');
    const agents = await response.json();

    state.agents = Array.isArray(agents) ? agents : [];
    renderAgentList();
  } catch (error) {
    console.error('Failed to load agents', error);
    const list = document.getElementById('agent-list');
    if (list) {
      list.innerHTML = '<li class="empty-state">Unable to load agents.</li>';
    }
  }
}

async function loadRulesets() {
  try {
    const response = await fetch(`${API_BASE}/api/rulesets`);
    if (!response.ok) throw new Error('Failed to load rulesets');
    const rulesets = await response.json();

    const grouped = {
      prompt_validation: [],
      tool_validation: [],
      response_filtering: [],
    };

    (rulesets || []).forEach((ruleset) => {
      if (grouped[ruleset.type]) {
        grouped[ruleset.type].push(ruleset);
      }
    });

    Object.keys(grouped).forEach((key) => {
      grouped[key].sort((a, b) => (a.name || a.ruleset_id).localeCompare(b.name || b.ruleset_id));
    });

    state.rulesets = grouped;
  } catch (error) {
    console.error('Failed to load rulesets', error);
  }
}

function renderAgentList(filter = '') {
  const list = document.getElementById('agent-list');
  const template = document.getElementById('agent-item-template');
  if (!list || !template) return;

  list.innerHTML = '';

  const filteredAgents = state.agents.filter((agent) => {
    if (!filter) return true;
    return (
      agent.agent_id?.toLowerCase().includes(filter) ||
      agent.name?.toLowerCase().includes(filter) ||
      agent.description?.toLowerCase().includes(filter)
    );
  });

  if (filteredAgents.length === 0) {
    list.innerHTML = '<li class="empty-state">No agents match this search.</li>';
    return;
  }

  filteredAgents
    .sort((a, b) => (a.name || a.agent_id).localeCompare(b.name || b.agent_id))
    .forEach((agent) => {
      const clone = template.content.cloneNode(true);
      const element = clone.querySelector('.agent-item');
      const name = clone.querySelector('.agent-name');
      const description = clone.querySelector('.agent-description');
      const statusChip = clone.querySelector('.status-chip');

      if (name) {
        name.textContent = agent.name || agent.agent_id;
      }
      if (description) {
        description.textContent = agent.description || '';
      }
      if (statusChip) {
        statusChip.classList.add(getStatusClass(agent.status));
        statusChip.textContent = (agent.status || 'unknown').toUpperCase();
      }

      element.dataset.agentId = agent.agent_id;
      element.addEventListener('click', () => selectAgent(agent.agent_id));

      if (agent.agent_id === state.selectedAgentId) {
        element.classList.add('active');
      }

      list.appendChild(clone);
    });
}

function getStatusClass(status = '') {
  const normalised = status.toLowerCase();
  if (normalised === 'active') return 'status-active';
  if (normalised === 'inactive') return 'status-inactive';
  return 'status-warning';
}

async function selectAgent(agentId) {
  state.selectedAgentId = agentId;
  highlightSelectedAgent();

  const details = await fetchAgentDetails(agentId);
  if (details) {
    renderAgentDetails(details);
  }
}

function highlightSelectedAgent() {
  document.querySelectorAll('.agent-item').forEach((item) => {
    if (item.dataset.agentId === state.selectedAgentId) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

async function fetchAgentDetails(agentId) {
  if (state.agentCache.has(agentId)) {
    return state.agentCache.get(agentId);
  }

  try {
    const response = await fetch(`${API_BASE}/api/agents/${agentId}`);
    if (!response.ok) throw new Error('Failed to fetch agent');
    const agent = await response.json();

    state.agentCache.set(agentId, agent);
    return agent;
  } catch (error) {
    console.error('Failed to fetch agent details', error);
    const container = document.getElementById('agent-details');
    if (container) {
      container.innerHTML = '<div class="agent-error">Unable to load agent details.</div>';
    }
    return null;
  }
}

function renderAgentDetails(agent) {
  const container = document.getElementById('agent-details');
  const template = document.getElementById('agent-details-template');
  if (!container || !template) return;

  container.innerHTML = '';
  const node = template.content.cloneNode(true);

  const title = node.querySelector('.agent-title');
  const subtitle = node.querySelector('.agent-subtitle');
  const statusChip = node.querySelector('.overview-meta .status-chip');
  const created = node.querySelector('[data-role="created"]');
  const pluginList = node.querySelector('.plugin-list');
  const policyForm = node.querySelector('#policy-editor');
  const enabledCheckbox = node.querySelector('#policy-enabled');
  const statusMessage = node.querySelector('#policy-status');

  if (title) {
    title.textContent = agent.name || agent.agent_id;
  }
  if (subtitle) {
    subtitle.textContent = agent.description || '';
  }
  if (statusChip) {
    statusChip.classList.add(getStatusClass(agent.status));
    statusChip.textContent = (agent.status || 'unknown').toUpperCase();
  }
  if (created) {
    created.textContent = agent.created_at
      ? `Created ${new Date(agent.created_at).toLocaleString()}`
      : 'Creation time unknown';
  }
  if (pluginList) {
    renderPluginList(pluginList, agent.plugins);
  }

  const policy = agent.policy || {};
  if (enabledCheckbox) {
    enabledCheckbox.checked = policy.enabled !== false;
  }

  populatePolicyColumns(node, policy);

  if (policyForm) {
    policyForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      await savePolicy(agent.agent_id, policyForm, statusMessage);
    });
  }

  container.appendChild(node);
}

function renderPluginList(listElement, plugins = []) {
  listElement.innerHTML = '';
  if (!plugins || plugins.length === 0) {
    listElement.innerHTML = '<li class="empty-state">No plugins registered.</li>';
    return;
  }

  plugins
    .map((plugin) => (typeof plugin === 'string' ? { name: plugin } : plugin))
    .forEach((plugin) => {
      const item = document.createElement('li');
      item.className = 'plugin-item';
      item.innerHTML = `
        <div>
          <strong>${plugin.name || 'Plugin'}</strong>
          ${plugin.type ? `<span class="pill">${plugin.type}</span>` : ''}
        </div>
        <span class="status-chip ${getStatusClass(plugin.status || 'active')}">
          ${(plugin.status || 'active').toUpperCase()}
        </span>
      `;
      listElement.appendChild(item);
    });
}

function populatePolicyColumns(root, policy) {
  const columns = root.querySelectorAll('.policy-column');

  columns.forEach((column) => {
    const type = column.dataset.policyType;
    const rulesetContainer = column.querySelector('.ruleset-list');
    if (!type || !rulesetContainer) return;

    rulesetContainer.innerHTML = '';
    const available = state.rulesets[type] || [];
    const assigned = new Set(policy[`${type}_rulesets`] || []);

    if (available.length === 0) {
      rulesetContainer.innerHTML = '<p class="empty-state">No rulesets available.</p>';
      return;
    }

    available.forEach((ruleset) => {
      const id = `${type}-${ruleset.ruleset_id}`;
      const wrapper = document.createElement('label');
      wrapper.className = 'ruleset-item';
      wrapper.innerHTML = `
        <input type="checkbox" name="${type}" value="${ruleset.ruleset_id}" ${
          assigned.has(ruleset.ruleset_id) ? 'checked' : ''
        } />
        <div class="ruleset-body">
          <span class="ruleset-name">${ruleset.name || ruleset.ruleset_id}</span>
          <p class="ruleset-description">${ruleset.description || 'No description provided.'}</p>
        </div>
      `;
      rulesetContainer.appendChild(wrapper);
    });
  });
}

async function savePolicy(agentId, form, statusElement) {
  const submitButton = form.querySelector('button[type="submit"]');
  const enabledCheckbox = form.querySelector('#policy-enabled');

  const payload = {
    prompt_validation_rulesets: getSelectedValues(form, 'prompt_validation'),
    tool_validation_rulesets: getSelectedValues(form, 'tool_validation'),
    response_filtering_rulesets: getSelectedValues(form, 'response_filtering'),
    enabled: enabledCheckbox ? enabledCheckbox.checked : true,
  };

  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = 'Saving…';
  }
  if (statusElement) {
    statusElement.textContent = 'Saving updates…';
  }

  try {
    const response = await fetch(`${API_BASE}/api/agents/${agentId}/policy`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error('Failed to update policy');

    // Refresh cached agent
    state.agentCache.delete(agentId);
    const updated = await fetchAgentDetails(agentId);
    if (updated) {
      renderAgentDetails(updated);
    }

    if (statusElement) {
      statusElement.textContent = 'Policy assignments saved successfully.';
      statusElement.classList.remove('error');
    }
  } catch (error) {
    console.error('Failed to save policy', error);
    if (statusElement) {
      statusElement.textContent = 'Failed to save policy assignments.';
      statusElement.classList.add('error');
    }
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = 'Save assignments';
    }
  }
}

function getSelectedValues(form, type) {
  return Array.from(form.querySelectorAll(`input[name="${type}"]:checked`)).map((input) => input.value);
}
