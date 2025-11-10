const API_BASE = window.location.origin;
const REFRESH_INTERVAL = 30000;

let eventsChart;

window.addEventListener('DOMContentLoaded', () => {
  setupControls();
  loadAll();
  setInterval(loadAll, REFRESH_INTERVAL);
});

function setupControls() {
  const refreshFlowButton = document.getElementById('refresh-flow');
  if (refreshFlowButton) {
    refreshFlowButton.addEventListener('click', () => loadAgentFlow(true));
  }

  const refreshDashboardButton = document.getElementById('refresh-dashboard');
  if (refreshDashboardButton) {
    refreshDashboardButton.addEventListener('click', () => loadAll(true));
  }
}

function loadAll(manual = false) {
  loadDashboardStats();
  loadRecentLogs();
  loadAgentFlow(manual);
}

async function loadDashboardStats() {
  try {
    const response = await fetch(`${API_BASE}/api/stats`);
    if (!response.ok) throw new Error('Failed to load stats');
    const stats = await response.json();

    updateStatCard('total-agents', stats.total_agents ?? 0);
    updateStatCard('total-rulesets', stats.total_rulesets ?? 0);
    updateStatCard('total-violations', stats.recent_violations ?? 0);
    updateStatCard('total-events', stats.total_events ?? 0);

    updateRiskIndicator(stats);
  } catch (error) {
    console.error('Failed to load dashboard stats', error);
  }
}

function updateStatCard(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = Number.isFinite(value) ? value : '--';
  }
}

function updateRiskIndicator(stats) {
  const violations = stats.recent_violations ?? 0;
  const total = stats.total_events ?? 0;
  const riskScore = total === 0 ? 0 : Math.min(100, Math.round((violations / total) * 100));

  const scoreElement = document.getElementById('risk-score');
  const barElement = document.getElementById('risk-bar-fill');

  if (scoreElement) {
    scoreElement.textContent = `${riskScore}`;
  }

  if (barElement) {
    barElement.style.width = `${riskScore}%`;
  }
}

async function loadRecentLogs() {
  try {
    const response = await fetch(`${API_BASE}/api/logs?limit=120`);
    if (!response.ok) throw new Error('Failed to load logs');
    const logs = await response.json();

    renderRecentLogs(logs.slice(0, 12));
    updateEventsChart(logs);
  } catch (error) {
    console.error('Failed to load recent logs', error);
  }
}

function renderRecentLogs(logs) {
  const container = document.getElementById('dashboard-log-list');
  if (!container) return;

  container.innerHTML = '';

  if (!logs || logs.length === 0) {
    container.innerHTML = `<p style="color: var(--text-secondary); text-align: center;">No recent activity</p>`;
    return;
  }

  logs.forEach((log) => {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    if (['VIOLATION', 'BLOCKED'].includes((log.verdict || '').toUpperCase())) {
      entry.classList.add('violation');
    }

    const timestamp = log.timestamp ? new Date(log.timestamp) : null;
    const formattedTime = timestamp ? timestamp.toLocaleString() : 'N/A';

    entry.innerHTML = `
      <div class="log-header">
        <div>
          <strong>${log.agent_id || 'Unknown Agent'}</strong>
          <span class="pill" style="margin-left: 0.5rem;">${log.policy_type || 'policy'}</span>
        </div>
        <span class="status-chip ${log.verdict && log.verdict.toUpperCase() === 'VIOLATION' ? 'status-inactive' : 'status-active'}">
          ${log.verdict || 'N/A'}
        </span>
      </div>
      <div class="log-message">${log.message || log.action || 'No message provided'}</div>
      <div class="log-meta">
        <span>${formattedTime}</span>
        ${log.target_agent ? `<span>→ ${log.target_agent}</span>` : ''}
      </div>
    `;

    container.appendChild(entry);
  });
}

