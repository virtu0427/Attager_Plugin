const API_BASE = window.location.origin;
const DEFAULT_LIMIT = 1000;

let logsCache = [];
let indexedLogs = [];
let miniSearch;

const filters = {
  agent: 'all',
  verdict: 'all',
  timeframe: 'all',
  query: '',
};

window.addEventListener('DOMContentLoaded', () => {
  setupControls();
  fetchLogs();
});

function translateVerdict(verdict = '') {
  const normalized = verdict.toLowerCase();
  if (normalized === 'pass') return '통과';
  if (normalized === 'violation' || normalized === 'blocked') return '위반';
  if (normalized === 'allow') return '허용';
  if (normalized === 'deny') return '거부';
  if (!verdict) return '미확인';
  return verdict;
}

function setupControls() {
  const searchInput = document.getElementById('log-search');
  if (searchInput) {
    searchInput.addEventListener('input', (event) => {
      filters.query = event.target.value.trim();
      renderResults();
    });
  }

  const agentFilter = document.getElementById('filter-agent');
  if (agentFilter) {
    agentFilter.addEventListener('change', (event) => {
      filters.agent = event.target.value;
      renderResults();
    });
  }

  const verdictFilter = document.getElementById('filter-verdict');
  if (verdictFilter) {
    verdictFilter.addEventListener('change', (event) => {
      filters.verdict = event.target.value;
      renderResults();
    });
  }

  const timeframeFilter = document.getElementById('filter-timeframe');
  if (timeframeFilter) {
    timeframeFilter.addEventListener('change', (event) => {
      filters.timeframe = event.target.value;
      renderResults();
    });
  }

  const refreshButton = document.getElementById('refresh-logs');
  if (refreshButton) {
    refreshButton.addEventListener('click', () => fetchLogs(true));
  }

  const modal = document.getElementById('log-modal');
  const closeModalButton = document.getElementById('close-log-modal');
  if (closeModalButton && modal) {
    closeModalButton.addEventListener('click', () => closeModal(modal));
  }
  if (modal) {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeModal(modal);
      }
    });
  }
}

async function fetchLogs(isManual = false) {
  const refreshButton = document.getElementById('refresh-logs');
  if (refreshButton && isManual) {
    refreshButton.disabled = true;
    refreshButton.textContent = '새로고침 중…';
  }

  try {
    const response = await fetch(`${API_BASE}/api/logs?limit=${DEFAULT_LIMIT}`);
    if (!response.ok) throw new Error('로그를 불러오지 못했습니다');
    const logs = await response.json();

    logsCache = Array.isArray(logs) ? logs : [];
    buildIndex();
    populateAgentFilter();
    renderResults();
  } catch (error) {
    console.error('로그를 불러오지 못했습니다', error);
  } finally {
    if (refreshButton) {
      refreshButton.disabled = false;
      refreshButton.textContent = '새로고침';
    }
  }
}

function buildIndex() {
  miniSearch = new MiniSearch({
    fields: ['agent_id', 'message', 'policy_type', 'verdict', 'target_agent', 'plugin'],
    storeFields: ['timestamp', 'agent_id', 'message', 'policy_type', 'verdict', 'target_agent', 'plugin', 'extra'],
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
    },
  });

  indexedLogs = logsCache.map((log, idx) => ({
    id: idx,
    agent_id: log.agent_id || 'unknown',
    message: log.message || log.action || '',
    policy_type: log.policy_type || log.policy || '',
    verdict: log.verdict || '',
    target_agent: log.target_agent || log.destination_agent || '',
    plugin: log.plugin || log.plugin_name || '',
    timestamp: log.timestamp || '',
    extra: log,
  }));

  miniSearch.addAll(indexedLogs);
}

function populateAgentFilter() {
  const select = document.getElementById('filter-agent');
  if (!select) return;

  const agents = new Set(indexedLogs.map((log) => log.agent_id).filter(Boolean));
  const current = select.value;

  select.innerHTML = '<option value="all">모든 에이전트</option>';
  Array.from(agents)
    .sort()
    .forEach((agent) => {
      const option = document.createElement('option');
      option.value = agent;
      option.textContent = agent;
      select.appendChild(option);
    });

  if (Array.from(agents).includes(current)) {
    select.value = current;
    filters.agent = current;
  } else {
    filters.agent = 'all';
  }
}

