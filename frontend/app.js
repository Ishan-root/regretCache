'use strict';

const POLICIES = ['FIFO', 'LRU', 'Optimal', 'RegretCache'];
const COLORS = { FIFO: '#8b93a7', LRU: '#3b82f6', Optimal: '#10b981', RegretCache: '#ef4444' };
const RANGE_IDS = ['n_requests', 'capacity', 'ghost_size', 'half_life'];

const state = { data: null, idx: 1, timer: null };
const charts = {};
let activeCell = null;

function el(id) {
  return document.getElementById(id);
}

function showError(msg) {
  const box = el('error');
  box.textContent = msg;
  box.hidden = false;
}

function hideError() {
  const box = el('error');
  box.textContent = '';
  box.hidden = true;
}

async function runSimulation() {
  const btn = el('run');
  btn.disabled = true;
  btn.textContent = 'Running...';
  try {
    const payload = {
      workload: document.getElementById('workload').value,
      n_requests: Number(document.getElementById('n_requests').value),
      capacity: Number(document.getElementById('capacity').value),
      ghost_size: Number(document.getElementById('ghost_size').value),
      half_life: Number(document.getElementById('half_life').value),
      seed: Number(document.getElementById('seed').value),
    };
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) { showError('Could not run the simulation. Check the inputs.'); return; }
    state.data = await res.json();
    hideError();
    renderAll();
  } catch (err) {
    showError('Could not reach the server. Is it running?');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run simulation';
  }
}

function renderAll() {
  renderSummary();
  renderCharts();
  resetReplay();
}

/* Summary */

