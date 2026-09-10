import {Display, Viewer} from 'three-cad-viewer';
import 'three-cad-viewer/css';
import './style_v3.css';

const LABELS = {
  MEASURED:'已测量', NEW_FAIL:'新增不满足', FIXED:'已修复', IMPROVED:'改善',
  REGRESSED:'退化', UNCHANGED:'无变化', NON_COMPARABLE:'不可比较',
  PASS:'满足', FAIL:'不满足', BLOCKED:'无法执行', REVIEW_REQUIRED:'需复核',
  FORMAL:'正式', PROVISIONAL:'待确认', EXPLORATORY:'探索'
};
const TAB = {MODEL:'MODEL', CHECKS:'CHECKS', REGRESSION:'REGRESSION'};
const state = {
  models:{}, cards:[], model:null, assembly:null, tab:TAB.CHECKS,
  viewer:null, display:null, viewerReady:false, manifest:null, abort:null,
  loadedParts:0, totalParts:0, loadedChunks:0, totalChunks:0, streamRoot:null,
  runs:{check:null, regression:null, explore:null},
  selectedCase:null, selectedOccurrence:null, quickMeasure:false,
  autoShots:new Set(), viewingEvidence:false, overviewModel:null
};
const $ = (s) => document.querySelector(s);
const escapeHtml = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'
}[c]));

async function api(url, options={}) {
  const r = await fetch(url, options);
  if (!r.ok) {
    let d = '';
    try { d = (await r.json()).detail || r.statusText; } catch { d = r.statusText; }
    throw new Error(`${r.status} ${d}`);
  }
  return r.json();
}
function yieldFrame() { return new Promise(resolve => requestAnimationFrame(resolve)); }

$('#app').innerHTML = `
<div class="shell">
  <header class="topbar">
    <div class="brand-block">
      <span class="brand">CAD Check</span>
      <span class="product-subtitle">Engineering Verification</span>
    </div>
    <select id="model" class="model-select" aria-label="模型"></select>
    <button id="load" class="ghost">加载模型</button>
    <span id="model-version" class="version-badge">—</span>
    <button id="run" class="primary">运行校核</button>

    <div class="jobbar" aria-live="polite">
      <div class="progress-track"><div id="progress" class="progress-fill"></div></div>
      <span id="progress-text" class="progress-text">未加载</span>
      <button id="cancel" class="text-btn hidden">取消</button>
    </div>

    <details class="more">
      <summary>更多</summary>
      <div class="more-panel">
        <details class="fold" open>
          <summary>模型与数据</summary>
          <div class="fold-body">
            <div class="row">
              <input id="step-upload" type="file" accept=".stp,.step">
              <button id="upload-step" class="ghost">上传并加载</button>
            </div>
            <div id="upload-status" class="hint">STEP 导入后自动进入模型列表。</div>
            <button id="readiness" class="ghost">查看 Readiness</button>
            <pre id="readiness-out" class="trace hidden"></pre>
          </div>
        </details>
        <details class="fold">
          <summary>证据与诊断</summary>
          <div class="fold-body">
            <button id="trace-btn" class="ghost">查看 Trace</button>
            <button id="shot-btn" class="ghost">保存当前截图</button>
            <pre id="trace-out" class="trace hidden"></pre>
          </div>
        </details>
      </div>
    </details>
  </header>

  <main class="workspace">
    <aside class="panel nav-panel">
      <div class="left-tabs">
        <button class="left-tab" data-tab="${TAB.MODEL}">模型树</button>
        <button class="left-tab active" data-tab="${TAB.CHECKS}">校核结果</button>
        <button class="left-tab" data-tab="${TAB.REGRESSION}">版本变化</button>
      </div>
      <div id="nav-content" class="nav-content">
        <div class="empty">尚未运行校核</div>
      </div>
    </aside>

    <section class="panel viewer-panel">
      <div class="viewer-head">
        <div>
          <strong id="vt">等待加载</strong>
          <span class="muted" id="viewer-meta"></span>
        </div>
        <div class="viewer-tools">
          <button id="overview-btn" class="tool-btn hidden">返回整车</button>
          <button id="quick-measure" class="tool-btn">快速测量</button>
        </div>
      </div>
      <div id="cad" class="cad-host"><div class="empty">选择模型后加载</div></div>
    </section>

    <aside class="panel inspector-panel">
      <div class="panel-head">
        <b id="inspector-title">校核配置</b>
        <span id="detail-tag"></span>
      </div>
      <div id="inspector" class="inspector-body"></div>
    </aside>
  </main>

  <footer class="statusbar">
    <span id="status-model">Model: —</span>
    <span id="status-runtime">Runtime: checking…</span>
    <span id="status-tree">Tree: —</span>
    <span id="status-viewer">Viewer: idle</span>
  </footer>
</div>`;

