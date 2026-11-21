/* HMX Predictor frontend — all data comes from the local backend API. */
'use strict';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtTime = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? String(iso) : d.toLocaleString();
};
let cache = { status: null, results: [], predictions: [], stats: null, evaluations: [] };
let countdownTimer = null;

async function api(path, options) {
  const r = await fetch(path, options);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

function bar(label, value, cls = '') {
  const pct = Math.max(0, Math.min(100, (value || 0) * 100));
  return `<div class="bar-row"><div class="bar-top"><span>${esc(label)}</span><span>${pct.toFixed(1)}%</span></div>
    <div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div></div>`;
}

function colourChips(colour) {
  return String(colour || '').split(',').filter(Boolean)
    .map(c => `<span class="chip ${esc(c)}">${esc(c)}</span>`).join('');
}

function renderHome() {
  const st = cache.status || {};
  const cur = st.collector && st.collector.tracker;
  const current = cur && cur.current_period ? cur.current_period : '—';
  $('currentPeriod').textContent = current;
  const cycle = (st.collector && st.collector.last_cycle) || {};
  const schedule = cycle.schedule || null;
  $('nextPeriod').textContent = schedule && schedule.next ? `next ${schedule.next.issue_number}` : 'next —';
  $('currentWindow').textContent = schedule && schedule.current
    ? `${fmtTime(new Date(schedule.current.start_ms).toISOString())} – ${fmtTime(new Date(schedule.current.end_ms).toISOString())}`
    : 'waiting for server schedule';

  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    if (!schedule || !schedule.current) return;
    const remain = Math.max(0, Math.floor((schedule.current.end_ms - Date.now()) / 1000));
    $('countdown').textContent = `${String(Math.floor(remain / 60)).padStart(2,'0')}:${String(remain % 60).padStart(2,'0')}`;
  }, 1000);

  const latest = cache.results[0];
  if (!latest) {
    $('latestResult').className = 'empty';
    $('latestResult').textContent = 'No result collected yet.';
    $('latestResultTime').textContent = '—';
  } else {
    $('latestResult').className = '';
    $('latestResult').innerHTML = `<span class="num ${esc(latest.result_colour.split(',')[0])}">${latest.result_number}</span>
      ${colourChips(latest.result_colour)} <span class="chip ${latest.result_size.toLowerCase()}">${esc(latest.result_size)}</span>
      <div class="small muted">${esc(latest.period_id)} · source ${esc((latest.source_url || '').split('/')[2] || 'import')}</div>`;
    $('latestResultTime').textContent = fmtTime(latest.result_timestamp);
  }

  const pending = cache.predictions.filter(p => p.prediction_status !== 'evaluated');
  const p = pending[0];
  const statusChip = $('predictionStatus');
  if (!p) {
    statusChip.textContent = 'none pending';
    statusChip.className = 'chip';
    $('latestPrediction').className = 'empty';
    $('latestPrediction').textContent = 'No pending prediction yet. The local collector creates one at each server-observed period transition.';
    $('numberBars').className = 'empty'; $('numberBars').textContent = 'No model output yet.';
    $('colourBars').className = 'empty'; $('colourBars').textContent = 'No model output yet.';
  } else {
    statusChip.textContent = p.is_late ? 'LATE (excluded)' : p.prediction_status;
    statusChip.className = 'chip ' + (p.is_late ? 'red' : 'green');
    $('latestPrediction').className = '';
    $('latestPrediction').innerHTML = `<div class="row-between"><div>
      <div class="label">PERIOD ${esc(p.period_id)}</div>
      <div class="big">${esc(p.selected_number)}</div></div>
      <div>${colourChips(p.selected_colour)}<span class="chip ${p.selected_size.toLowerCase()}">${esc(p.selected_size)}</span></div></div>
      <div class="small muted">cutoff ${esc(p.data_cutoff_period || '—')} · n=${p.sample_count} · created ${fmtTime(p.created_at)}</div>`;
    $('numberBars').className = '';
    $('numberBars').innerHTML = Object.entries(p.number_probs)
      .sort((a,b) => Number(a[0]) - Number(b[0])).map(([k,v]) => bar(k, v)).join('');
    $('colourBars').className = '';
    $('colourBars').innerHTML = Object.entries(p.colour_probs)
      .map(([k,v]) => bar(k, v, k)).join('') + bar('Big', p.big_prob, 'big') + bar('Small', p.small_prob, 'small');
  }

  const feeds = st.feed_state || [];
  const fresh = feeds.filter(f => f.last_status === 'ok' || f.last_status === 'not_modified');
  const lastSuccess = fresh.map(f => f.last_success_at).filter(Boolean).sort().pop();
  const statusText = feeds.map(f => `${esc(f.feed_key)}: ${esc(f.last_status || 'unknown')}`).join(' · ') || 'No feed data.';
  $('collectorStatus').innerHTML = `running: <b>${st.collector && st.collector.running ? 'yes' : 'no'}</b>
    · cycles: <b>${st.collector && st.collector.cycles || 0}</b>
    · last success: <b>${fmtTime(lastSuccess)}</b><br>${statusText}`;
  $('lastUpdate').textContent = 'checked ' + fmtTime(new Date().toISOString());
  $('statusPill').textContent = st.provider_enabled ? (fresh.length ? 'feed online' : 'feed idle') : 'import only';
  $('statusPill').className = 'status-pill ' + (fresh.length ? 'online' : '');
}

