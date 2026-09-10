import './style_v3.css';
import './viewer/viewer.css';
import { BabylonCadViewer } from './viewer/babylon_cad_viewer.js';

const LABELS = {
  MEASURED:'已测量', NEW_FAIL:'新增不满足', FIXED:'已修复', IMPROVED:'改善',
  REGRESSED:'退化', UNCHANGED:'无变化', NON_COMPARABLE:'不可比较',
  PASS:'满足', FAIL:'不满足', BLOCKED:'无法执行', REVIEW_REQUIRED:'需复核',
  FORMAL:'正式', PROVISIONAL:'待确认', EXPLORATORY:'探索',
};
const TAB = {MODEL:'MODEL', CHECKS:'CHECKS', REGRESSION:'REGRESSION'};
const TERMINAL = new Set(['SUCCEEDED','FAILED','CANCELLED','TIMED_OUT']);
const JOB_PHASE = {
  QUEUED:'等待 CAD Worker', STARTING:'CAD Worker 已接收', READING:'读取 STEP / AP242',
  INVENTORY:'构建 Canonical AssemblyTree', TESSELLATING:'生成局部三维', CHECKING:'执行校核',
  FINALIZING:'固化工程证据', DONE:'完成', FAILED:'失败', CANCELLED:'已取消',
  WORKER_RESTARTING:'重启 CAD Worker', WORKER_CRASHED:'CAD Worker 异常',
  CONTROLLER_RECOVERED:'Runtime 已恢复',
};

const state = {
  models:{}, cards:[], model:null, openInfo:null, assembly:null,
  viewer:null, tab:TAB.CHECKS, activeJob:null,
  selectedCase:null, selectedOccurrence:null, lastPick:null,
  quickMeasure:false, sectionEnabled:false,
  checkScope:'SET', checkCardId:'CLR_BAT_BRACKET',
  runs:{check:null, regression:null, explore:null},
  evidenceModel:null, autoShots:new Set(),
  runtimeState:null, workerState:null,
};
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;',
}[char]));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function api(url, options={}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch {}
    throw new Error(`${response.status} ${detail}`);
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response.text();
}

$('#app').innerHTML = `
<div class="shell">
  <header class="topbar">
    <div class="brand-block"><span class="brand">CAD Check</span><span class="product-subtitle">Electron Engineering Verification</span></div>
    <select id="model" class="model-select" aria-label="模型"></select>
    <button id="load" class="ghost">加载模型</button>
    <button id="open-step" class="ghost">打开 STEP…</button>
    <span id="model-version" class="version-badge">—</span>
    <button id="run" class="primary">运行 Check Set</button>
    <div class="jobbar" aria-live="polite">
      <div class="progress-track"><div id="progress" class="progress-fill"></div></div>
      <span id="progress-text" class="progress-text">Runtime 准备中</span>
      <button id="cancel" class="text-btn hidden">取消</button>
    </div>
    <details class="more">
      <summary>更多</summary>
      <div class="more-panel">
        <details class="fold" open><summary>Runtime</summary><div class="fold-body">
          <div id="product-form" class="panel-message">检查 Electron 产品环境…</div>
          <div class="row"><button id="restart-worker" class="ghost">重启 CAD Worker</button><button id="restart-runtime" class="ghost">重启 Runtime</button></div>
          <pre id="runtime-detail" class="trace"></pre>
        </div></details>
        <details class="fold"><summary>模型 Readiness</summary><div class="fold-body"><pre id="readiness-out" class="trace">尚未解析模型</pre></div></details>
        <details class="fold"><summary>Trace</summary><div class="fold-body"><button id="trace-btn" class="ghost">读取当前 Trace</button><pre id="trace-out" class="trace hidden"></pre></div></details>
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
      <div id="nav-content" class="nav-content"><div class="empty">加载模型后开始</div></div>
    </aside>

    <section class="panel viewer-panel">
      <div class="viewer-head">
        <div><strong id="vt">等待模型</strong><span class="muted" id="viewer-meta">Babylon / native OCP</span></div>
        <div class="viewer-tools">
          <button id="show-all" class="tool-btn">全部显示</button>
          <button id="section" class="tool-btn">Z 剖切</button>
          <button id="quick-measure" class="tool-btn">快速测量</button>
        </div>
      </div>
      <div id="cad" class="cad-host"><div class="empty">Electron Viewer 初始化中</div></div>
      <div id="viewer-badge" class="viewer-badge">BABYLON · NATIVE OCP · PROXY/DETAIL</div>
    </section>

    <aside class="panel inspector-panel">
      <div class="panel-head"><b id="inspector-title">校核配置</b><span id="detail-tag"></span></div>
      <div id="inspector" class="inspector-body"></div>
    </aside>
  </main>

  <footer class="statusbar">
    <span id="status-model">Model: —</span>
    <span id="status-runtime">Runtime: —</span>
    <span id="status-worker">Worker: —</span>
    <span id="status-tree">Tree: —</span>
    <span id="status-viewer">Viewer: Babylon</span>
  </footer>
</div>`;