function renderResults() {
  const query = filters.query;
  let results = indexedLogs;

  if (query) {
    const searchResults = miniSearch.search(query, {
      combineWith: 'AND',
    });
    const ids = new Set(searchResults.map((result) => result.id));
    results = indexedLogs.filter((log) => ids.has(log.id));
  }

  results = results.filter((log) => applyFilters(log));

  results.sort((a, b) => {
    const aTime = a.timestamp ? new Date(a.timestamp).getTime() : 0;
    const bTime = b.timestamp ? new Date(b.timestamp).getTime() : 0;
    return bTime - aTime;
  });

  updateCount(results.length);
  renderTable(results.slice(0, 200));
}

function applyFilters(log) {
  if (filters.agent !== 'all' && log.agent_id !== filters.agent) {
    return false;
  }

  if (filters.verdict !== 'all') {
    const verdict = (log.verdict || '').toLowerCase();
    if (filters.verdict === 'pass' && verdict !== 'pass') return false;
    if (filters.verdict === 'violation' && verdict !== 'violation') return false;
    if (filters.verdict === 'blocked' && verdict !== 'blocked') return false;
  }

  if (filters.timeframe !== 'all' && log.timestamp) {
    const timestamp = new Date(log.timestamp).getTime();
    const now = Date.now();
    const delta = now - timestamp;
    const limits = {
      '15m': 15 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
    };

    const allowed = limits[filters.timeframe];
    if (allowed && delta > allowed) {
      return false;
    }
  }

  return true;
}

function updateCount(count) {
  const pill = document.getElementById('log-count');
  if (pill) {
    pill.textContent = `${count}건`;
  }
}

function renderTable(logs) {
  const tbody = document.getElementById('logs-table-body');
  const template = document.getElementById('log-row-template');
  if (!tbody || !template) return;

  tbody.innerHTML = '';

  if (!logs || logs.length === 0) {
    const row = document.createElement('tr');
    row.innerHTML = '<td colspan="6" class="empty-state">조건에 맞는 로그가 없습니다.</td>';
    tbody.appendChild(row);
    return;
  }

  logs.forEach((log) => {
    const clone = template.content.cloneNode(true);
    const timeCell = clone.querySelector('.log-time');
    const agentCell = clone.querySelector('.log-agent');
    const verdictCell = clone.querySelector('.log-verdict');
    const contextCell = clone.querySelector('.log-context');
    const messageCell = clone.querySelector('.log-message');
    const actionButton = clone.querySelector('button');

    if (timeCell) {
      timeCell.textContent = log.timestamp ? new Date(log.timestamp).toLocaleString() : '없음';
    }
    if (agentCell) {
      agentCell.textContent = log.agent_id || '알 수 없음';
    }
    if (verdictCell) {
      const verdict = log.verdict || '미확인';
      verdictCell.innerHTML = `<span class="status-chip ${getVerdictClass(verdict)}">${translateVerdict(verdict)}</span>`;
    }
    if (contextCell) {
      const context = [log.policy_type, log.target_agent, log.plugin].filter(Boolean).join(' · ');
      contextCell.textContent = context || '없음';
    }
    if (messageCell) {
      messageCell.textContent = log.message || log.extra?.message || log.extra?.action || '내용 없음';
    }
    if (actionButton) {
      actionButton.addEventListener('click', () => openModal(log.extra));
    }

    tbody.appendChild(clone);
  });
}

function getVerdictClass(verdict) {
  const normalized = verdict.toLowerCase();
  if (normalized === 'violation' || normalized === 'blocked') return 'status-inactive';
  if (normalized === 'pass') return 'status-active';
  return 'status-warning';
}

function openModal(log) {
  const modal = document.getElementById('log-modal');
  const content = document.getElementById('log-modal-content');
  if (!modal || !content) return;

  content.textContent = JSON.stringify(log, null, 2);
  modal.classList.remove('hidden');
}

function closeModal(modal) {
  modal.classList.add('hidden');
}