function setProgress(pct, text, {indeterminate=false, cancellable=false}={}) {
  const bar = $('#progress');
  bar.classList.toggle('indeterminate', indeterminate);
  bar.style.width = indeterminate ? '30%' : `${Math.max(0, Math.min(100, pct))}%`;
  $('#progress-text').textContent = text;
  $('#cancel').classList.toggle('hidden', !cancellable);
}

function setStatus(id, text, tone='') {
  const el = $(id);
  el.textContent = text;
  el.classList.remove('ok','warn','error');
  if (tone) el.classList.add(tone);
}

function ensureViewer() {
  if (state.viewer) return;
  const host = $('#cad');
  host.innerHTML = '';
  state.display = new Display(host, {
    cadWidth: Math.max(700, host.clientWidth || 900),
    height: Math.max(620, host.clientHeight || 620),
    treeWidth: 0,
    theme: 'browser',
    tools: true,
    measureTools: false,
    selectTool: true
  });
  state.viewer = new Viewer(state.display, {tools:true}, () => {});
}

function clearViewer(message='准备加载几何') {
  try { state.viewer?.clear?.(); } catch {}
  state.viewer = null;
  state.display = null;
  state.viewerReady = false;
  state.streamRoot = null;
  $('#cad').innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
  setStatus('#status-viewer', 'Viewer: idle');
}

function viewerRenderOptions() {
  return [
    {ambientIntensity:1, directIntensity:1.1, metalness:.2, roughness:.7,
     edgeColor:0x606975, defaultOpacity:.88, normalLen:0},
    {ortho:true, ticks:5, control:'trackball', up:'Z', collapse:1}
  ];
}

async function loadChunk(chunk, index, signal) {
  const payload = await api(chunk.url, {signal});
  if (!payload?.shapes?.parts?.length) throw new Error(`${chunk.id} 没有可显示几何`);
  ensureViewer();
  const [appearance, view] = viewerRenderOptions();

  if (index === 0 || !state.viewerReady) {
    state.viewer.render(payload.shapes, appearance, view);
    state.streamRoot = payload.shapes;
    state.viewerReady = true;
    state.viewer.presetCamera?.('iso');
    setStatus('#status-viewer', 'Viewer: interactive', 'ok');
  } else {
    let incremental = true;
    try {
      for (const part of payload.shapes.parts) {
        state.viewer.addPart(state.streamRoot.id, part, {skipBounds:true});
      }
      state.viewer.updateBounds?.();
    } catch {
      incremental = false;
    }
    if (!incremental) {
      state.streamRoot.parts.push(...payload.shapes.parts);
      state.viewer.clear?.();
      state.viewer.render(state.streamRoot, appearance, view);
    }
  }

  state.loadedParts += chunk.part_count;
  state.loadedChunks += 1;
  const pct = state.totalParts
    ? Math.round(state.loadedParts / state.totalParts * 100)
    : Math.round(state.loadedChunks / Math.max(1, state.totalChunks) * 100);
  setProgress(pct, `Overview ${state.loadedParts}/${state.totalParts} 件`, {cancellable:true});
  $('#viewer-meta').textContent = `${state.loadedChunks}/${state.totalChunks} 分块`;
  await yieldFrame();
}