function setStatus(selector, text, tone='') {
  const element = $(selector);
  element.textContent = text;
  element.classList.remove('ok','warn','error');
  if (tone) element.classList.add(tone);
}
function setProgress(text, {indeterminate=false, done=false, cancellable=false, fraction=null}={}) {
  const bar = $('#progress');
  bar.classList.toggle('indeterminate', indeterminate && fraction == null);
  if (fraction != null) bar.style.width = `${Math.max(0, Math.min(100, fraction * 100))}%`;
  else bar.style.width = done ? '100%' : (indeterminate ? '30%' : '0%');
  $('#progress-text').textContent = text;
  $('#cancel').classList.toggle('hidden', !cancellable);
}
function updateJobStatus(job) {
  const fraction = Number.isFinite(job.completed) && Number.isFinite(job.total) && job.total > 0
    ? job.completed / job.total : null;
  const terminal = TERMINAL.has(job.state);
  const phase = JOB_PHASE[job.progress_phase] || job.message || job.state;
  const detail = job.current_case_id ? `${phase} · ${job.current_case_id}` : phase;
  setProgress(detail, {
    indeterminate:!terminal && fraction == null,
    done:job.state === 'SUCCEEDED',
    cancellable:!terminal,
    fraction,
  });
  const tone = ['FAILED','TIMED_OUT'].includes(job.state) ? 'error' : (job.state === 'CANCELLED' ? 'warn' : 'ok');
  setStatus('#status-worker', `Worker: ${job.worker_pid ? `PID ${job.worker_pid}` : job.state}`, tone);
}

async function waitForJob(jobId) {
  state.activeJob = jobId;
  for (;;) {
    const job = await api(`/api/jobs/${jobId}`);
    updateJobStatus(job);
    if (job.state === 'SUCCEEDED') {
      state.activeJob = null;
      return job.result;
    }
    if (TERMINAL.has(job.state)) {
      state.activeJob = null;
      throw new Error(job.error_message || job.message || job.state);
    }
    await sleep(160);
  }
}
async function submitJob(kind, payload={}, timeout_s=null) {
  const body = {kind, payload};
  if (timeout_s != null) body.timeout_s = timeout_s;
  const job = await api('/api/jobs', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body),
  });
  updateJobStatus(job);
  return waitForJob(job.job_id);
}
async function cancelActiveJob() {
  if (!state.activeJob) return;
  const id = state.activeJob;
  try {
    const job = await api(`/api/jobs/${id}`, {method:'DELETE'});
    updateJobStatus(job);
  } finally {
    if (state.activeJob === id) state.activeJob = null;
  }
}

function ensureViewer() {
  if (state.viewer) return state.viewer;
  state.viewer = new BabylonCadViewer($('#cad'), {
    maxResidentDetails:24,
    onPick:(occurrenceId, point, component) => {
      state.lastPick = {occurrenceId, point:point?.asArray?.() || null, component};
      selectOccurrence(occurrenceId, {loadDetail:false}).catch(console.error);
    },
  });
  setStatus('#status-viewer', 'Viewer: Babylon ready', 'ok');
  return state.viewer;
}
function flattenTree(nodes, out=[]) {
  for (const node of nodes || []) {
    out.push(node);
    flattenTree(node.children, out);
  }
  return out;
}
function allNodes() { return flattenTree(state.assembly?.roots || [], []); }
function leafNodes() { return allNodes().filter((node) => !node.children?.length); }
function nodeById(id) { return allNodes().find((node) => node.occurrence_id === id) || null; }

function acceptOpenedModel(result, {preserve=false}={}) {
  state.openInfo = result;
  state.assembly = result.assembly;
  state.model = result.model;
  $('#model').value = state.model;
  const viewer = ensureViewer();
  const summary = viewer.loadOverview(state.assembly);
  const stats = state.assembly.stats;
  setStatus('#status-tree', `Tree: ${stats.occurrence_count} · depth ${stats.max_depth}`, 'ok');
  setStatus('#status-model', `Model: ${state.model}`, 'ok');
  setStatus('#status-viewer', `Viewer: ${summary.occurrences} proxy`, 'ok');
  $('#vt').textContent = `${state.model} · Overview`;
  $('#viewer-meta').textContent = `${stats.leaf_count} leaves · proxy-first · detail budget ${summary.max_resident_details}`;
  $('#readiness-out').textContent = JSON.stringify(result.readiness || {}, null, 2);
  updateModelMeta();
  if (!preserve) {
    state.selectedCase = null;
    state.selectedOccurrence = null;
    state.lastPick = null;
  }
  renderNavigation();
  renderInspector();
}

async function loadModel(key=state.model, {preserve=false, loadSmallDetail=true}={}) {
  if (!key) throw new Error('没有可加载的模型');
  state.model = key;
  state.openInfo = null;
  state.assembly = null;
  state.viewer?.clear();
  $('#vt').textContent = `${key} · 读取中`;
  setStatus('#status-tree', 'Tree: loading…');
  const result = await submitJob('OPEN_MODEL', {model:key}, 900);
  acceptOpenedModel(result, {preserve});

  // Small controlled fixtures are made visually complete immediately.  Large
  // engineering models remain proxy-first: no whole-vehicle detail sweep.
  if (loadSmallDetail && result.leaf_count <= 80) {
    const paths = leafNodes().filter((node) => node.valid).map((node) => node.original_path);
    if (paths.length) {
      try {
        const detail = await submitJob('DETAIL', {
          model:key, paths, deviation:0.35, angular_tolerance:0.35, render_edges:false,
        }, 240);
        state.viewer.loadDetail(detail);
        setStatus('#status-viewer', 'Viewer: controlled detail', 'ok');
        $('#viewer-meta').textContent = `${result.leaf_count} leaves · detail resident`;
      } catch (error) {
        console.warn('Controlled detail load failed; proxy remains usable', error);
      }
    }
  }
  setProgress('模型已就绪', {done:true});
  return result;
}