function renderAnalytics() {
  const s = cache.stats;
  if (!s || !s.sample_size) return;
  const max = Math.max(1, ...Object.values(s.number_counts));
  $('sampleSize').textContent = `sample ${s.sample_size}`;
  $('analyticsNumbers').className = '';
  $('analyticsNumbers').innerHTML = Object.entries(s.number_counts).map(([k,v]) =>
    `<div class="bar-row"><div class="bar-top"><span>${k}</span><span>${v}</span></div>
     <div class="bar-track"><div class="bar-fill" style="width:${v/max*100}%"></div></div></div>`).join('');
  $('analyticsColours').className = '';
  $('analyticsColours').innerHTML = Object.entries(s.colour_counts).map(([k,v]) => bar(k, v / s.sample_size, k.split(',')[0])).join('') +
    `<div class="metric"><span>Big</span><b>${s.size_counts.Big || 0}</b></div>
     <div class="metric"><span>Small</span><b>${s.size_counts.Small || 0}</b></div>`;
  $('analyticsPatterns').className = '';
  $('analyticsPatterns').innerHTML = `<div class="metric"><span>Sample size</span><b>${s.sample_size}</b></div>
    <div class="metric"><span>Consecutive repeats</span><b>${s.consecutive_repeats}</b></div>
    <div class="metric"><span>Missing periods</span><b>${(cache.results[0] && s.missing_count) || '—'}</b></div>
    <div class="small muted" style="margin-top:8px">${esc(s.note)}</div>`;
}

function renderHistory() {
  const rows = cache.results;
  $('historyMeta').textContent = `${rows.length} shown`;
  if (!rows.length) return;
  $('historyList').className = '';
  $('historyList').innerHTML = `<div class="history-row head"><span>Period</span><span>No.</span><span>Colour/Size</span><span>End (local)</span></div>` +
    rows.map(r => `<div class="history-row"><span>${esc(r.period_id)}</span>
      <span class="num ${esc(r.result_colour.split(',')[0])}">${r.result_number}</span>
      <span>${colourChips(r.result_colour)}<span class="chip ${r.result_size.toLowerCase()}">${esc(r.result_size)}</span></span>
      <span class="muted">${fmtTime(r.result_timestamp)}</span></div>`).join('');
}

function renderAccuracy() {
  const s = cache.stats;
  if (!s) return;
  $('lifecycleSummary').className = '';
  $('lifecycleSummary').innerHTML = `<div class="metric"><span>Total predictions</span><b>${s.total_predictions || 0}</b></div>
    <div class="metric"><span>Evaluated</span><b>${s.evaluated_predictions || 0}</b></div>
    <div class="metric"><span>Pending</span><b>${s.pending_predictions || 0}</b></div>
    <div class="metric"><span>Late created / excluded</span><b>${s.late_predictions_created || 0} / ${s.late_evaluations_excluded || 0}</b></div>`;

  const a = s.accuracy || {};
  if (!a.count) {
    $('accuracySummary').className = 'empty';
    $('accuracySummary').textContent = a.note || 'No evaluated predictions yet.';
  } else {
    $('accuracySummary').className = '';
    $('accuracySummary').innerHTML = `<div class="metric"><span>Valid evaluations</span><b>${a.count}</b></div>
      <div class="metric"><span>Correct / incorrect number</span><b>${a.correct_number || 0} / ${a.incorrect_number || 0}</b></div>
      <div class="metric"><span>Number accuracy</span><b>${(a.exact_accuracy*100).toFixed(1)}%</b></div>
      <div class="metric"><span>Colour accuracy</span><b>${(a.colour_accuracy*100).toFixed(1)}%</b></div>
      <div class="metric"><span>Big/Small accuracy</span><b>${(a.size_accuracy*100).toFixed(1)}%</b></div>
      <div class="metric"><span>Log loss (model / baseline)</span><b>${a.mean_log_loss.toFixed(3)} / ${a.baseline_log_loss.toFixed(3)}</b></div>
      <div class="metric"><span>Brier (model / baseline)</span><b>${a.mean_brier.toFixed(3)} / ${a.baseline_brier.toFixed(3)}</b></div>
      <div class="small muted" style="margin-top:8px">${esc(a.note)}</div>`;
  }
  const cal = a.calibration || [];
  if (!cal.length) {
    $('calibrationInfo').className = 'empty';
    $('calibrationInfo').textContent = 'No calibration data yet.';
  } else {
    $('calibrationInfo').className = '';
    $('calibrationInfo').innerHTML = cal.map(c => `<div class="metric"><span>Confidence bucket ${c.bucket*10}-${c.bucket*10+9}% (n=${c.count})</span><b>${(c.hit_rate*100).toFixed(0)}% hits</b></div>`).join('');
  }
  const evs = cache.evaluations || [];
  $('accuracyList').className = evs.length ? '' : 'empty';
  $('accuracyList').innerHTML = evs.length ? evs.slice(0, 20).map(e =>
    `<div class="history-row"><span>${esc(e.period_id)}</span><span>${e.exact_number_hit ? '✓' : '·'}</span>
     <span>${e.colour_hit ? '✓' : '·'} / ${e.size_hit ? '✓' : '·'}</span><span>${e.log_loss.toFixed(2)}</span></div>`).join('') : 'Nothing evaluated yet.';
}