async function loadAssembly() {
  if (!state.model) return;
  try {
    state.assembly = await api(`/api/models/${encodeURIComponent(state.model)}/assembly`);
    const s = state.assembly.stats;
    setStatus('#status-tree', `Tree: ${s.occurrence_count} nodes · depth ${s.max_depth}`, 'ok');
    if (state.tab === TAB.MODEL) renderNavigation();
  } catch (error) {
    state.assembly = null;
    setStatus('#status-tree', 'Tree: unavailable', 'error');
    if (state.tab === TAB.MODEL) {
      $('#nav-content').innerHTML = `<div class="panel-message error">${escapeHtml(error.message)}</div>`;
    }
  }
}

async function loadModel() {
  const model = $('#model').value;
  if (!model) return;
  if (state.abort) state.abort.abort();

  state.abort = new AbortController();
  state.model = model;
  state.overviewModel = model;
  state.viewingEvidence = false;
  $('#overview-btn').classList.add('hidden');
  clearViewer();
  $('#vt').textContent = `${model} · 准备中`;
  setProgress(0, '读取模型…', {indeterminate:true, cancellable:true});
  setStatus('#status-model', `Model: ${model}`);
  await loadAssembly();

  try {
    const manifest = await api(`/api/models/${encodeURIComponent(model)}/viewer/manifest?profile=preview`, {signal:state.abort.signal});
    state.manifest = manifest;
    state.loadedParts = 0;
    state.totalParts = manifest.part_count || 0;
    state.loadedChunks = 0;
    state.totalChunks = manifest.chunk_count || 0;
    setProgress(0, `Overview 0/${state.totalParts} 件`, {cancellable:true});
    $('#vt').textContent = `${model} · 渐进加载`;

    for (let i = 0; i < manifest.chunks.length; i++) {
      await loadChunk(manifest.chunks[i], i, state.abort.signal);
    }

    setProgress(100, `已加载 ${state.totalParts} 件`);
    $('#vt').textContent = `${model} · Overview`;
    $('#viewer-meta').textContent = `${manifest.chunk_count} 分块 · ${manifest.profile.name}`;
  } catch (error) {
    if (error.name === 'AbortError') {
      setProgress(0, '已取消');
      $('#vt').textContent = `${model} · 已取消`;
    } else {
      setProgress(0, '加载失败');
      $('#vt').textContent = `${model} · 加载失败`;
      setStatus('#status-viewer', 'Viewer: failed', 'error');
      renderInspectorMessage('模型预览失败', error.message, 'error');
    }
  } finally {
    state.abort = null;
    $('#cancel').classList.add('hidden');
  }
}

function flattenTree(nodes, out=[]) {
  for (const n of nodes || []) {
    out.push(n);
    flattenTree(n.children, out);
  }
  return out;
}

function treeNodeHtml(node, depth=0) {
  const hasChildren = node.children?.length;
  const safeId = escapeHtml(node.occurrence_id);
  const title = escapeHtml(node.name);
  const validClass = node.valid ? '' : ' invalid';
  const row = `<button class="tree-row${validClass}" data-occ="${safeId}" style="--depth:${depth}">
    <span class="tree-caret">${hasChildren ? '▾' : '·'}</span>
    <span class="tree-name">${title}</span>
  </button>`;
  const children = hasChildren ? `<div class="tree-children">${node.children.map(c => treeNodeHtml(c, depth + 1)).join('')}</div>` : '';
  return `<div class="tree-node">${row}${children}</div>`;
}

function renderModelTree() {
  if (!state.assembly) {
    $('#nav-content').innerHTML = '<div class="empty">加载模型后显示装配树</div>';
    return;
  }
  const s = state.assembly.stats;
  $('#nav-content').innerHTML = `
    <div class="nav-summary">
      <b>${escapeHtml(state.assembly.model_id)}</b>
      <span>${s.occurrence_count} 节点 · ${s.leaf_count} 叶件 · 深度 ${s.max_depth}</span>
    </div>
    <div class="tree-scroll">${state.assembly.roots.map(n => treeNodeHtml(n)).join('')}</div>`;
  document.querySelectorAll('.tree-row').forEach(el => {
    el.onclick = () => selectOccurrence(el.dataset.occ);
  });
}