async function ensureModelForEvidence(modelKey) {
  if (state.model === modelKey && state.assembly && state.openInfo) return state.openInfo;
  return loadModel(modelKey, {preserve:true, loadSmallDetail:true});
}

async function openNativeStep() {
  if (!window.cadDesktop?.isDesktop || !window.cadDesktop?.pickStepFile) {
    throw new Error('产品导入必须从 Electron 原生文件选择器发起。');
  }
  const filePath = await window.cadDesktop.pickStepFile();
  if (!filePath) return;
  const response = await api('/api/desktop/models/register', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:filePath}),
  });
  state.model = response.descriptor.key;
  await refreshModels();
  const result = await waitForJob(response.job.job_id);
  acceptOpenedModel(result);
  setProgress('本地 STEP 已打开', {done:true});
}

function treeNodeHtml(node, depth=0) {
  const children = node.children || [];
  const active = state.selectedOccurrence?.occurrence_id === node.occurrence_id ? 'active' : '';
  return `<div class="tree-node"><button class="tree-row ${node.valid ? '' : 'invalid'} ${active}" data-occ="${escapeHtml(node.occurrence_id)}" style="--depth:${depth}"><span class="tree-caret">${children.length ? '▾' : '·'}</span><span class="tree-name">${escapeHtml(node.name)}</span></button>${children.length ? `<div class="tree-children">${children.map((child) => treeNodeHtml(child, depth + 1)).join('')}</div>` : ''}</div>`;
}
function renderModelTree() {
  if (!state.assembly) {
    $('#nav-content').innerHTML = '<div class="empty">加载模型后显示 Canonical Tree</div>';
    return;
  }
  const stats = state.assembly.stats;
  $('#nav-content').innerHTML = `<div class="nav-summary"><b>${escapeHtml(state.openInfo?.model_id || state.model)}</b><span>${stats.occurrence_count} 节点 · ${stats.parent_count} 父节点 · ${stats.leaf_count} 叶件 · 深度 ${stats.max_depth}</span></div><div class="tree-scroll">${state.assembly.roots.map((node) => treeNodeHtml(node)).join('')}</div>`;
  document.querySelectorAll('.tree-row').forEach((element) => {
    element.onclick = () => selectOccurrence(element.dataset.occ, {loadDetail:false});
    element.ondblclick = () => selectOccurrence(element.dataset.occ, {loadDetail:true});
  });
}

function priority(status) {
  return ({NEW_FAIL:0,REGRESSED:1,FAIL:2,REVIEW_REQUIRED:3,BLOCKED:4,NON_COMPARABLE:5,FIXED:6,IMPROVED:7,PASS:8,UNCHANGED:9,MEASURED:10})[status] ?? 99;
}
function checkRows() {
  const run = state.runs.check || state.runs.explore;
  if (!run) return [];
  const executions = run.executions || (run.execution ? [run.execution] : []);
  return executions.map((execution) => ({
    caseId:execution.case_id, title:execution.title, outcome:execution.status,
    execution, run, kind:'check',
  })).sort((a,b) => priority(a.outcome)-priority(b.outcome));
}
function regressionRows() {
  const run = state.runs.regression;
  if (!run) return [];
  return (run.regression || []).map((regression) => ({
    caseId:regression.case_id, title:regression.title || regression.case_id,
    outcome:regression.regression, execution:regression.candidate,
    regression, run, kind:'regression',
  })).sort((a,b) => priority(a.outcome)-priority(b.outcome));
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
  return `<button class="result-row ${state.selectedCase === row.caseId ? 'active' : ''}" data-case="${escapeHtml(row.caseId)}" data-kind="${row.kind}"><div class="result-main"><span class="result-status ${statusClass(row.outcome)}">${escapeHtml(LABELS[row.outcome] || row.outcome)}</span>${authority}</div><b>${escapeHtml(row.title)}</b><div class="result-meta"><span>${e.value ?? '—'} ${escapeHtml(e.unit || '')}</span><span>${escapeHtml(row.caseId)}</span></div></button>`;
}
function bindResultRows() {
  document.querySelectorAll('.result-row').forEach((element) => {
    element.onclick = () => selectResult(element.dataset.case, element.dataset.kind).catch(showError);
  });
}
function renderChecks() {
  const rows = checkRows();
  $('#nav-content').innerHTML = rows.length
    ? `<div class="result-list">${rows.map(resultRowHtml).join('')}</div>`
    : '<div class="empty-stack"><b>尚未运行校核</b><span>默认执行 MVP Coverage Check Set · 18 Cases。</span></div>';
  bindResultRows();
}
function renderRegression() {
  const rows = regressionRows();
  $('#nav-content').innerHTML = rows.length
    ? `<div class="regression-head"><span>Baseline V1</span><span>→</span><span>Candidate V2</span></div><div class="result-list">${rows.map(resultRowHtml).join('')}</div>`
    : '<div class="empty-stack"><b>尚未运行版本回归</b><span>严格比较同一 FORMAL Case/Method/Binding 合同。</span></div>';
  bindResultRows();
}
function renderNavigation() {
  document.querySelectorAll('.left-tab').forEach((button) => button.classList.toggle('active', button.dataset.tab === state.tab));
  if (state.tab === TAB.MODEL) renderModelTree();
  else if (state.tab === TAB.REGRESSION) renderRegression();
  else renderChecks();
  updatePrimaryAction();
}
function setTab(tab) {
  state.tab = tab;
  state.selectedCase = null;
  state.quickMeasure = false;
  $('#quick-measure').classList.remove('active');
  renderNavigation();
  renderInspector();
}