function updateEventsChart(logs) {
  const canvas = document.getElementById('events-chart');
  if (!canvas) return;

  const now = new Date();
  const buckets = [];

  for (let i = 59; i >= 0; i -= 1) {
    const bucketTime = new Date(now.getTime() - i * 60 * 1000);
    const label = `${bucketTime.getHours().toString().padStart(2, '0')}:${bucketTime
      .getMinutes()
      .toString()
      .padStart(2, '0')}`;

    buckets.push({
      label,
      start: bucketTime,
      end: new Date(bucketTime.getTime() + 60 * 1000),
      events: 0,
      violations: 0,
    });
  }

  logs.forEach((log) => {
    if (!log.timestamp) return;
    const ts = new Date(log.timestamp).getTime();
    for (const bucket of buckets) {
      if (ts >= bucket.start.getTime() && ts < bucket.end.getTime()) {
        bucket.events += 1;
        if (['VIOLATION', 'BLOCKED'].includes((log.verdict || '').toUpperCase())) {
          bucket.violations += 1;
        }
        break;
      }
    }
  });

  const labels = buckets.map((bucket) => bucket.label);
  const eventSeries = buckets.map((bucket) => bucket.events);
  const violationSeries = buckets.map((bucket) => bucket.violations);

  const chartRange = document.getElementById('chart-range');
  if (chartRange) {
    chartRange.textContent = `Last ${buckets.length} minutes`;
  }

  if (!eventsChart) {
    eventsChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Events',
            data: eventSeries,
            borderColor: 'rgba(109, 211, 255, 0.85)',
            backgroundColor: 'rgba(109, 211, 255, 0.1)',
            tension: 0.35,
            fill: true,
          },
          {
            label: 'Violations',
            data: violationSeries,
            borderColor: 'rgba(255, 77, 79, 0.9)',
            backgroundColor: 'rgba(255, 77, 79, 0.15)',
            tension: 0.35,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { color: 'rgba(255, 255, 255, 0.6)', maxTicksLimit: 8 },
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
          },
          y: {
            beginAtZero: true,
            ticks: { color: 'rgba(255, 255, 255, 0.6)' },
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
          },
        },
        plugins: {
          legend: {
            labels: { color: 'rgba(255, 255, 255, 0.75)' },
          },
          tooltip: {
            mode: 'index',
            intersect: false,
          },
        },
      },
    });
  } else {
    eventsChart.data.labels = labels;
    eventsChart.data.datasets[0].data = eventSeries;
    eventsChart.data.datasets[1].data = violationSeries;
    eventsChart.update('none');
  }
}

async function loadAgentFlow(manual = false) {
  const statusPill = document.getElementById('flow-status');
  if (statusPill && manual) {
    statusPill.textContent = 'Refreshing…';
  }

  try {
    const response = await fetch(`${API_BASE}/api/graph/agent-flow?limit=200`);
    if (!response.ok) throw new Error('Failed to load agent flow');
    const flow = await response.json();

    renderAgentFlowGraph(flow);
    renderAgentStatusList(flow.nodes);

    if (statusPill) {
      const updatedAt = flow.meta?.generated_at
        ? new Date(flow.meta.generated_at).toLocaleTimeString()
        : new Date().toLocaleTimeString();
      statusPill.textContent = `Updated ${updatedAt}`;
    }
  } catch (error) {
    console.error('Failed to load agent flow', error);
    if (statusPill) {
      statusPill.textContent = 'Sync failed';
    }
  }
}

function renderAgentStatusList(nodes = []) {
  const list = document.getElementById('agent-status-list');
  if (!list) return;

  const knownAgents = nodes.filter((node) => node.status !== 'external' && node.id !== 'unknown');
  knownAgents.sort((a, b) => (b.metrics?.events || 0) - (a.metrics?.events || 0));

  list.innerHTML = '';

  if (knownAgents.length === 0) {
    list.innerHTML = `<li style="color: var(--text-secondary);">No agent telemetry available.</li>`;
    return;
  }

  knownAgents.forEach((node) => {
    const item = document.createElement('li');
    item.className = 'agent-status-item';

    const status = (node.status || 'unknown').toLowerCase();
    const statusClass = status === 'active' ? 'status-active' : status === 'inactive' ? 'status-inactive' : 'status-warning';

    const plugins = Array.isArray(node.plugins)
      ? node.plugins
          .map((plugin) => (typeof plugin === 'string' ? plugin : plugin.name))
          .filter(Boolean)
          .join(', ')
      : '';

    const metrics = node.metrics || { events: 0, violations: 0 };

    item.innerHTML = `
      <div class="agent-meta">
        <span class="name">${node.name || node.id}</span>
        <span class="plugins">${plugins || 'No plugins registered'}</span>
      </div>
      <div class="agent-metrics">
        <span class="status-chip ${statusClass}">${status.toUpperCase()}</span>
        <span class="pill">${metrics.events || 0} events</span>
        <span class="pill">${metrics.violations || 0} violations</span>
      </div>
    `;

    list.appendChild(item);
  });
}

