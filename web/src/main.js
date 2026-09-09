import {Display, Viewer} from 'three-cad-viewer';
import 'three-cad-viewer/css';
import './style.css';

const LABELS = {
  NEW_FAIL: '新增不满足',
  FIXED: '已修复',
  IMPROVED: '改善',
  REGRESSED: '退化',
  UNCHANGED: '无变化',
  NON_COMPARABLE: '不可比较',
  PASS: '满足',
  FAIL: '不满足',
  BLOCKED: '无法执行',
  REVIEW_REQUIRED: '需复核',
};

const state = {
  run: null,
  selected: null,
  model: 'V2',
  viewer: null,
  display: null,
  viewerReady: false,
  busy: false,
};

const root = document.querySelector('#app');
root.innerHTML = `
  <header>
    <b>CAD Check</b>
    <span>STEP / OCCT 能力验证 MVP</span>
    <i id="sys" class="status" role="status">正在检查运行环境…</i>
  </header>
  <nav class="toolbar">
    <button id="run" class="primary">1. 运行 V1 → V2 校核</button>
    <button id="v1" class="model-button">查看 V1</button>
    <button id="v2" class="model-button selected">查看 V2</button>
    <span id="rid" class="run-id">尚未运行</span>
  </nav>
  <section id="guide" class="guide" aria-label="手测步骤">
    <div class="step active" data-step="run"><b>1</b><span>运行校核</span><small>生成 V1/V2 结果</small></div>
    <div class="step" data-step="model"><b>2</b><span>检查三维</span><small>切换版本、定位对象</small></div>
    <div class="step" data-step="evidence"><b>3</b><span>复核证据</span><small>测量线和 Trace</small></div>
    <div class="step" data-step="save"><b>4</b><span>保存证据</span><small>导出 Evidence PNG</small></div>
  </section>
  <section id="sum" class="summary"></section>
  <main>
    <aside class="panel cases-panel">
      <h3>校核项</h3>
      <p class="hint">先运行校核，再选择案例进入三维复核。</p>
      <div id="cases"><div class="empty">尚未运行</div></div>
    </aside>
    <section class="viewer panel">
      <div class="vh"><span id="vt">真实 STEP 三维视图 · V2</span><b id="measure"></b></div>
      <div id="cad"><div class="viewer-empty">正在加载三维数据…</div></div>
    </section>
    <aside class="detail panel">
      <h3>手测详情</h3>
      <div id="detail">
        <p class="hint">手测顺序：</p>
        <ol class="manual-list">
          <li>运行 V1 → V2 校核</li>
          <li>选择一个新增不满足项</li>
          <li>确认对象、版本和测量线</li>
          <li>打开 Trace 并保存 PNG</li>
        </ol>
      </div>
    </aside>
  </main>
`;

const $ = (selector) => document.querySelector(selector);

async function api(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!response.ok) {
    const detail = payload && typeof payload === 'object' ? payload.detail : payload;
    throw new Error(`${response.status} ${detail || response.statusText}`);
  }
  return payload;
}

function setStatus(message, tone = '') {
  const element = $('#sys');
  element.textContent = message;
  element.className = `status ${tone}`;
}

function setStep(name, stateName) {
  const step = document.querySelector(`[data-step="${name}"]`);
  if (!step) return;
  step.classList.remove('active', 'done', 'error');
  if (stateName) step.classList.add(stateName);
}

function resetSteps() {
  setStep('run', 'active');
  setStep('model', '');
  setStep('evidence', '');
  setStep('save', '');
}

function setBusy(value) {
  state.busy = value;
  $('#run').disabled = value;
  $('#run').textContent = value ? '正在运行…' : '1. 运行 V1 → V2 校核';
}