async function selectOccurrence(occurrenceId, {loadDetail=false}={}) {
  const node = nodeById(occurrenceId);
  if (!node) return;
  state.selectedOccurrence = node;
  state.selectedCase = null;
  state.viewer?.setSelection([occurrenceId]);
  state.viewer?.focusObjects([occurrenceId]);
  if (state.tab === TAB.MODEL) renderModelTree();
  renderInspector();
  if (loadDetail && !node.children?.length && node.valid) await loadOccurrenceDetail(node);
}
async function loadOccurrenceDetail(node=state.selectedOccurrence) {
  if (!node || node.children?.length || !node.valid) return;
  const detail = await submitJob('DETAIL', {
    model:state.model, paths:[node.original_path], deviation:0.2,
    angular_tolerance:0.25, render_edges:true,
  }, 180);
  state.viewer.loadDetail(detail);
  state.viewer.setSelection([node.occurrence_id]);
  state.viewer.focusObjects([node.occurrence_id]);
  setProgress('局部 Detail 已加载', {done:true});
}

function currentSelectedRow() {
  if (!state.selectedCase) return null;
  const rows = state.tab === TAB.REGRESSION ? regressionRows() : checkRows();
  return rows.find((row) => row.caseId === state.selectedCase) || null;
}
function findCaseDefinition(row) {
  return (row.run?.cases || []).find((item) => item.id === row.caseId) || row.run?.case || null;
}
function thresholdText(row) {
  const rule = findCaseDefinition(row)?.rule;
  if (!rule) return '—';
  if (rule.threshold != null) return `${rule.operator} ${rule.threshold} ${rule.unit || ''}`;
  return `${rule.lower ?? '—'} ~ ${rule.upper ?? '—'} ${rule.unit || ''}`;
}
function renderResultInspector(row) {
  const e = row.execution || {};
  const status = row.outcome || e.status;
  const reg = row.regression;
  const compare = reg ? `<div class="compare-box"><div><span>V1</span><b>${reg.baseline?.value ?? '—'} ${escapeHtml(reg.baseline?.unit || '')}</b></div><div><span>V2</span><b>${reg.candidate?.value ?? '—'} ${escapeHtml(reg.candidate?.unit || '')}</b></div><div><span>Δ</span><b>${reg.delta ?? '—'}</b></div></div>` : '';
  $('#inspector-title').textContent = row.kind === 'regression' ? '版本变化' : '当前校核';
  $('#detail-tag').innerHTML = `<span class="tag ${statusClass(status)}">${escapeHtml(LABELS[status] || status)}</span>`;
  $('#inspector').innerHTML = `<div class="metric">${e.value ?? '—'} <small>${escapeHtml(e.unit || '')}</small></div>${compare}<dl class="kv"><dt>Case</dt><dd>${escapeHtml(row.caseId)}</dd><dt>成熟度</dt><dd>${escapeHtml(LABELS[e.rule_authority] || e.rule_authority || '—')}</dd><dt>Executor</dt><dd>${escapeHtml(e.executor || '—')}</dd><dt>阈值</dt><dd>${escapeHtml(thresholdText(row))}</dd><dt>Margin</dt><dd>${e.margin ?? '—'}</dd><dt>Method</dt><dd>${escapeHtml(e.evidence?.measurement_method || '—')}</dd><dt>Evidence</dt><dd>${escapeHtml(e.evidence?.annotation || '—')}</dd></dl><div class="action-stack"><button id="view-evidence" class="primary">重新定位 Evidence</button><button id="replay-evidence" class="ghost">Replay 已保存状态</button>${row.kind === 'regression' ? '<div class="segmented"><button id="view-v1">看 V1</button><button id="view-v2" class="active">看 V2</button></div>' : ''}</div>${reg?.non_comparable_reason ? `<p class="panel-message warn">${escapeHtml(reg.non_comparable_reason)}</p>` : ''}<p class="hint">正式数值来自 Python/OCP B-Rep；Babylon 仅负责理解和复核。</p>`;
  $('#view-evidence').onclick = () => showEvidence(row, row.kind === 'regression' ? (state.evidenceModel || 'V2') : state.model, {persist:true}).catch(showError);
  $('#replay-evidence').onclick = () => replayEvidence(row).catch(showError);
  if ($('#view-v1')) $('#view-v1').onclick = () => showEvidence(row, 'V1', {persist:false}).catch(showError);
  if ($('#view-v2')) $('#view-v2').onclick = () => showEvidence(row, 'V2', {persist:false}).catch(showError);
}
function renderOccurrenceInspector() {
  const node = state.selectedOccurrence;
  const face = state.lastPick?.occurrenceId === node.occurrence_id ? state.lastPick?.component?.face_id : null;
  $('#inspector-title').textContent = '当前对象';
  $('#detail-tag').innerHTML = `<span class="tag ${node.valid ? 'good' : 'warn'}">${node.valid ? '可用' : '几何异常'}</span>`;
  $('#inspector').innerHTML = `<h3 class="object-title">${escapeHtml(node.name)}</h3><dl class="kv"><dt>Occurrence</dt><dd class="mono">${escapeHtml(node.occurrence_id)}</dd><dt>Path</dt><dd class="mono">${escapeHtml(node.original_path)}</dd><dt>Face Pick</dt><dd>${face != null ? `triangle-face ${face} → occurrence` : '—'}</dd><dt>Children</dt><dd>${node.children?.length || 0}</dd></dl><div class="action-stack">${!node.children?.length ? '<button id="load-detail" class="primary">加载局部精细几何</button>' : ''}<div class="segmented"><button id="isolate-node">隔离</button><button id="hide-node">隐藏</button></div></div><p class="hint">Canonical Tree/occurrence identity 独立于 Viewer Mesh；Face Pick 只作为当前显示几何的局部拾取信息。</p>`;
  if ($('#load-detail')) $('#load-detail').onclick = () => loadOccurrenceDetail(node).catch(showError);
  $('#isolate-node').onclick = () => { state.viewer.isolate([node.occurrence_id]); state.viewer.focusObjects([node.occurrence_id]); };
  $('#hide-node').onclick = () => state.viewer.setVisibility([node.occurrence_id], false);
}
function renderCheckConfig() {
  $('#inspector-title').textContent = '校核配置';
  $('#detail-tag').innerHTML = '<span class="tag">MVP</span>';
  const options = state.cards.map((card) => `<option value="${escapeHtml(card.id)}" ${card.id === state.checkCardId ? 'selected' : ''}>${escapeHtml(card.title || card.id)}</option>`).join('');
  $('#inspector').innerHTML = `<label class="field-label">执行范围</label><select id="check-scope" class="field-control"><option value="SET" ${state.checkScope === 'SET' ? 'selected' : ''}>MVP Coverage Set · 18 Cases</option><option value="SINGLE" ${state.checkScope === 'SINGLE' ? 'selected' : ''}>Golden / 单 Case</option></select><div id="single-card" class="${state.checkScope === 'SINGLE' ? '' : 'hidden'}"><label class="field-label">Check Card</label><select id="check-card" class="field-control">${options}</select></div><div class="card-summary"><b>3 Executors</b><p class="hint">Minimum Clearance / Directional Distance / Angle。Coverage 验证复用，不等同于 18 个 Golden。</p></div>`;
  $('#check-scope').onchange = (event) => { state.checkScope = event.target.value; renderCheckConfig(); updatePrimaryAction(); };
  if ($('#check-card')) $('#check-card').onchange = (event) => { state.checkCardId = event.target.value; };
}
function renderQuickMeasure() {
  $('#inspector-title').textContent = '快速测量';
  $('#detail-tag').innerHTML = '<span class="tag warn">探索</span>';
  const leaves = leafNodes().filter((node) => node.valid);
  const options = leaves.map((node) => `<option value="${escapeHtml(node.original_path)}">${escapeHtml(node.name)} · ${escapeHtml(node.original_path)}</option>`).join('');
  $('#inspector').innerHTML = `<label class="field-label">对象 A</label><select id="measure-a" class="field-control">${options}</select><label class="field-label">对象 B</label><select id="measure-b" class="field-control">${options}</select><button id="measure-run" class="primary full">最小距离</button><p class="hint">EXPLORATORY，只生成临时测量，不进入正式 Regression。</p>`;
  if ($('#measure-run')) $('#measure-run').onclick = () => runQuickMeasure().catch(showError);
}
function renderInspectorMessage(title, body, tone='') {
  $('#inspector-title').textContent = title;
  $('#detail-tag').innerHTML = '';
  $('#inspector').innerHTML = `<div class="panel-message ${tone}">${escapeHtml(body)}</div>`;
}
function renderInspector() {
  const row = currentSelectedRow();
  if (row) return renderResultInspector(row);
  if (state.quickMeasure) return renderQuickMeasure();
  if (state.selectedOccurrence) return renderOccurrenceInspector();
  return renderCheckConfig();
}
function showError(error) {
  console.error(error);
  renderInspectorMessage('操作失败', error?.message || String(error), 'error');
}