function renderSummary() {
  const data = state.data;
  const g = data.gap_closed;
  let text;
  if (g === null) {
    text = 'LRU already matches Optimal on this run, so there is no gap to close.';
  } else if (g >= 0) {
    text = 'RegretCache closed ' + Math.round(g * 100) + '% of the gap between LRU and Optimal.';
  } else {
    text = 'RegretCache did worse than LRU on this run.';
  }
  el('headline').textContent = text;

  const tbody = el('results-table').querySelector('tbody');
  tbody.innerHTML = '';
  POLICIES.forEach((name) => {
    const r = data.results[name];
    const tr = document.createElement('tr');
    if (name === 'RegretCache') tr.className = 'rc-row';
    const label = name === 'Optimal' ? 'Optimal (ceiling)' : name;
    [label, r.hits, r.misses, (r.hit_rate * 100).toFixed(1) + '%'].forEach((v) => {
      const td = document.createElement('td');
      td.textContent = v;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

/* Charts */

function makeChart(key, canvasId, config) {
  if (typeof Chart === 'undefined') return;
  if (charts[key]) charts[key].destroy();
  charts[key] = new Chart(el(canvasId), config);
}

function renderCharts() {
  const data = state.data;

  makeChart('misses', 'chart-misses', {
    type: 'bar',
    data: {
      labels: POLICIES,
      datasets: [{
        label: 'Misses',
        data: POLICIES.map((p) => data.results[p].misses),
        backgroundColor: POLICIES.map((p) => COLORS[p]),
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });

  makeChart('sweep', 'chart-sweep', {
    type: 'line',
    data: {
      labels: data.sweep.capacities,
      datasets: POLICIES.map((p) => ({
        label: p,
        data: data.sweep.hit_rate[p].map((v) => v * 100),
        borderColor: COLORS[p],
        backgroundColor: COLORS[p],
        borderDash: p === 'Optimal' ? [6, 4] : [],
        borderWidth: p === 'RegretCache' ? 3 : 2,
        tension: 0.15,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: 'Cache size (pages)' } },
        y: { title: { display: true, text: 'Hit rate (%)' } },
      },
    },
  });

  const rcSteps = data.results.RegretCache.steps;
  makeChart('regret', 'chart-regret', {
    type: 'line',
    data: {
      labels: rcSteps.map((s) => s.t),
      datasets: [{
        label: 'Regret rate',
        data: rcSteps.map((s) => s.regret_rate),
        borderColor: COLORS.RegretCache,
        backgroundColor: COLORS.RegretCache,
        pointRadius: 0,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { min: 0, max: 1 } },
    },
  });
}

/* Replay */

function currentSteps() {
  return state.data.results[el('replay_policy').value].steps;
}

function stopTimer() {
  if (state.timer !== null) {
    clearInterval(state.timer);
    state.timer = null;
  }
  el('replay_play').textContent = 'Play';
}

function resetReplay() {
  stopTimer();
  state.idx = 1;
  const n = state.data.trace.length;
  const slider = el('replay_slider');
  slider.max = String(n);
  slider.value = '1';
  buildStrip();
  setIdx(1);
}

function buildStrip() {
  const strip = el('replay_strip');
  strip.innerHTML = '';
  activeCell = null;
  const frag = document.createDocumentFragment();
  currentSteps().forEach((s) => {
    const cell = document.createElement('button');
    cell.type = 'button';
    cell.className = s.hit ? 'hit' : 'miss';
    cell.title = 't=' + s.t + ' page ' + s.page + ' ' + (s.hit ? 'HIT' : 'MISS');
    cell.dataset.t = String(s.t);
    frag.appendChild(cell);
  });
  strip.appendChild(frag);
}

function makeChip(text, sub, isCurrent) {
  const chip = document.createElement('div');
  chip.className = isCurrent ? 'chip current' : 'chip';
  chip.textContent = String(text);
  if (sub !== undefined && sub !== null) {
    const small = document.createElement('small');
    small.textContent = String(sub);
    chip.appendChild(small);
  }
  return chip;
}

function renderStep() {
  if (!state.data) return;
  const policy = el('replay_policy').value;
  const step = currentSteps()[state.idx - 1];
  if (!step) return;
  const isRC = policy === 'RegretCache';

  let info = 'Request ' + step.t + ': page ' + step.page + ', ' + (step.hit ? 'HIT' : 'MISS');
  if (!step.hit && step.evicted !== null) info += ', evicted page ' + step.evicted;
  el('replay_info').textContent = info;

  const cacheRow = el('replay_cache');
  cacheRow.innerHTML = '';
  step.cache.forEach((page) => {
    const sub = isRC ? step.scores[String(page)] : null;
    cacheRow.appendChild(makeChip(page, sub, page === step.page));
  });

  const ghostRow = el('replay_ghost');
  const stats = el('replay_stats');
  ghostRow.innerHTML = '';
  if (isRC) {
    const title = document.createElement('div');
    title.className = 'row-title';
    title.textContent = 'Recently evicted (ghost list)';
    const chips = document.createElement('div');
    chips.className = 'chips';
    step.ghost.forEach((page) => chips.appendChild(makeChip(page, null, false)));
    ghostRow.appendChild(title);
    ghostRow.appendChild(chips);
    ghostRow.hidden = false;
    stats.textContent = 'Regret rate ' + step.regret_rate.toFixed(2) +
      ', mistakes ' + step.mistakes;
    stats.hidden = false;
  } else {
    ghostRow.hidden = true;
    stats.textContent = '';
    stats.hidden = true;
  }
}

function setIdx(i) {
  if (!state.data) return;
  const n = state.data.trace.length;
  const idx = Math.min(n, Math.max(1, Math.round(i)));
  state.idx = idx;
  el('replay_slider').value = String(idx);

  const strip = el('replay_strip');
  const next = strip.children[idx - 1] || null;
  if (activeCell && activeCell !== next) activeCell.classList.remove('active');
  if (next) next.classList.add('active');
  activeCell = next;

  renderStep();
}

function togglePlay() {
  if (!state.data) return;
  if (state.timer !== null) {
    stopTimer();
    return;
  }
  const n = state.data.trace.length;
  if (state.idx >= n) setIdx(1);
  el('replay_play').textContent = 'Pause';
  state.timer = setInterval(() => {
    if (state.idx >= n) {
      stopTimer();
      return;
    }
    setIdx(state.idx + 1);
  }, 300);
}

/* Startup */

function init() {
  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
  }

  RANGE_IDS.forEach((id) => {
    const input = el(id);
    const out = el(id + '_val');
    input.addEventListener('input', () => { out.textContent = input.value; });
  });

  el('run').addEventListener('click', runSimulation);
  el('replay_slider').addEventListener('input', (e) => setIdx(Number(e.target.value)));
  el('replay_prev').addEventListener('click', () => setIdx(state.idx - 1));
  el('replay_next').addEventListener('click', () => setIdx(state.idx + 1));
  el('replay_play').addEventListener('click', togglePlay);
  el('replay_strip').addEventListener('click', (e) => {
    const t = e.target.dataset ? e.target.dataset.t : undefined;
    if (t) setIdx(Number(t));
  });
  el('replay_policy').addEventListener('change', () => {
    if (!state.data) return;
    const keep = state.idx;
    buildStrip();
    setIdx(keep);
  });

  runSimulation();
}

init();
