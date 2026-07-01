/* ============================================================
   BreatheSafe — Frontend SPA logic
   ============================================================ */

const API = '';  // Same origin

// ---- Helpers ----
const fmt = {
  num: (n) => n == null ? '—' : Number(n).toLocaleString('en-IN'),
  pct: (n) => n == null ? '—' : `${Number(n).toFixed(1)}%`,
  float: (n, d = 2) => n == null ? '—' : Number(n).toFixed(d),
  pm: (n) => n == null ? '—' : `${Number(n).toFixed(1)} µg/m³`,
};

const el = (id) => document.getElementById(id);

// ---- Load KPIs ----
async function loadSummary() {
  try {
    const res = await fetch(`${API}/api/summary`);
    const data = await res.json();
    el('kpiDistricts').querySelector('.kpi-value').textContent = fmt.num(data.districts_analyzed);
    el('kpiHigh').querySelector('.kpi-value').textContent = fmt.num(data.high_risk_count);
    el('kpiDesert').querySelector('.kpi-value').textContent = fmt.num(data.awareness_desert_count);
    const top = data.top_awareness_desert;
    if (top) {
      el('kpiTop').querySelector('.kpi-value').textContent = top.district;
      const sub = el('kpiTop').querySelector('.kpi-sub') || (() => {
        const s = document.createElement('div');
        s.className = 'kpi-sub';
        el('kpiTop').appendChild(s);
        return s;
      })();
      sub.textContent = `${top.state} · gap ${fmt.float(top.awareness_gap)} · est. undiagnosed ${fmt.num(top.estimated_undiagnosed)}`;
    } else {
      el('kpiTop').querySelector('.kpi-value').textContent = '—';
    }
  } catch (e) {
    console.error('loadSummary failed', e);
  }
}

// ---- Load states for filter ----
async function loadStateFilter() {
  try {
    const res = await fetch(`${API}/api/states`);
    const data = await res.json();
    const sel = el('stateFilter');
    data.rows
      .map(r => r.state_name)
      .sort()
      .forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        sel.appendChild(opt);
      });
  } catch (e) {
    console.error('loadStateFilter failed', e);
  }
}

// ---- Load districts table ----
async function loadDistricts() {
  const state = el('stateFilter').value;
  const risk = el('riskFilter').value;
  const search = el('searchBox').value.trim().toLowerCase();

  const params = new URLSearchParams();
  if (state) params.set('state', state);
  if (risk) params.set('risk_category', risk);
  params.set('limit', '100');
  params.set('sort_by', 'awareness_gap_score');

  const tbody = el('districtTableBody');
  tbody.innerHTML = '<tr><td colspan="11" class="loading">Loading…</td></tr>';

  try {
    const res = await fetch(`${API}/api/districts?${params}`);
    const data = await res.json();
    let rows = data.rows || [];
    if (search) {
      rows = rows.filter(r =>
        r.district_name.toLowerCase().includes(search) ||
        r.state_name.toLowerCase().includes(search)
      );
    }
    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="11" class="loading">No districts match your filter.</td></tr>';
      el('tableFoot').textContent = '';
      return;
    }
    tbody.innerHTML = rows.map((r, i) => `
      <tr>
        <td>${i + 1}</td>
        <td><strong>${r.district_name}</strong>${r.is_awareness_desert ? '<span class="desert-flag">DESERT</span>' : ''}</td>
        <td>${r.state_name}</td>
        <td>${fmt.float(r.risk_score, 3)}</td>
        <td>${fmt.float(r.awareness_gap_score, 3)}</td>
        <td>${fmt.pm(r.pm25_annual_mean)}</td>
        <td>${fmt.pct(r.pct_adults_hypertension)}</td>
        <td>${fmt.pct(r.pct_adults_overweight_obese)}</td>
        <td>${r.awareness_normalized != null ? fmt.float(r.awareness_normalized, 3) : '—'}</td>
        <td>${fmt.num(r.estimated_undiagnosed)}</td>
        <td><span class="risk-pill ${r.risk_category}">${r.risk_category}</span></td>
      </tr>
    `).join('');
    el('tableFoot').textContent = `Showing ${rows.length} district${rows.length === 1 ? '' : 's'} · sorted by awareness-gap score · data joined from NFHS-5 + Census 2011 + CPCB AQI + Google Trends`;
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="11" class="loading">Error loading: ${e.message}</td></tr>`;
  }
}

// ---- Agent chat ----
async function askAgent(question) {
  const resp = el('agentResponse');
  resp.classList.remove('empty');
  resp.innerHTML = '<p class="loading">Thinking…</p>';
  try {
    const res = await fetch(`${API}/api/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    resp.innerHTML = renderMarkdown(data.answer);
    // Append a small metadata line
    const meta = document.createElement('p');
    meta.className = 'muted';
    meta.style.marginTop = '12px';
    meta.textContent = `Tools called: ${data.tools_called.join(', ')} · ${data.tool_results_count} data points referenced`;
    resp.appendChild(meta);
  } catch (e) {
    resp.innerHTML = `<p style="color: var(--danger)">Error: ${e.message}</p>`;
  }
}