async function selectResult(caseId, kind) {
  state.selectedCase = caseId;
  state.selectedOccurrence = null;
  state.quickMeasure = false;
  $('#quick-measure').classList.remove('active');
  state.tab = kind === 'regression' ? TAB.REGRESSION : TAB.CHECKS;
  renderNavigation();
  renderInspector();
  const row = currentSelectedRow();
  if (!row || ['BLOCKED','NON_COMPARABLE'].includes(row.outcome)) return;
  const model = row.kind === 'regression' ? 'V2' : state.model;
  await showEvidence(row, model, {
    persist:['FAIL','REVIEW_REQUIRED','NEW_FAIL','REGRESSED'].includes(row.outcome),
  });
}

async function runEngineeringCheck() {
  if (!state.model || !state.assembly) throw new Error('请先加载模型');
  let result;
  if (state.checkScope === 'SINGLE') {
    const cardId = state.checkCardId || state.cards[0]?.id;
    if (!cardId) throw new Error('没有可用 Check Card');
    result = await submitJob('CHECK', {model:state.model, card_id:cardId}, 300);
  } else {
    result = await submitJob('CHECK_SET', {model:state.model}, 900);
  }
  state.runs.check = result;
  state.runs.explore = null;
  state.tab = TAB.CHECKS;
  const first = checkRows()[0];
  state.selectedCase = first?.caseId || null;
  renderNavigation();
  renderInspector();
  if (first && first.outcome !== 'BLOCKED') await selectResult(first.caseId, 'check');
  return result;
}
async function runRegression() {
  const result = await submitJob('REGRESSION', {baseline:'V1', candidate:'V2'}, 1200);
  state.runs.regression = result;
  state.tab = TAB.REGRESSION;
  const first = regressionRows()[0];
  state.selectedCase = first?.caseId || null;
  renderNavigation();
  renderInspector();
  if (first && !['NON_COMPARABLE','BLOCKED'].includes(first.outcome)) await selectResult(first.caseId, 'regression');
  return result;
}
async function runQuickMeasure() {
  const target = $('#measure-a')?.value;
  const counterpart = $('#measure-b')?.value;
  if (!target || !counterpart) throw new Error('请选择两个对象');
  if (target === counterpart) throw new Error('对象 A 与对象 B 不能相同');
  const bindings = {bindings:{target:{default:target},counterpart:{default:counterpart}}};
  const result = await submitJob('EXPLORE', {
    model:state.model, target:'target', counterpart:'counterpart', executor:'minimum_clearance',
    bindings, title:'快速测量',
  }, 300);
  state.runs.explore = result;
  state.runs.check = null;
  state.quickMeasure = false;
  $('#quick-measure').classList.remove('active');
  state.tab = TAB.CHECKS;
  state.selectedCase = result.execution?.case_id || null;
  renderNavigation();
  renderInspector();
  const row = currentSelectedRow();
  if (row) await showEvidence(row, state.model, {persist:false});
  return result;
}