function renderSettings() {
  const st = cache.status || {};
  const cfg = cache.stats || {};
  $('windowInput').value = (st.config && st.config.analysis_window) || 200;
  const eng = (st.config && st.config.engine) || {};
  $('predictionConfig').innerHTML = `min history <b>${esc(eng.min_history)}</b> · window <b>${esc(eng.analysis_window)}</b>
    · tau <b>${esc(eng.recency_tau)}</b> · alpha <b>${esc(eng.dirichlet_alpha)}</b><br>
    weights: ${Object.entries(eng.weights || {}).map(([k,v]) => `${esc(k)} ${v}`).join(' · ')}`;
  $('sourceStatus').innerHTML = `Provider: <b>${st.provider_enabled ? 'enabled' : 'disabled'}</b><br>
    Poll interval: <b>${st.poll_interval_seconds}s</b><br>
    Last successful collection: <b>${fmtTime((st.feed_state || []).map(f => f.last_success_at).filter(Boolean).sort().pop())}</b><br>
    ${esc(st.source_note || '')}`;
}

async function loadAll() {
  try {
    const [status, results, predictions, stats, evaluations] = await Promise.all([
      api('/api/status'), api('/api/results?limit=200'),
      api('/api/predictions?limit=50'), api('/api/stats'), api('/api/evaluations?limit=200'),
    ]);
    cache = { status, results: results.results || [], predictions: predictions.predictions || [], stats,
              evaluations: evaluations.evaluations || [] };
    renderHome(); renderAnalytics(); renderHistory(); renderAccuracy(); renderSettings();
  } catch (e) {
    $('statusPill').textContent = 'backend offline';
    $('statusPill').className = 'status-pill offline';
  }
}

document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b === btn));
  document.querySelectorAll('.screen').forEach(s => s.classList.toggle('active', s.id === `screen-${btn.dataset.screen}`));
}));

$('saveWindow').addEventListener('click', async () => {
  const value = Number($('windowInput').value);
  const r = await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({analysis_window: value})});
  $('importResult').textContent = r.ok ? 'Analysis window saved.' : 'Could not save setting.';
});
$('collectNow').addEventListener('click', async () => {
  $('collectorActionResult').textContent = 'Collecting…';
  try { const r = await api('/api/collector/once'); $('collectorActionResult').textContent = 'Done: ' + JSON.stringify(r.statuses); await loadAll(); }
  catch (e) { $('collectorActionResult').textContent = 'Failed: ' + e.message; }
});
$('startCollector').addEventListener('click', async () => { await api('/api/collector/start', {method:'POST'}); await loadAll(); });
$('stopCollector').addEventListener('click', async () => { await api('/api/collector/stop', {method:'POST'}); await loadAll(); });
$('backupDb').addEventListener('click', async () => {
  try { const r = await api('/api/backup', {method:'POST'}); $('importResult').textContent = 'Backup: ' + r.backup; }
  catch (e) { $('importResult').textContent = 'Backup failed: ' + e.message; }
});
$('exportCsv').addEventListener('click', () => { window.location.href = '/api/export?format=csv'; });
$('exportJson').addEventListener('click', () => { window.location.href = '/api/export?format=json'; });
$('importFile').addEventListener('change', async (e) => {
  const file = e.target.files[0]; if (!file) return;
  const text = await file.text();
  const isCsv = file.name.toLowerCase().endsWith('.csv');
  const body = JSON.stringify({text, format: isCsv ? 'csv' : 'json'});
  try {
    const r = await fetch('/api/import', {method:'POST', headers:{'Content-Type':'application/json'}, body});
    const j = await r.json();
    $('importResult').textContent = `inserted ${j.inserted}, duplicates ${j.duplicate}, invalid ${j.invalid}`;
    await loadAll();
  } catch (err) { $('importResult').textContent = 'Import failed: ' + err.message; }
});

loadAll();
setInterval(loadAll, 30000);