function checkRows() {
  const run = state.runs.check || state.runs.explore;
  const e = run?.execution;
  return e ? [{caseId:e.case_id, title:e.title, outcome:e.status, execution:e, run, kind:'check'}] : [];
}

function regressionRows() {
  const run = state.runs.regression;
  if (!run) return [];
  return (run.regression || []).map(r => {
    const e = (run.candidate || []).find(x => x.case_id === r.case_id) || {};
    return {caseId:r.case_id, title:r.title || e.title || r.case_id, outcome:r.regression || r.outcome, execution:e, regression:r, run, kind:'regression'};
  });
}

function statusClass(status) {
  if (['FAIL','NEW_FAIL','REGRESSED'].includes(status)) return 'bad';
  if (['REVIEW_REQUIRED','BLOCKED','NON_COMPARABLE'].includes(status)) return 'warn';
  if (['PASS','FIXED','IMPROVED'].includes(status)) return 'good';
  return '';
}

function resultRowHtml(row) {
  const e = row.execution || {};
  const authority = e.rule_authority ? `<span class="authority">${escapeHtml(LABELS[e.rule_authority] || e.rule_authority)}</span>` : '';
  return `<button class="result-row ${state.selectedCase === row.caseId ? 'active' : ''}" data-case="${escapeHtml(row.caseId)}" data-kind="${row.kind}">
    <div class="result-main"><span class="result-status ${statusClass(row.outcome)}">${escapeHtml(LABELS[row.outcome] || row.outcome)}</span>${authority}</div>
    <b>${escapeHtml(row.title)}</b>
    <div class="result-meta"><span>${e.value ?? '—'} ${escapeHtml(e.unit || '')}</span><span>${escapeHtml(row.caseId)}</span></div>
  </button>`;
}

function renderChecks() {
  const rows = checkRows();
  $('#nav-content').innerHTML = rows.length ? `<div class="result-list">${rows.map(resultRowHtml).join('')}</div>` : `<div class="empty-stack"><b>尚未运行校核</b><span>右侧选择 Check Card，点击顶部“运行校核”。</span></div>`;
  bindResultRows();
}

function renderRegression() {
  const rows = regressionRows();
  $('#nav-content').innerHTML = rows.length ? `<div class="regression-head"><span>Baseline V1</span><span>→</span><span>Candidate V2</span></div><div class="result-list">${rows.map(resultRowHtml).join('')}</div>` : `<div class="empty-stack"><b>尚未运行版本回归</b><span>点击顶部“运行版本回归”。</span></div>`;
  bindResultRows();
}

function bindResultRows() {
  document.querySelectorAll('.result-row').forEach(el => {
    el.onclick = () => selectResult(el.dataset.case, el.dataset.kind);
  });
}