function rowExecutionForModel(row, modelKey) {
  if (row.kind !== 'regression') return row.execution;
  if (modelKey === 'V1') return row.regression?.baseline;
  return row.regression?.candidate;
}
async function showEvidence(row, modelKey, {persist=false}={}) {
  if (!row?.run?.run_id || !modelKey) return;
  await ensureModelForEvidence(modelKey);
  const result = await submitJob('EVIDENCE_DETAIL', {
    model:modelKey, run_id:row.run.run_id, case_id:row.caseId,
  }, 300);
  state.evidenceModel = modelKey;
  const execution = result.execution || rowExecutionForModel(row, modelKey) || row.execution;
  const viewer = ensureViewer();
  viewer.loadDetail(result.detail, {replace:true});
  const ids = execution.evidence?.focus_occurrence_ids || [];
  viewer.setSelection(ids);
  viewer.showEvidenceGeometry(execution);
  viewer.focusObjects(ids);
  $('#vt').textContent = `${modelKey} · ${row.title}`;
  $('#viewer-meta').textContent = 'Evidence Detail · Babylon / OCP';
  if (persist && ['FAIL','REVIEW_REQUIRED'].includes(execution.status)) {
    await sleep(80);
    await persistEvidence(row, execution);
  }
  setProgress('Evidence 已定位', {done:true});
  return execution;
}
async function persistEvidence(row, execution) {
  const key = `${row.run.run_id}:${row.caseId}:${execution.model_version}`;
  if (state.autoShots.has(key)) return;
  const data_url = state.viewer.captureView();
  const viewState = {
    ...state.viewer.getViewState(),
    model_key:state.evidenceModel || state.model,
    model_sha:execution.evidence?.model_sha,
    import_schema_version:execution.evidence?.import_schema_version,
    focus_occurrence_ids:execution.evidence?.focus_occurrence_ids || [],
    annotation:execution.evidence?.annotation,
    evidence_id:execution.evidence?.evidence_id,
  };
  await Promise.all([
    api(`/api/runs/${row.run.run_id}/evidence/${encodeURIComponent(row.caseId)}/screenshot`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({data_url}),
    }),
    api(`/api/runs/${row.run.run_id}/evidence/${encodeURIComponent(row.caseId)}/view-state`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({state:viewState}),
    }),
  ]);
  state.autoShots.add(key);
}
async function replayEvidence(row) {
  const record = await api(`/api/runs/${row.run.run_id}/evidence/${encodeURIComponent(row.caseId)}/replay`);
  const saved = record.view_state;
  if (!saved) return showReplayFallback(record, '没有可重建的三维 View State；保留结构化结果/截图。');
  const modelKey = saved.model_key;
  if (!modelKey || !state.models[modelKey]) return showReplayFallback(record, '原模型版本不可用，禁止按名称猜测对象。');
  await ensureModelForEvidence(modelKey);
  if (saved.model_sha && state.openInfo?.model_sha !== saved.model_sha) {
    return showReplayFallback(record, 'Model SHA 已变化，禁止把旧 Evidence 绑定到新几何。');
  }
  if (saved.import_schema_version && state.assembly?.import_schema_version !== saved.import_schema_version) {
    return showReplayFallback(record, 'Import Schema 不兼容，禁止猜测 occurrence identity。');
  }
  const available = new Set(allNodes().map((node) => node.occurrence_id));
  const required = saved.focus_occurrence_ids || [];
  if (required.some((id) => !available.has(id))) {
    return showReplayFallback(record, 'Occurrence Identity 不兼容，已降级为记录/截图查看。');
  }
  await showEvidence(row, modelKey, {persist:false});
  state.viewer.applyViewState(saved);
  setProgress('Replay 已恢复', {done:true});
  return true;
}
function showReplayFallback(record, message) {
  $('#inspector-title').textContent = 'Replay 降级查看';
  $('#detail-tag').innerHTML = '<span class="tag warn">不可重建</span>';
  const image = record.screenshot_url ? `<img class="evidence-shot" src="${escapeHtml(record.screenshot_url)}" alt="Evidence screenshot">` : '';
  $('#inspector').innerHTML = `<div class="panel-message warn">${escapeHtml(message)}</div>${image}<pre class="trace">${escapeHtml(JSON.stringify(record.result, null, 2))}</pre>`;
  return false;
}