// ---- Minimal Markdown renderer (safe subset) ----
function renderMarkdown(md) {
  if (!md) return '';
  // Escape HTML
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

  // Tables
  html = html.replace(/((?:^\|.*\|\n)+)/gm, (block) => {
    const lines = block.trim().split('\n');
    if (lines.length < 2) return block;
    const head = lines[0].split('|').slice(1, -1).map(s => s.trim());
    const body = lines.slice(2).map(l => l.split('|').slice(1, -1).map(s => s.trim()));
    let t = '<table><thead><tr>';
    head.forEach(h => t += `<th>${h}</th>`);
    t += '</tr></thead><tbody>';
    body.forEach(r => {
      t += '<tr>';
      r.forEach(c => t += `<td>${c}</td>`);
      t += '</tr>';
    });
    t += '</tbody></table>';
    return t;
  });

  // Headers
  html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');

  // Bold / italic / code
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');

  // Lists
  html = html.replace(/(^[-*]\s+.+(\n[-*]\s+.+)*)/gm, (block) => {
    const items = block.split('\n').map(l => l.replace(/^[-*]\s+/, '').trim());
    return '<ul>' + items.map(i => `<li>${i}</li>`).join('') + '</ul>';
  });

  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr>');

  // Paragraphs (lines that aren't already tags)
  html = html.split('\n\n').map(p => {
    if (/^<(h\d|ul|ol|pre|table|hr)/.test(p.trim())) return p;
    return `<p>${p.replace(/\n/g, '<br>')}</p>`;
  }).join('\n');

  return html;
}

