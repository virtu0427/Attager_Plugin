const API_BASE = window.location.origin;

let rulesets = [];

window.addEventListener('DOMContentLoaded', () => {
  loadRulesets();
  bindControls();
});

function bindControls() {
  const createButton = document.getElementById('open-create-ruleset');
  if (createButton) {
    createButton.addEventListener('click', () => openFormModal());
  }

  const modal = document.getElementById('ruleset-modal');
  const closeButton = document.getElementById('close-ruleset-modal');
  if (modal) {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeModal();
      }
    });
  }
  if (closeButton) {
    closeButton.addEventListener('click', closeModal);
  }
}

async function loadRulesets() {
  try {
    const response = await fetch(`${API_BASE}/api/rulesets`);
    if (!response.ok) throw new Error('Failed to load rulesets');
    rulesets = await response.json();
    renderRulesetTable();
  } catch (error) {
    console.error('Failed to load rulesets', error);
    const tbody = document.getElementById('ruleset-table-body');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Unable to load rulesets.</td></tr>';
    }
  }
}

function renderRulesetTable() {
  const tbody = document.getElementById('ruleset-table-body');
  const template = document.getElementById('ruleset-row-template');
  if (!tbody || !template) return;

  tbody.innerHTML = '';

  if (!rulesets || rulesets.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No rulesets defined yet.</td></tr>';
    return;
  }

  rulesets
    .slice()
    .sort((a, b) => (a.name || a.ruleset_id).localeCompare(b.name || b.ruleset_id))
    .forEach((ruleset) => {
      const clone = template.content.cloneNode(true);
      clone.querySelector('.ruleset-id').textContent = ruleset.ruleset_id;
      clone.querySelector('.ruleset-name').textContent = ruleset.name || ruleset.ruleset_id;
      clone.querySelector('.ruleset-type').textContent = formatType(ruleset.type);

      const statusCell = clone.querySelector('.ruleset-status');
      if (statusCell) {
        const chip = document.createElement('span');
        chip.className = `status-chip ${ruleset.enabled ? 'status-active' : 'status-inactive'}`;
        chip.textContent = ruleset.enabled ? 'ACTIVE' : 'INACTIVE';
        statusCell.appendChild(chip);
      }

      clone.querySelector('.ruleset-updated').textContent = formatDate(ruleset.updated_at || ruleset.created_at);

      const actionCell = clone.querySelector('.ruleset-actions');
      if (actionCell) {
        actionCell.querySelector('[data-action="view"]').addEventListener('click', () => openDetailModal(ruleset));
        actionCell.querySelector('[data-action="edit"]').addEventListener('click', () => openFormModal(ruleset));
        actionCell.querySelector('[data-action="delete"]').addEventListener('click', () => confirmDelete(ruleset));
      }

      tbody.appendChild(clone);
    });
}

function formatType(type) {
  const map = {
    prompt_validation: 'Prompt validation',
    tool_validation: 'Tool validation',
    response_filtering: 'Response filtering',
  };
  return map[type] || type || 'Unknown';
}

function formatDate(dateString) {
  if (!dateString) return '—';
  return new Date(dateString).toLocaleString();
}

function openDetailModal(ruleset) {
  const modal = document.getElementById('ruleset-modal');
  const title = document.getElementById('ruleset-modal-title');
  const body = document.getElementById('ruleset-modal-body');
  const template = document.getElementById('ruleset-detail-template');
  if (!modal || !title || !body || !template) return;

  body.innerHTML = '';
  title.textContent = ruleset.name || ruleset.ruleset_id;

  const node = template.content.cloneNode(true);
  const wrapper = node.querySelector('.ruleset-detail');
  wrapper.querySelector('[data-field="ruleset_id"]').textContent = ruleset.ruleset_id;
  wrapper.querySelector('[data-field="type"]').textContent = formatType(ruleset.type);
  wrapper.querySelector('[data-field="status"]').textContent = ruleset.enabled ? 'Enabled' : 'Disabled';
  wrapper.querySelector('[data-field="updated"]').textContent = formatDate(ruleset.updated_at || ruleset.created_at);
  wrapper.querySelector('[data-field="description"]').textContent = ruleset.description || 'No description provided.';

  const configuration = { ...ruleset };
  wrapper.querySelector('[data-field="json"]').textContent = JSON.stringify(configuration, null, 2);

  body.appendChild(wrapper);
  openModal();
}