function ensureViewer() {
  if (state.viewer) return;
  const container = $('#cad');
  container.innerHTML = '';
  state.display = new Display(container, {
    cadWidth: Math.max(700, container.clientWidth || 900),
    height: 620,
    treeWidth: 220,
    theme: 'browser',
    tools: true,
    measureTools: false,
    selectTool: true,
  });
  state.viewer = new Viewer(state.display, {tools: true}, () => {});
}

function setModelButton(model) {
  state.model = model;
  for (const key of ['V1', 'V2']) {
    $(`#v${key.slice(1)}`).classList.toggle('selected', key === model);
  }
  $('#vt').textContent = `真实 STEP 三维视图 · ${model}`;
}

async function renderViewer() {
  ensureViewer();
  setStep('model', 'active');
  const evidenceUrl = state.run && state.selected
    ? `/api/runs/${state.run.run_id}/evidence/${state.selected}/viewer?model=${state.model}`
    : `/api/models/${state.model}/viewer`;
  const payload = await api(evidenceUrl);
  if (!payload?.shapes?.parts?.length) {
    throw new Error('viewer payload 没有可显示的 shape');
  }
  state.viewer.clear?.();
  state.viewer.render(payload.shapes, {
    ambientIntensity: 1,
    directIntensity: 1.1,
    metalness: 0.2,
    roughness: 0.7,
    edgeColor: 0x606975,
    defaultOpacity: 0.85,
    normalLen: 0,
  }, {ortho: true, ticks: 5, control: 'trackball', up: 'Z', collapse: 1});
  state.viewer.presetCamera?.('iso');
  state.viewerReady = true;
  setStep('model', 'done');
  if (state.run && state.selected) setStep('evidence', 'done');
  setStatus(`${state.model} 三维已加载`, 'ok');
}

function renderSummary() {
  const counts = {
    NEW_FAIL: 0,
    FIXED: 0,
    IMPROVED: 0,
    REGRESSED: 0,
    UNCHANGED: 0,
    NON_COMPARABLE: 0,
  };
  for (const item of state.run.regression) counts[item.regression]++;
  $('#sum').innerHTML = Object.entries(counts)
    .map(([key, value]) => `<div><strong>${value}</strong><span>${LABELS[key]}</span></div>`)
    .join('');
}

function renderCaseList() {
  $('#cases').innerHTML = state.run.regression.map((item) => `
    <button class="case ${item.case_id === state.selected ? 'selected' : ''}" data-id="${item.case_id}">
      <span>${item.title}</span><b class="tag-${item.regression}">${LABELS[item.regression]}</b>
    </button>
  `).join('');
  document.querySelectorAll('.case').forEach((button) => {
    button.onclick = () => selectCase(button.dataset.id);
  });
}

function renderDetail(item, definition) {
  $('#detail').innerHTML = `
    <h2>${item.title}</h2>
    <p class="result ${item.regression}"><b>${LABELS[item.regression]}</b></p>
    <dl class="facts">
      <dt>执行器</dt><dd>${definition.executor}</dd>
      <dt>V1</dt><dd>${item.baseline.value ?? '—'} ${item.baseline.unit} · ${LABELS[item.baseline.status]}</dd>
      <dt>V2</dt><dd>${item.candidate.value ?? '—'} ${item.candidate.unit} · ${LABELS[item.candidate.status]}</dd>
      <dt>变化量</dt><dd>${item.delta ?? '—'} ${item.candidate.unit}</dd>
      <dt>规则来源</dt><dd>${definition.source_ref}</dd>
    </dl>
    <div class="detail-actions">
      <button id="trace">查看 Trace</button>
      <button id="shot">保存 Evidence PNG</button>
    </div>
    <pre id="out" aria-live="polite"></pre>
  `;
  $('#measure').textContent = item.candidate.evidence.annotation || '';
  $('#trace').onclick = async () => {
    try {
      const text = await api(`/api/runs/${state.run.run_id}/trace`);
      const lines = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
      $('#out').textContent = lines.split('\n')
        .filter((line) => line.includes(`"case_id": "${item.case_id}"`))
        .join('\n') || lines;
      setStep('evidence', 'done');
      setStatus('Trace 已加载', 'ok');
    } catch (error) {
      $('#out').textContent = error.message;
      setStep('evidence', 'error');
      setStatus(`Trace 失败：${error.message}`, 'error');
    }
  };
  $('#shot').onclick = async () => {
    try {
      if (!state.viewerReady) throw new Error('请先完成三维加载');
      const image = await state.viewer.getImage('evidence');
      const saved = await api(`/api/runs/${state.run.run_id}/evidence/${item.case_id}/screenshot`, {
        method: 'POST',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify({data_url: image.dataUrl}),
      });
      $('#shot').textContent = `已保存 ${saved.bytes} bytes`;
      setStep('save', 'done');
      setStatus('Evidence PNG 已保存', 'ok');
    } catch (error) {
      $('#out').textContent = error.message;
      setStep('save', 'error');
      setStatus(`Evidence 失败：${error.message}`, 'error');
    }
  };
}