function renderNavigation() {
  document.querySelectorAll('.left-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === state.tab));
  if (state.tab === TAB.MODEL) renderModelTree();
  else if (state.tab === TAB.REGRESSION) renderRegression();
  else renderChecks();
  updatePrimaryAction();
}

function setTab(tab) {
  state.tab = tab;
  state.selectedCase = null;
  state.selectedOccurrence = null;
  state.quickMeasure = false;
  $('#quick-measure').classList.remove('active');
  renderNavigation();
  renderInspector();
}

function currentSelectedRow() {
  if (!state.selectedCase) return null;
  const rows = state.tab === TAB.REGRESSION ? regressionRows() : checkRows();
  return rows.find(r => r.caseId === state.selectedCase) || null;
}

function selectOccurrence(occurrenceId) {
  if (!state.assembly) return;
  const all = flattenTree(state.assembly.roots);
  state.selectedOccurrence = all.find(n => n.occurrence_id === occurrenceId) || null;
  state.selectedCase = null;
  renderModelTree();
  renderInspector();
  document.querySelectorAll('.tree-row').forEach(el => el.classList.toggle('active', el.dataset.occ === occurrenceId));
}

function selectResult(caseId, kind) {
  state.selectedCase = caseId;
  state.selectedOccurrence = null;
  state.quickMeasure = false;
  $('#quick-measure').classList.remove('active');
  if (kind === 'regression' && state.tab !== TAB.REGRESSION) state.tab = TAB.REGRESSION;
  renderNavigation();
  renderInspector();
}

function renderInspectorMessage(title, body, tone='') {
  $('#inspector-title').textContent = title;
  $('#detail-tag').innerHTML = '';
  $('#inspector').innerHTML = `<div class="panel-message ${tone}">${escapeHtml(body)}</div>`;
}

function ruleThresholdFor(row) {
  const run = row?.run;
  const caseDef = (run?.cases || []).find(c => c.id === row.caseId) || run?.case;
  const rule = caseDef?.rule;
  if (!rule) return null;
  if (rule.threshold != null) return `${rule.operator} ${rule.threshold} ${rule.unit || ''}`;
  if (rule.lower != null || rule.upper != null) return `${rule.lower ?? '—'} ~ ${rule.upper ?? '—'} ${rule.unit || ''}`;
  return null;
}

function renderResultInspector(row) {
  const e = row.execution || {};
  const status = row.outcome || e.status;
  const threshold = ruleThresholdFor(row);
  const authority = e.rule_authority || row.run?.case?.rule?.authority || '—';
  const regression = row.regression;
  const compare = regression ? `<div class="compare-box"><div><span>V1</span><b>${regression.baseline?.value ?? '—'} ${escapeHtml(regression.baseline?.unit || '')}</b></div><div><span>V2</span><b>${regression.candidate?.value ?? '—'} ${escapeHtml(regression.candidate?.unit || '')}</b></div><div><span>Δ</span><b>${regression.delta ?? '—'}</b></div></div>` : '';

  $('#inspector-title').textContent = row.kind === 'regression' ? '版本变化' : '当前校核';
  $('#detail-tag').innerHTML = `<span class="tag ${statusClass(status)}">${escapeHtml(LABELS[status] || status)}</span>`;
  $('#inspector').innerHTML = `
    <div class="metric">${e.value ?? '—'} <small>${escapeHtml(e.unit || '')}</small></div>
    ${compare}
    <dl class="kv">
      <dt>Case</dt><dd>${escapeHtml(row.caseId)}</dd>
      <dt>成熟度</dt><dd>${escapeHtml(LABELS[authority] || authority)}</dd>
      <dt>Executor</dt><dd>${escapeHtml(e.executor || '—')}</dd>
      <dt>阈值</dt><dd>${escapeHtml(threshold || '—')}</dd>
      <dt>Margin</dt><dd>${e.margin ?? '—'}</dd>
      <dt>Evidence</dt><dd>${escapeHtml(e.evidence?.annotation || '—')}</dd>
    </dl>
    <div class="action-stack">
      <button id="view-evidence" class="primary">查看局部 Evidence</button>
      ${row.kind === 'regression' ? `<div class="segmented"><button id="view-v1">看 V1</button><button id="view-v2" class="active">看 V2</button></div>` : ''}
    </div>
    <p class="hint">正式数值来自 OCP/OCCT B-Rep；Viewer 只负责理解和复核。</p>`;

  $('#view-evidence').onclick = () => showEvidence(row, row.kind === 'regression' ? 'V2' : state.model);
  if ($('#view-v1')) $('#view-v1').onclick = () => showEvidence(row, 'V1');
  if ($('#view-v2')) $('#view-v2').onclick = () => showEvidence(row, 'V2');
}

function renderOccurrenceInspector() {
  const n = state.selectedOccurrence;
  if (!n) return;
  $('#inspector-title').textContent = '当前对象';
  $('#detail-tag').innerHTML = `<span class="tag ${n.valid ? 'good' : 'warn'}">${n.valid ? '可用' : '几何异常'}</span>`;
  $('#inspector').innerHTML = `
    <h3 class="object-title">${escapeHtml(n.name)}</h3>
    <dl class="kv">
      <dt>Occurrence</dt><dd class="mono">${escapeHtml(n.occurrence_id)}</dd>
      <dt>Path</dt><dd class="mono">${escapeHtml(n.original_path)}</dd>
      <dt>Geometry Ref</dt><dd class="mono">${escapeHtml(n.geometry_ref?.value || '—')}</dd>
      <dt>Children</dt><dd>${n.children?.length || 0}</dd>
    </dl>
    <p class="hint">装配树独立于 Viewer Mesh；当前节点身份来自 Canonical XCAF Tree。</p>`;
}

function renderCheckConfig() {
  const options = state.cards.map(c => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.title || c.id)}</option>`).join('');
  $('#inspector-title').textContent = '校核配置';
  $('#detail-tag').innerHTML = '<span class="tag">MVP</span>';
  $('#inspector').innerHTML = `
    <label class="field-label" for="check-card">Check Card</label>
    <select id="check-card" class="field-control">${options}</select>
    <div id="card-summary" class="card-summary"></div>
    <p class="hint">第一版沿用现有单 Case API；后续 Check Set 批量执行按 V1.1 合同接入。</p>`;
  const select = $('#check-card');
  const renderCard = () => {
    const card = state.cards.find(c => c.id === select.value);
    if (!card) { $('#card-summary').innerHTML = ''; return; }
    $('#card-summary').innerHTML = `<dl class="kv compact"><dt>Executor</dt><dd>${escapeHtml(card.executor)}</dd><dt>成熟度</dt><dd>${escapeHtml(LABELS[card.rule?.authority] || card.rule?.authority || '—')}</dd><dt>Rule</dt><dd>${escapeHtml(card.rule?.operator || '—')} ${card.rule?.threshold ?? ''} ${escapeHtml(card.rule?.unit || '')}</dd></dl>`;
  };
  select.onchange = renderCard;
  renderCard();
}

async function renderQuickMeasure() {
  $('#inspector-title').textContent = '快速测量';
  $('#detail-tag').innerHTML = '<span class="tag warn">探索</span>';
  $('#inspector').innerHTML = '<div class="empty">正在读取对象…</div>';
  try {
    const parts = await summaryParts();
    const opts = parts.map(p => `<option value="${escapeHtml(p.path)}">${escapeHtml(p.name)} · ${escapeHtml(p.path)}</option>`).join('');
    $('#inspector').innerHTML = `
      <label class="field-label">对象 A</label>
      <select id="measure-a" class="field-control">${opts}</select>
      <label class="field-label">对象 B</label>
      <select id="measure-b" class="field-control">${opts}</select>
      <button id="measure-run" class="primary full">测量最小间隙</button>
      <p class="hint">快速测量为 EXPLORATORY，不自动成为正式 Verification Case。</p>`;
    $('#measure-run').onclick = runQuickMeasure;
  } catch (error) {
    renderInspectorMessage('快速测量', error.message, 'error');
  }
}

function renderInspector() {
  if (state.quickMeasure) { renderQuickMeasure(); return; }
  const row = currentSelectedRow();
  if (row) { renderResultInspector(row); return; }
  if (state.selectedOccurrence) { renderOccurrenceInspector(); return; }
  renderCheckConfig();
}

function updatePrimaryAction() {
  const button = $('#run');
  if (state.tab === TAB.REGRESSION) {
    button.textContent = '运行版本回归';
    button.disabled = false;
  } else {
    button.textContent = '运行校核';
    button.disabled = !state.model;
  }
}

async function runPrimary() {
  if (state.tab === TAB.REGRESSION) return runRegression();
  return runEngineeringCheck();
}

async function runEngineeringCheck() {
  const card = $('#check-card')?.value || state.cards[0]?.id;
  if (!state.model) throw new Error('请先选择模型');
  if (!card) throw new Error('没有可用 Check Card');
  const button = $('#run');
  button.disabled = true;
  setProgress(0, '运行校核…', {indeterminate:true});
  try {
    state.runs.check = await api('/api/runs/check', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model:state.model, card_id:card})});
    state.runs.explore = null;
    state.selectedCase = state.runs.check.execution?.case_id || null;
    state.tab = TAB.CHECKS;
    setProgress(100, '校核完成');
    renderNavigation();
    renderInspector();
  } catch (error) {
    setProgress(0, '校核失败');
    renderInspectorMessage('校核失败', error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

async function runRegression() {
  const button = $('#run');
  button.disabled = true;
  setProgress(0, '运行版本回归…', {indeterminate:true});
  try {
    state.runs.regression = await api('/api/runs/regression', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({baseline:'V1', candidate:'V2'})});
    const first = regressionRows()[0];
    state.selectedCase = first?.caseId || null;
    state.tab = TAB.REGRESSION;
    setProgress(100, '版本回归完成');
    renderNavigation();
    renderInspector();
  } catch (error) {
    setProgress(0, '回归失败');
    renderInspectorMessage('版本回归失败', error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

async function runQuickMeasure() {
  const target = $('#measure-a')?.value;
  const counterpart = $('#measure-b')?.value;
  if (!target || !counterpart) return;
  if (target === counterpart) {
    renderInspectorMessage('快速测量', '对象 A 与对象 B 不能相同。', 'warn');
    state.quickMeasure = true;
    return;
  }
  setProgress(0, '测量中…', {indeterminate:true});
  try {
    const bindings = {bindings:{target:{default:target}, counterpart:{default:counterpart}}};
    state.runs.explore = await api('/api/runs/explore', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model:state.model, target:'target', counterpart:'counterpart', executor:'minimum_clearance', bindings, title:'快速测量'})});
    state.runs.check = null;
    state.quickMeasure = false;
    $('#quick-measure').classList.remove('active');
    state.tab = TAB.CHECKS;
    state.selectedCase = state.runs.explore.execution?.case_id || null;
    setProgress(100, '测量完成');
    renderNavigation();
    renderInspector();
  } catch (error) {
    setProgress(0, '测量失败');
    renderInspectorMessage('快速测量失败', error.message, 'error');
  }
}

async function showEvidence(row, model) {
  if (!row?.run?.run_id || !model) return;
  setProgress(0, '加载局部 Evidence…', {indeterminate:true});
  try {
    const payload = await api(`/api/runs/${row.run.run_id}/evidence/${encodeURIComponent(row.caseId)}/viewer?model=${encodeURIComponent(model)}`);
    clearViewer();
    ensureViewer();
    const [appearance, view] = viewerRenderOptions();
    state.viewer.render(payload.shapes, appearance, view);
    state.viewerReady = true;
    state.viewer.presetCamera?.('iso');
    state.viewingEvidence = true;
    $('#overview-btn').classList.remove('hidden');
    $('#vt').textContent = `${model} · ${row.title}`;
    $('#viewer-meta').textContent = '局部 Evidence';
    setStatus('#status-viewer', 'Viewer: evidence', 'ok');
    setProgress(100, 'Evidence 已加载');
    await autoCaptureEvidence(row);
  } catch (error) {
    setProgress(0, 'Evidence 失败');
    renderInspectorMessage('Evidence 加载失败', error.message, 'error');
  }
}

async function autoCaptureEvidence(row) {
  const e = row.execution || {};
  if (!['FAIL','REVIEW_REQUIRED'].includes(e.status)) return;
  const key = `${row.run.run_id}:${row.caseId}`;
  if (state.autoShots.has(key) || !state.viewerReady) return;
  try {
    const image = await state.viewer.getImage('evidence');
    await api(`/api/runs/${row.run.run_id}/evidence/${encodeURIComponent(row.caseId)}/screenshot`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({data_url:image.dataUrl})});
    state.autoShots.add(key);
  } catch (error) {
    console.warn('Auto evidence screenshot failed:', error);
  }
}

async function restoreOverview() {
  if (!state.overviewModel) return;
  await loadModel();
}

async function summaryParts() {
  if (!state.model) return [];
  const d = await api(`/api/models/${encodeURIComponent(state.model)}/inventory/summary`);
  return d.parts || [];
}

async function uploadStep() {
  const input = $('#step-upload');
  const file = input.files?.[0];
  if (!file) return;
  $('#upload-status').textContent = '导入 STEP…';
  setProgress(0, '导入 STEP…', {indeterminate:true});
  try {
    const form = new FormData();
    form.append('file', file, file.name);
    const result = await api('/api/models/upload', {method:'POST', body:form});
    await refreshModels();
    $('#model').value = result.key;
    state.model = result.key;
    $('#upload-status').textContent = `${result.filename} 已登记`;
    await loadModel();
    renderInspector();
  } catch (error) {
    $('#upload-status').textContent = `导入失败：${error.message}`;
    setProgress(0, '导入失败');
  }
}

async function showReadiness() {
  if (!state.model) return;
  const data = await api(`/api/models/${encodeURIComponent(state.model)}/readiness`);
  const out = $('#readiness-out');
  out.classList.remove('hidden');
  out.textContent = JSON.stringify(data, null, 2);
}

function activeRun() {
  const row = currentSelectedRow();
  return row?.run || state.runs.check || state.runs.regression || state.runs.explore;
}

async function showTrace() {
  const run = activeRun();
  if (!run?.run_id) return;
  const r = await fetch(`/api/runs/${run.run_id}/trace`);
  const out = $('#trace-out');
  out.classList.remove('hidden');
  out.textContent = await r.text();
}

async function saveShot() {
  const row = currentSelectedRow();
  if (!state.viewerReady || !row?.run?.run_id) return;
  const image = await state.viewer.getImage('evidence');
  await api(`/api/runs/${row.run.run_id}/evidence/${encodeURIComponent(row.caseId)}/screenshot`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({data_url:image.dataUrl})});
  setProgress(100, '截图已保存');
}

async function refreshModels() {
  state.models = await api('/api/models');
  const select = $('#model');
  const preferred = state.models.SCANIA ? 'SCANIA' : (state.model && state.models[state.model] ? state.model : Object.keys(state.models)[0]);
  select.innerHTML = Object.entries(state.models).map(([key, model]) => `<option value="${escapeHtml(key)}">${escapeHtml(key)} · ${escapeHtml(model.model_id)}</option>`).join('');
  state.model = preferred || null;
  select.value = preferred || '';
  updateModelMeta();
  select.onchange = async () => {
    state.model = select.value;
    state.assembly = null;
    state.selectedCase = null;
    state.selectedOccurrence = null;
    state.quickMeasure = false;
    state.viewingEvidence = false;
    clearViewer('点击“加载模型”进入 Overview');
    setProgress(0, '未加载');
    $('#vt').textContent = `${state.model} · 等待加载`;
    updateModelMeta();
    await loadAssembly();
    renderNavigation();
    renderInspector();
  };
  if (state.model) await loadAssembly();
}

function updateModelMeta() {
  const m = state.models[state.model];
  $('#model-version').textContent = m?.version || '—';
  setStatus('#status-model', `Model: ${state.model || '—'}`);
}

async function checkRuntime() {
  try {
    const health = await api('/api/health');
    setStatus('#status-runtime', `Runtime: ${health.ok ? 'ready' : 'unknown'}`, health.ok ? 'ok' : 'warn');
  } catch {
    setStatus('#status-runtime', 'Runtime: unavailable', 'error');
  }
}

$('#load').onclick = loadModel;
$('#cancel').onclick = () => state.abort?.abort();
$('#run').onclick = async () => {
  try { await runPrimary(); }
  catch (error) { renderInspectorMessage('操作失败', error.message, 'error'); }
};
$('#quick-measure').onclick = () => {
  state.quickMeasure = !state.quickMeasure;
  $('#quick-measure').classList.toggle('active', state.quickMeasure);
  renderInspector();
};
$('#overview-btn').onclick = restoreOverview;
$('#upload-step').onclick = uploadStep;
$('#readiness').onclick = showReadiness;
$('#trace-btn').onclick = showTrace;
$('#shot-btn').onclick = saveShot;
document.querySelectorAll('.left-tab').forEach(b => b.onclick = () => setTab(b.dataset.tab));

(async () => {
  try {
    await checkRuntime();
    state.cards = await api('/api/check-cards');
    await refreshModels();
    renderNavigation();
    renderInspector();
    if (state.model) {
      $('#vt').textContent = `${state.model} · 等待加载`;
      setProgress(0, '未加载');
    }
  } catch (error) {
    setProgress(0, '初始化失败');
    renderInspectorMessage('初始化失败', error.message, 'error');
  }
})();