function openFormModal(ruleset) {
  const modal = document.getElementById('ruleset-modal');
  const title = document.getElementById('ruleset-modal-title');
  const body = document.getElementById('ruleset-modal-body');
  const template = document.getElementById('ruleset-form-template');
  if (!modal || !title || !body || !template) return;

  body.innerHTML = '';
  const node = template.content.cloneNode(true);
  const form = node.querySelector('#ruleset-form');
  const typeSelect = node.querySelector('#ruleset-type');
  const statusMessage = node.querySelector('#ruleset-form-status');

  if (ruleset) {
    title.textContent = 'Edit ruleset';
    populateForm(form, ruleset);
    form.dataset.mode = 'edit';
  } else {
    title.textContent = 'Create ruleset';
    form.dataset.mode = 'create';
  }

  if (typeSelect) {
    typeSelect.addEventListener('change', () => toggleTypeFields(typeSelect.value, form));
    toggleTypeFields(typeSelect.value, form);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    await submitForm(form, statusMessage, ruleset);
  });

  body.appendChild(node);
  openModal();
}

function populateForm(form, ruleset) {
  form.querySelector('#ruleset-id').value = ruleset.ruleset_id;
  form.querySelector('#ruleset-id').disabled = true;
  form.querySelector('#ruleset-name').value = ruleset.name || '';
  form.querySelector('#ruleset-type').value = ruleset.type || 'prompt_validation';
  form.querySelector('#ruleset-enabled').checked = ruleset.enabled !== false;
  form.querySelector('#ruleset-description').value = ruleset.description || '';
  form.querySelector('#ruleset-system-prompt').value = ruleset.system_prompt || '';
  form.querySelector('#ruleset-model').value = ruleset.model || '';
  form.querySelector('#ruleset-tool-name').value = ruleset.tool_name || '';
  form.querySelector('#ruleset-rules').value = ruleset.rules ? JSON.stringify(ruleset.rules, null, 2) : '';
  form.querySelector('#ruleset-blocked').value = ruleset.blocked_keywords
    ? JSON.stringify(ruleset.blocked_keywords, null, 2)
    : '';
}

function toggleTypeFields(type, form) {
  const fields = form.querySelectorAll('[data-field]');
  fields.forEach((group) => {
    const fieldType = group.dataset.field;
    group.classList.toggle('hidden', fieldType && fieldType !== type);
  });
}

async function submitForm(form, statusElement, existing) {
  const submitButton = form.querySelector('button[type="submit"]');
  const formData = new FormData(form);

  const payload = {
    ruleset_id: formData.get('ruleset_id') || existing?.ruleset_id,
    name: formData.get('name'),
    type: formData.get('type'),
    description: formData.get('description'),
    enabled: formData.get('enabled') === 'on',
  };

  if (payload.type === 'prompt_validation') {
    payload.system_prompt = formData.get('system_prompt');
    payload.model = formData.get('model');
  } else if (payload.type === 'tool_validation') {
    payload.tool_name = formData.get('tool_name');
    payload.rules = safeJsonParse(formData.get('rules')) || {};
  } else if (payload.type === 'response_filtering') {
    payload.blocked_keywords = safeJsonParse(formData.get('blocked_keywords')) || [];
  }

  if (statusElement) {
    statusElement.textContent = 'Saving…';
    statusElement.classList.remove('error');
  }
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = 'Saving…';
  }

  try {
    const method = existing ? 'PUT' : 'POST';
    const url = existing
      ? `${API_BASE}/api/rulesets/${encodeURIComponent(existing.ruleset_id)}`
      : `${API_BASE}/api/rulesets`;

    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error('Failed to save ruleset');

    await loadRulesets();
    closeModal();
  } catch (error) {
    console.error('Failed to save ruleset', error);
    if (statusElement) {
      statusElement.textContent = 'Unable to save ruleset. Check input values.';
      statusElement.classList.add('error');
    }
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = 'Save ruleset';
    }
  }
}

function safeJsonParse(value) {
  if (!value) return undefined;
  try {
    return JSON.parse(value);
  } catch (error) {
    console.warn('Invalid JSON input', value);
    return undefined;
  }
}

function confirmDelete(ruleset) {
  if (!confirm(`Delete ruleset ${ruleset.ruleset_id}?`)) return;
  deleteRuleset(ruleset.ruleset_id);
}

async function deleteRuleset(rulesetId) {
  try {
    const response = await fetch(`${API_BASE}/api/rulesets/${encodeURIComponent(rulesetId)}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete ruleset');
    await loadRulesets();
  } catch (error) {
    console.error('Failed to delete ruleset', error);
    alert('Unable to delete ruleset.');
  }
}

function openModal() {
  const modal = document.getElementById('ruleset-modal');
  if (modal) {
    modal.classList.remove('hidden');
  }
}

function closeModal() {
  const modal = document.getElementById('ruleset-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}