function renderAgentFlowGraph(flow) {
  const svgElement = document.getElementById('agent-flow-graph');
  const tooltip = document.getElementById('graph-tooltip');
  if (!svgElement || !tooltip) return;

  const svg = d3.select(svgElement);
  svg.selectAll('*').remove();

  const container = svgElement.parentElement;
  const width = container?.clientWidth || 720;
  const height = container?.clientHeight || 480;

  svg.attr('viewBox', `0 0 ${width} ${height}`);

  const nodes = flow.nodes?.map((node) => ({ ...node })) || [];
  const links = flow.edges?.map((edge) => ({ ...edge })) || [];

  const simulation = d3
    .forceSimulation(nodes)
    .force(
      'link',
      d3
        .forceLink(links)
        .id((d) => d.id)
        .distance((d) => 140 - Math.min(d.count || 0, 60))
        .strength(0.4)
    )
    .force('charge', d3.forceManyBody().strength(-260))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(60));

  const link = svg
    .append('g')
    .attr('stroke', 'rgba(109, 211, 255, 0.3)')
    .attr('stroke-width', 1.5)
    .selectAll('line')
    .data(links)
    .enter()
    .append('line')
    .attr('class', 'flow-link')
    .attr('stroke-width', (d) => Math.max(1.5, Math.log(d.count + 1) * 2));

  const nodeGroup = svg
    .append('g')
    .selectAll('g')
    .data(nodes)
    .enter()
    .append('g')
    .attr('class', 'flow-node')
    .call(
      d3
        .drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    );

  nodeGroup
    .append('circle')
    .attr('r', (d) => 26 + Math.min(12, Math.log((d.metrics?.events || 0) + 1) * 6))
    .attr('class', (d) => `node-circle status-${(d.status || 'unknown').toLowerCase()}`)
    .on('mouseover', (event, d) => showTooltip(event, d))
    .on('mousemove', (event, d) => showTooltip(event, d))
    .on('mouseout', hideTooltip);

  nodeGroup
    .append('text')
    .attr('dy', 4)
    .attr('text-anchor', 'middle')
    .attr('class', 'node-label')
    .text((d) => (d.name || d.id).split(' ')[0]);

  simulation.on('tick', () => {
    link
      .attr('x1', (d) => clampPosition(d.source.x, width))
      .attr('y1', (d) => clampPosition(d.source.y, height))
      .attr('x2', (d) => clampPosition(d.target.x, width))
      .attr('y2', (d) => clampPosition(d.target.y, height));

    nodeGroup.attr('transform', (d) => `translate(${clampPosition(d.x, width)}, ${clampPosition(d.y, height)})`);
  });

  function showTooltip(event, node) {
    if (!tooltip) return;
    tooltip.classList.remove('hidden');
    tooltip.style.left = `${event.offsetX}px`;
    tooltip.style.top = `${event.offsetY}px`;

    const metrics = node.metrics || { events: 0, violations: 0 };
    const plugins = Array.isArray(node.plugins)
      ? node.plugins
          .map((plugin) => (typeof plugin === 'string' ? plugin : plugin.name))
          .filter(Boolean)
      : [];

    tooltip.innerHTML = `
      <div class="tooltip-title">${node.name || node.id}</div>
      <div class="tooltip-meta">${(node.status || 'unknown').toUpperCase()}</div>
      <ul>
        <li><strong>${metrics.events || 0}</strong> recent events</li>
        <li><strong>${metrics.violations || 0}</strong> violations</li>
        <li><strong>${plugins.length}</strong> plugins</li>
      </ul>
    `;
  }

  function hideTooltip() {
    if (!tooltip) return;
    tooltip.classList.add('hidden');
  }
}

function clampPosition(value, max) {
  return Math.max(40, Math.min(max - 40, value || 0));
}