function updatePrimaryAction() {
  const button = $('#run');
  if (state.tab === TAB.REGRESSION) {
    button.textContent = '运行版本回归';
    button.disabled = false;
  } else {
    button.textContent = state.checkScope === 'SINGLE' ? '运行单 Case' : '运行 Check Set';
    button.disabled = !state.model || !state.assembly;
  }
}
async function runPrimary() {
  return state.tab === TAB.REGRESSION ? runRegression() : runEngineeringCheck();
}

async function refreshModels() {
  state.models = await api('/api/desktop/models');
  const select = $('#model');
  const keys = Object.keys(state.models);
  if (!state.model || !state.models[state.model]) state.model = state.models.V2 ? 'V2' : keys[0] || null;
  select.innerHTML = keys.map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(key)} · ${escapeHtml(state.models[key].model_id || '')}</option>`).join('');
  select.value = state.model || '';
  select.onchange = () => {
    state.model = select.value;
    state.assembly = null;
    state.openInfo = null;
    state.selectedCase = null;
    state.selectedOccurrence = null;
    state.viewer?.clear();
    $('#vt').textContent = `${state.model} · 未加载`;
    setStatus('#status-tree', 'Tree: —');
    updateModelMeta();
    renderNavigation();
    renderInspector();
  };
  updateModelMeta();
}
function updateModelMeta() {
  const descriptor = state.models[state.model];
  $('#model-version').textContent = descriptor?.version || '—';
  setStatus('#status-model', `Model: ${state.model || '—'}`);
}

async function checkRuntimeAndWorker() {
  const desktop = window.cadDesktop;
  if (desktop?.isDesktop) {
    const runtime = await desktop.runtimeStatus();
    state.runtimeState = runtime;
    $('#product-form').textContent = `Electron Desktop · ${desktop.platform} · Runtime PID ${runtime.pid || '—'}`;
    $('#product-form').classList.add('ok');
    setStatus('#status-runtime', `Runtime: ${runtime.state}`, runtime.state === 'RUNNING' ? 'ok' : 'error');
  } else {
    $('#product-form').textContent = 'DEBUG HARNESS：不是 Electron 产品环境，不能作为 MVP 验收。';
    $('#product-form').classList.add('warn');
    setStatus('#status-runtime', 'Runtime: browser debug', 'warn');
  }
  const worker = await api('/api/desktop/worker');
  state.workerState = worker;
  const tone = worker.state === 'RUNNING' ? 'ok' : (worker.state === 'UNRESPONSIVE' ? 'error' : 'warn');
  setStatus('#status-worker', `Worker: ${worker.state}${worker.pid ? ` · ${worker.pid}` : ''}`, tone);
  $('#runtime-detail').textContent = JSON.stringify({runtime:state.runtimeState,worker}, null, 2);
}
async function restartWorker() {
  const result = await api('/api/desktop/worker/restart', {method:'POST'});
  setStatus('#status-worker', `Worker: ${result.state} · ${result.pid || '—'}`, 'ok');
  setProgress('CAD Worker 已重启', {done:true});
  return result;
}
async function restartRuntime() {
  if (!window.cadDesktop?.restartRuntime) throw new Error('仅 Electron 可重启 Runtime');
  setProgress('重启 Runtime…', {indeterminate:true});
  return window.cadDesktop.restartRuntime();
}
async function showTrace() {
  const row = currentSelectedRow();
  const run = row?.run || state.runs.check || state.runs.regression || state.runs.explore;
  if (!run?.run_id) throw new Error('当前没有 Run');
  const output = $('#trace-out');
  output.classList.remove('hidden');
  output.textContent = await api(`/api/runs/${run.run_id}/trace`);
}

async function runElectronE2E() {
  if (!window.cadDesktop?.isE2E) return;
  const report = {ok:false, stages:[], viewer:null};
  const stage = (name, data={}) => report.stages.push({name, ...data});
  try {
    if (!window.cadDesktop.isDesktop) throw new Error('E2E did not start inside Electron');
    stage('electron', {platform:window.cadDesktop.platform});

    await loadModel('V2');
    if (state.openInfo?.leaf_count !== 12) throw new Error(`controlled V2 leaf count=${state.openInfo?.leaf_count}`);
    if (state.assembly?.import_schema_version !== 'xcaf-occurrence-v1') throw new Error('canonical import schema missing');
    stage('open-model', {leaf_count:state.openInfo.leaf_count, tree:state.assembly.stats});

    state.checkScope = 'SINGLE';
    state.checkCardId = 'CLR_BAT_BRACKET';
    const check = await submitJob('CHECK', {model:'V2', card_id:'CLR_BAT_BRACKET'}, 120);
    if (check.execution?.status !== 'FAIL' || Math.abs(check.execution?.value - 8.0) > 0.001) {
      throw new Error(`golden check mismatch: ${JSON.stringify(check.execution)}`);
    }
    state.runs.check = check;
    state.runs.explore = null;
    state.tab = TAB.CHECKS;
    state.selectedCase = 'CLR_BAT_BRACKET';
    const row = checkRows().find((item) => item.caseId === 'CLR_BAT_BRACKET');
    await showEvidence(row, 'V2', {persist:true});
    stage('fail-evidence', {run_id:check.run_id,evidence_id:check.execution.evidence?.evidence_id});

    const replayRecord = await api(`/api/runs/${check.run_id}/evidence/CLR_BAT_BRACKET/replay`);
    if (!replayRecord.view_state || !replayRecord.screenshot_url) throw new Error('Evidence view state/screenshot missing');
    const replayed = await replayEvidence(row);
    if (!replayed) throw new Error('Replay fell back unexpectedly');
    stage('replay', {model_sha:replayRecord.view_state.model_sha});

    const regression = await submitJob('REGRESSION', {
      baseline:'V1', candidate:'V2', case_ids:['CLR_BAT_BRACKET'],
    }, 180);
    const golden = regression.regression?.find((item) => item.case_id === 'CLR_BAT_BRACKET');
    if (!golden || golden.regression !== 'NEW_FAIL' || golden.baseline.value !== 12.0 || golden.candidate.value !== 8.0) {
      throw new Error(`regression mismatch: ${JSON.stringify(golden)}`);
    }
    stage('regression', {status:golden.regression,delta:golden.delta});

    const ids = check.execution.evidence?.focus_occurrence_ids || [];
    if (ids.length !== 2 || ids.some((id) => !state.viewer.hasOccurrence(id))) throw new Error('viewer occurrence mapping missing');
    state.viewer.setSelection(ids);
    state.viewer.isolate(ids);
    state.viewer.showAll();
    report.viewer = state.viewer.getStats();
    stage('viewer', report.viewer);

    const before = await api('/api/desktop/worker');
    const restarted = await restartWorker();
    const ping = await submitJob('PING', {}, 15);
    if (!ping.ok || !restarted.pid) throw new Error('worker restart/ping failed');
    stage('worker-restart', {before_pid:before.pid,after_pid:restarted.pid,ping_pid:ping.worker_pid});

    report.ok = true;
  } catch (error) {
    report.error = error?.stack || error?.message || String(error);
  }
  await window.cadDesktop.reportE2E(report);
}

$('#load').onclick = () => loadModel().catch(showError);
$('#open-step').onclick = () => openNativeStep().catch(showError);
$('#cancel').onclick = () => cancelActiveJob().catch(showError);
$('#run').onclick = () => runPrimary().catch(showError);
$('#quick-measure').onclick = () => {
  state.quickMeasure = !state.quickMeasure;
  $('#quick-measure').classList.toggle('active', state.quickMeasure);
  state.selectedCase = null;
  renderInspector();
};
$('#show-all').onclick = () => { state.viewer?.showAll(); state.viewer?.setSelection([]); };
$('#section').onclick = () => {
  state.sectionEnabled = !state.sectionEnabled;
  $('#section').classList.toggle('active', state.sectionEnabled);
  const node = state.selectedOccurrence;
  const z = node?.bbox?.length === 6 ? (node.bbox[2] + node.bbox[5]) / 2 : 0;
  state.viewer?.setSectionPlane(state.sectionEnabled ? {normal:[0,0,1],point:[0,0,z]} : null);
};
$('#restart-worker').onclick = () => restartWorker().catch(showError);
$('#restart-runtime').onclick = () => restartRuntime().catch(showError);
$('#trace-btn').onclick = () => showTrace().catch(showError);
document.querySelectorAll('.left-tab').forEach((button) => button.onclick = () => setTab(button.dataset.tab));

if (window.cadDesktop?.onRuntimeState) {
  window.cadDesktop.onRuntimeState((runtime) => {
    state.runtimeState = runtime;
    setStatus('#status-runtime', `Runtime: ${runtime.state}`, runtime.state === 'RUNNING' ? 'ok' : (runtime.state === 'FAILED' ? 'error' : 'warn'));
  });
}

(async () => {
  try {
    if (!window.cadDesktop?.isDesktop) {
      throw new Error('CAD Check 产品入口必须是 Electron Desktop；浏览器仅允许单独的开发 Harness。');
    }
    ensureViewer();
    await checkRuntimeAndWorker();
    state.cards = await api('/api/check-cards');
    state.checkCardId = state.cards.some((card) => card.id === 'CLR_BAT_BRACKET') ? 'CLR_BAT_BRACKET' : state.cards[0]?.id || null;
    await refreshModels();
    renderNavigation();
    renderInspector();
    setProgress('就绪', {done:true});
    await runElectronE2E();
  } catch (error) {
    setProgress('初始化失败');
    showError(error);
    if (window.cadDesktop?.isE2E) {
      await window.cadDesktop.reportE2E({ok:false,stage:'renderer-init',error:error?.stack || error?.message || String(error)});
    }
  }
})();