async function selectCase(caseId) {
  if (!state.run) return;
  const item = state.run.regression.find((entry) => entry.case_id === caseId);
  const definition = state.run.cases.find((entry) => entry.id === caseId);
  if (!item || !definition) return;
  state.selected = caseId;
  renderCaseList();
  renderDetail(item, definition);
  $('#vt').textContent = `${state.model} · ${item.title}`;
  setStep('evidence', 'active');
  try {
    await renderViewer();
  } catch (error) {
    state.viewerReady = false;
    setStep('model', 'error');
    setStep('evidence', 'error');
    setStatus(`三维加载失败：${error.message}`, 'error');
    $('#out').textContent = error.message;
  }
}

async function runChecks() {
  if (state.busy) return;
  setBusy(true);
  resetSteps();
  state.run = null;
  state.selected = null;
  state.viewerReady = false;
  $('#cases').innerHTML = '<div class="empty">正在运行真实 STEP 校核…</div>';
  $('#detail').innerHTML = '<p class="hint">正在生成结果和证据…</p>';
  setStatus('正在运行 V1 → V2 校核…', 'working');
  try {
    state.run = await api('/api/runs/regression', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({baseline: 'V1', candidate: 'V2'}),
    });
    $('#rid').textContent = `Run ${state.run.run_id}`;
    renderSummary();
    setStep('run', 'done');
    const first = state.run.regression.find((item) => item.regression === 'NEW_FAIL') || state.run.regression[0];
    setStatus(`校核完成：${state.run.regression.length} 项`, 'ok');
    await selectCase(first.case_id);
  } catch (error) {
    setStep('run', 'error');
    setStatus(`校核失败：${error.message}`, 'error');
    $('#cases').innerHTML = `<div class="empty error-text">${error.message}</div>`;
  } finally {
    setBusy(false);
  }
}

async function switchModel(model) {
  setModelButton(model);
  try {
    await renderViewer();
  } catch (error) {
    state.viewerReady = false;
    setStep('model', 'error');
    setStatus(`三维加载失败：${error.message}`, 'error');
  }
}

async function boot() {
  try {
    const readiness = await api('/api/system/readiness');
    const models = await api('/api/models');
    if (!models.V1 || !models.V2) throw new Error('缺少 V1/V2 模型，请先运行 bootstrap');
    setStatus(`运行环境 READY · OCP ${readiness.python_packages['cadquery-ocp']}`, 'ok');
    await renderViewer();
  } catch (error) {
    setStep('model', 'error');
    setStatus(`启动检查失败：${error.message}`, 'error');
    $('#cad').innerHTML = `<div class="viewer-empty error-text">${error.message}</div>`;
  }
}

$('#run').onclick = runChecks;
$('#v1').onclick = () => switchModel('V1');
$('#v2').onclick = () => switchModel('V2');
boot();