// ---- Image analysis ----
async function analyzeImage(file) {
  const resp = el('imageResponse');
  resp.classList.remove('empty');
  resp.innerHTML = '<p class="loading">Analyzing image with Vertex AI Vision (Gemini 2.5 Flash)…</p>';
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${API}/api/analyze-image`, { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    let html = '';
    if (data.extracted) {
      html += `<h4>Vision extraction</h4>`;
      html += `<pre>${JSON.stringify(data.extracted, null, 2)}</pre>`;
    }
    if (data.cross_reference) {
      const cr = data.cross_reference;
      html += `<h4>BigQuery cross-reference</h4>`;
      html += `<p>Matched district: <strong>${cr.matched_district}, ${cr.matched_state}</strong></p>`;
      html += `<ul>`;
      html += `<li>Risk score: <strong>${fmt.float(cr.risk_score, 3)}</strong> (${cr.risk_category})</li>`;
      html += `<li>Awareness gap: <strong>${fmt.float(cr.awareness_gap, 3)}</strong></li>`;
      html += `<li>PM2.5: <strong>${fmt.pm(cr.pm25_annual_mean)}</strong></li>`;
      html += `<li>Estimated undiagnosed cases: <strong>${fmt.num(cr.estimated_undiagnosed)}</strong></li>`;
      html += `</ul>`;
    } else if (data.extracted && data.extracted.location_name) {
      html += `<p style="color: var(--warn)">No matching district in our dataset for "${data.extracted.location_name}".</p>`;
    }
    if (data.note) {
      html += `<p class="muted">${data.note}</p>`;
    }
    resp.innerHTML = html;
  } catch (e) {
    resp.innerHTML = `<p style="color: var(--danger)">Error: ${e.message}</p>`;
  }
}

// ---- Event bindings ----
el('stateFilter').addEventListener('change', loadDistricts);
el('riskFilter').addEventListener('change', loadDistricts);
el('searchBox').addEventListener('input', debounce(loadDistricts, 200));
el('resetBtn').addEventListener('click', () => {
  el('stateFilter').value = '';
  el('riskFilter').value = '';
  el('searchBox').value = '';
  loadDistricts();
});

el('askForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const q = el('askInput').value.trim();
  if (q) askAgent(q);
});
document.querySelectorAll('.chip').forEach(btn => {
  btn.addEventListener('click', () => {
    const q = btn.getAttribute('data-prompt');
    el('askInput').value = q;
    askAgent(q);
  });
});

el('imageForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const f = el('imageInput').files[0];
  if (f) analyzeImage(f);
});

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// ---- Initial load ----
loadSummary();
loadStateFilter();
loadDistricts();
initDashboard();

// ============================================================
// Live India Dashboard (replaces the old Looker placeholder)
// ============================================================
let dashCache = { rows: [], stateNames: [] };

async function initDashboard() {
  // Pre-populate the state filter
  try {
    const r = await fetch(`${API}/api/states`);
    const d = await r.json();
    dashCache.stateNames = d.rows.map(s => s.state_name).sort();
    const sel = el('dashStateFilter');
    dashCache.stateNames.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s; opt.textContent = s;
      sel.appendChild(opt);
    });
  } catch (e) { console.error('dash states failed', e); }

  // Wire up controls
  ['dashStateFilter', 'dashRiskFilter', 'dashSortBy', 'dashLimit'].forEach(id => {
    el(id).addEventListener('change', loadDashboard);
  });

  await loadDashboard();
}

async function loadDashboard() {
  const state = el('dashStateFilter').value;
  const risk = el('dashRiskFilter').value;
  const sortBy = el('dashSortBy').value;
  const limit = el('dashLimit').value;

  const params = new URLSearchParams({ sort_by: sortBy, limit });
  if (state) params.set('state', state);
  if (risk) params.set('risk_category', risk);

  // Show loading state
  el('dashBarChart').innerHTML = '<div class="dash-loading">Loading…</div>';
  el('dashScatter').innerHTML = '';
  el('dashTable').querySelector('tbody').innerHTML = '<tr><td colspan="6" class="dash-loading">Loading…</td></tr>';

  try {
    const r = await fetch(`${API}/api/districts?${params}`);
    const d = await r.json();
    dashCache.rows = d.rows;
    renderDashBar(d.rows);
    renderDashScatter(d.rows);
    renderDashTable(d.rows);
  } catch (e) {
    el('dashBarChart').innerHTML = '<div class="dash-loading">Failed to load</div>';
    console.error('loadDashboard failed', e);
  }
}

function renderDashBar(rows) {
  const el2 = el('dashBarChart');
  if (!rows.length) { el2.innerHTML = '<div class="dash-loading">No rows</div>'; return; }
  const max = Math.max(...rows.map(r => r[el('dashSortBy').value] || 0), 0.001);
  el2.innerHTML = rows.slice(0, 10).map(r => {
    const v = r[el('dashSortBy').value] || 0;
    const pct = (v / max) * 100;
    return `
      <div class="dash-bar-row">
        <div class="dash-bar-label" title="${r.district_name}, ${r.state_name}">${r.district_name}, ${r.state_name}</div>
        <div class="dash-bar-track"><div class="dash-bar-fill cat-${r.risk_category}" style="width:${pct}%"></div></div>
        <div class="dash-bar-value">${fmt.float(v, 3)}</div>
      </div>`;
  }).join('');
}

function renderDashScatter(rows) {
  const el2 = el('dashScatter');
  if (!rows.length) { el2.innerHTML = '<div class="dash-loading">No rows</div>'; return; }
  // Sample down to 200 for performance
  const sample = rows.length > 200 ? rows.sort(() => Math.random() - 0.5).slice(0, 200) : rows;
  const W = 400, H = 240, PAD = 30;
  const pts = sample.map(r => {
    const x = PAD + (r.awareness_normalized || 0) * (W - 2 * PAD);
    const y = H - PAD - (r.risk_score || 0) * (H - 2 * PAD);
    const color = r.risk_category === 'HIGH' ? '#fc8181' : r.risk_category === 'MODERATE' ? '#f6ad55' : '#4fd1c5';
    const r2 = Math.max(2, Math.min(8, Math.sqrt(r.estimated_undiagnosed || 0) / 40));
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r2.toFixed(1)}" fill="${color}" fill-opacity="0.7" stroke="${color}" stroke-width="0.5"><title>${r.district_name}, ${r.state_name} — risk ${fmt.float(r.risk_score,2)}, awareness ${fmt.float(r.awareness_normalized,2)}</title></circle>`;
  }).join('');
  el2.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <line x1="${PAD}" y1="${H-PAD}" x2="${W-PAD}" y2="${H-PAD}" stroke="#3a4a5e" stroke-width="0.5"/>
    <line x1="${PAD}" y1="${PAD}" x2="${PAD}" y2="${H-PAD}" stroke="#3a4a5e" stroke-width="0.5"/>
    <text x="${W/2}" y="${H-5}" fill="#7d8ea3" font-size="9" text-anchor="middle">Awareness (0 = none, 1 = high)</text>
    <text x="5" y="${PAD+5}" fill="#7d8ea3" font-size="9">Risk</text>
    <text x="5" y="${H-PAD-5}" fill="#7d8ea3" font-size="9">Low</text>
    <text x="5" y="${PAD+10}" fill="#7d8ea3" font-size="9">High</text>
    ${pts}
  </svg>`;
}

function renderDashTable(rows) {
  const tb = el('dashTable').querySelector('tbody');
  if (!rows.length) { tb.innerHTML = '<tr><td colspan="6" class="dash-loading">No rows</td></tr>'; return; }
  tb.innerHTML = rows.slice(0, 50).map(r => `
    <tr>
      <td>${r.district_name}</td>
      <td>${r.state_name}</td>
      <td>${fmt.float(r.risk_score, 3)}</td>
      <td>${fmt.float(r.awareness_gap_score, 3)}</td>
      <td>${fmt.num(r.estimated_undiagnosed)}</td>
      <td>${r.pm25_annual_mean != null ? fmt.float(r.pm25_annual_mean, 1) : '—'}</td>
    </tr>`).join('');
}
