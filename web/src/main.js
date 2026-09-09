import {Display, Viewer} from 'three-cad-viewer';
import 'three-cad-viewer/css';
import './style.css';

const LABELS = {
  MEASURED: '已测量',
  NEW_FAIL: '新增不满足',
  FIXED: '已修复',
  IMPROVED: '改善',
  REGRESSED: '退化',
  UNCHANGED: '无变化',
  NON_COMPARABLE: '不可比较',
  PASS: '满足',
  FAIL: '不满足',
  BLOCKED: '无法执行',
  REVIEW_REQUIRED: '需工程复核',
};

const MODES = {
  EXPLORE_MEASURE: {
    label: '快速测量',
    hint: '选对象、测几何，只输出测量证据，不做工程判定。',
  },
  ENGINEERING_CHECK: {
    label: '工程校验',
    hint: '选择版本化 Check Card，按规则输出结果和证据。',
  },
  REGRESSION_COMPARE: {
    label: '版本回归',
    hint: '复用同一组校验，比较 V1/V2 的风险变化。',
  },
};

const state = {
  mode: 'REGRESSION_COMPARE',
  run: null,
  selected: null,
  model: 'V2',
  models: {},
  cards: [],
  inventory: {},
  viewer: null,
  display: null,
  viewerReady: false,
  busy: false,
};

const root = document.querySelector('#app');
root.innerHTML = `
  <header>
    <b>CAD Check</b>
    <span>STEP / OCCT 三种校验模式 MVP</span>
    <i id="sys" class="status" role="status">正在检查运行环境…</i>
  </header>
  <nav class="toolbar">
    <div id="mode-tabs" class="mode-tabs" aria-label="校验模式">
      ${Object.entries(MODES).map(([id, item]) => `
        <button class="mode-tab" data-mode="${id}">${item.label}</button>
      `).join('')}
    </div>
    <button id="run" class="primary">运行版本回归</button>
    <button id="v1" class="model-button">查看 V1</button>
    <button id="v2" class="model-button selected">查看 V2</button>
    <span id="rid" class="run-id">尚未运行</span>
  </nav>
  <section id="mode-config" class="mode-config"></section>
  <section id="guide" class="guide" aria-label="手测步骤">
    <div class="step active" data-step="run"><b>1</b><span>运行校验</span><small>生成当前模式结果</small></div>
    <div class="step" data-step="model"><b>2</b><span>检查三维</span><small>定位对象和测量位置</small></div>
    <div class="step" data-step="evidence"><b>3</b><span>复核证据</span><small>测量线、数值和 Trace</small></div>
    <div class="step" data-step="save"><b>4</b><span>保存证据</span><small>导出 Evidence PNG</small></div>
  </section>
  <section id="sum" class="summary"></section>
  <main>
    <aside class="panel cases-panel">
      <h3>校验结果</h3>
      <p id="mode-hint" class="hint">先选择模式并运行。</p>
      <div id="cases"><div class="empty">尚未运行</div></div>
    </aside>
    <section class="viewer panel">
      <div class="vh"><span id="vt">真实 STEP 三维视图 · V2</span><b id="measure"></b></div>
      <div id="cad"><div class="viewer-empty">正在加载三维数据…</div></div>
    </section>
    <aside class="detail panel">
      <h3>运行详情</h3>
      <div id="detail">
        <p class="hint">手测顺序：</p>
        <ol class="manual-list">
          <li>选择一种校验模式</li>
          <li>运行校验并选择结果</li>
          <li>确认对象、测量线和规则来源</li>
          <li>查看 Trace 并保存 Evidence PNG</li>
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
  $('#run').textContent = value ? '正在运行…' : `运行${MODES[state.mode].label}`;
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

function setModel(model) {
  state.model = model;
  for (const key of ['V1', 'V2']) {
    const button = $(`#v${key.slice(1)}`);
    if (button) button.classList.toggle('selected', key === model);
  }
  $('#vt').textContent = `${state.model} · ${state.selected || '真实 STEP 三维视图'}`;
}

function renderEvidenceOverlay(row) {
  document.querySelector('.evidence-overlay')?.remove();
  if (!row) return;
  const execution = row.execution;
  const focus = execution.evidence?.focus_ids || [];
  const overlay = document.createElement('div');
  overlay.className = 'evidence-overlay';
  overlay.innerHTML = `
    <b>${row.title}</b>
    <span>A：${focus[0] || '—'}</span>
    <span>B：${focus[1] || '—'}</span>
    <strong>${execution.evidence?.annotation || `${execution.value ?? '—'} ${execution.unit || ''}`}</strong>
    <em>${LABELS[row.outcome] || row.outcome}</em>
  `;
  $('#cad').append(overlay);
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
  if (state.run && state.selected) {
    const row = currentRows().find((item) => item.caseId === state.selected);
    renderEvidenceOverlay(row);
    setStep('evidence', 'done');
  } else {
    renderEvidenceOverlay(null);
  }
  setStatus(`${state.model} 三维已加载`, 'ok');
}

function fillModelSelect(select, selected = state.model) {
  select.innerHTML = Object.entries(state.models)
    .map(([key, model]) => `<option value="${key}" ${key === selected ? 'selected' : ''}>${key} · ${model.model_id}</option>`)
    .join('');
}

async function loadInventory(model) {
  if (!state.inventory[model]) {
    state.inventory[model] = await api(`/api/models/${model}/inventory`);
  }
  return state.inventory[model];
}

function objectChoices(model) {
  const inventory = state.inventory[model];
  if (!inventory) return [];
  const choices = [];
  for (const occurrence of inventory.occurrences) {
    if (occurrence.children > 0) continue;
    choices.push({value: {path: occurrence.path}, label: occurrence.path});
    for (const kind of ['shell', 'face']) {
      for (const item of (occurrence.subshapes?.[kind] || [])) {
        choices.push({
          value: {path: occurrence.path, selector: item.selector},
          label: `${occurrence.path}#${kind}[${item.selector.index}]`,
        });
      }
    }
  }
  return choices;
}

function fillObjectSelect(select, choices, preferredText = '') {
  select.innerHTML = '';
  for (const choice of choices) {
    const option = document.createElement('option');
    option.value = JSON.stringify(choice.value);
    option.textContent = choice.label;
    select.append(option);
  }
  const preferred = choices.findIndex((choice) => choice.label.includes(preferredText));
  if (preferred >= 0) select.selectedIndex = preferred;
}

function renderCardPreview(card) {
  const preview = $('#card-preview');
  if (!preview || !card) return;
  const rule = card.rule || {};
  preview.innerHTML = `
    <b>${card.title}</b>
    <span>${card.engineering_domain} · ${card.verification_method} · ${card.executor}</span>
    <span>权限：${rule.authority || '—'} · ${rule.operator || '—'} ${rule.threshold ?? ''} ${rule.unit || ''}</span>
    <small>${card.source_ref}</small>
  `;
}

async function renderModeConfig() {
  const mode = state.mode;
  $('#mode-hint').textContent = MODES[mode].hint;
  $('#mode-tabs').querySelectorAll('.mode-tab').forEach((button) => {
    button.classList.toggle('selected', button.dataset.mode === mode);
  });
  $('#run').textContent = `运行${MODES[mode].label}`;

  if (mode === 'EXPLORE_MEASURE') {
    $('#mode-config').innerHTML = `
      <div class="mode-title"><b>快速测量</b><span>无 Rule、无 PASS/FAIL，只保存测量事实和 Evidence。</span></div>
      <label>模型<select id="explore-model"></select></label>
      <label>对象 A<select id="explore-a"></select></label>
      <label>对象 B<select id="explore-b"></select></label>
      <label>方法<select id="explore-executor"><option value="minimum_clearance">minimum_clearance</option><option value="directional_distance">directional_distance</option><option value="angle">angle</option></select></label>
      <label id="explore-axis-field">方向<select id="explore-axis"><option value="Z">Z</option><option value="X">X</option><option value="Y">Y</option></select></label>
      <label id="explore-angle-axis-field">角度轴<select id="explore-angle-axis"><option value="Z">Z</option><option value="X">X</option><option value="Y">Y</option></select></label>
    `;
    const modelSelect = $('#explore-model');
    const executorSelect = $('#explore-executor');
    const updateExploreInputs = () => {
      $('#explore-axis-field').hidden = executorSelect.value !== 'directional_distance';
      $('#explore-angle-axis-field').hidden = executorSelect.value !== 'angle';
    };
    fillModelSelect(modelSelect);
    const fillObjects = async () => {
      const model = modelSelect.value;
      state.model = model;
      const choices = objectChoices(model) || [];
      fillObjectSelect($('#explore-a'), choices, 'battery');
      fillObjectSelect($('#explore-b'), choices, 'underbody_bracket');
    };
    await loadInventory(modelSelect.value);
    await fillObjects();
    executorSelect.onchange = updateExploreInputs;
    updateExploreInputs();
    modelSelect.onchange = async () => {
      await loadInventory(modelSelect.value);
      await fillObjects();
      await switchModel(modelSelect.value);
    };
  } else if (mode === 'ENGINEERING_CHECK') {
    $('#mode-config').innerHTML = `
      <div class="mode-title"><b>工程规则校验</b><span>规则来自 Check Card Registry；Provisional 只能进入需复核。</span></div>
      <label>模型<select id="check-model"></select></label>
      <label>Check Card<select id="check-card"></select></label>
      <div id="card-preview" class="card-preview"></div>
      <div id="binding-editor" class="binding-editor"></div>
    `;
    const modelSelect = $('#check-model');
    const cardSelect = $('#check-card');
    fillModelSelect(modelSelect);
    cardSelect.innerHTML = state.cards
      .map((card) => `<option value="${card.id}">${card.id} · ${card.title}</option>`)
      .join('');
    const refreshBindings = async () => {
      const card = state.cards.find((item) => item.id === cardSelect.value);
      const model = modelSelect.value;
      renderCardPreview(card);
      await loadInventory(model);
      const current = await api(`/api/bindings?model=${encodeURIComponent(model)}`);
      const choices = objectChoices(model);
      const required = card?.required_bindings || [];
      $('#binding-editor').innerHTML = `
        <span class="binding-title">人工 Binding（选择后保存）</span>
        ${required.map((semanticId) => `
          <label data-binding-row="${semanticId}">${semanticId}<select data-binding-id="${semanticId}"></select></label>
        `).join('')}
        <button id="save-bindings" type="button">保存 Binding</button>
      `;
      for (const semanticId of required) {
        const select = document.querySelector(`[data-binding-id="${semanticId}"]`);
        fillObjectSelect(select, choices);
        const existing = current.bindings?.[semanticId];
        const path = typeof existing === 'string' ? existing : existing?.path;
        const selector = typeof existing === 'object' ? existing?.selector : null;
        const preferred = choices.findIndex((choice) => {
          const value = choice.value;
          return value.path === path && JSON.stringify(value.selector || null) === JSON.stringify(selector || null);
        });
        if (preferred >= 0) select.selectedIndex = preferred;
      }
      $('#save-bindings').onclick = async () => {
        const bindings = {};
        for (const semanticId of required) {
          const select = document.querySelector(`[data-binding-id="${semanticId}"]`);
          bindings[semanticId] = JSON.parse(select.value);
        }
        try {
          const saved = await api('/api/bindings', {
            method: 'POST',
            headers: {'content-type': 'application/json'},
            body: JSON.stringify({model, bindings}),
          });
          setStatus(`Binding 已保存：${Object.keys(saved.validation.ok || {}).length} 项`, 'ok');
        } catch (error) {
          setStatus(`Binding 保存失败：${error.message}`, 'error');
        }
      };
    };
    await refreshBindings();
    cardSelect.onchange = refreshBindings;
    modelSelect.onchange = async () => {
      await refreshBindings();
      await switchModel(modelSelect.value);
    };
  } else {
    $('#mode-config').innerHTML = `
      <div class="mode-title"><b>版本回归</b><span>沿用现有 V1/V2 回归内核，失败绑定会阻断比较。</span></div>
      <label>回归范围<select id="regression-scope">
        <option value="legacy">兼容案例集（18 条）</option>
        <option value="mvp">本轮受控 Cards（3 条）</option>
      </select></label>
      <span class="mode-note">默认显示候选版本 V2；可点击查看 V1。</span>
    `;
  }
}

function renderSummary() {
  if (!state.run) {
    $('#sum').innerHTML = '';
    return;
  }
  if (state.run.regression) {
    const counts = {};
    for (const item of state.run.regression) counts[item.regression] = (counts[item.regression] || 0) + 1;
    $('#sum').innerHTML = Object.entries(counts)
      .map(([key, value]) => `<div><strong>${value}</strong><span>${LABELS[key] || key}</span></div>`)
      .join('');
    return;
  }
  const execution = state.run.execution;
  const status = execution?.status || '—';
  $('#sum').innerHTML = `<div><strong>${LABELS[status] || status}</strong><span>${MODES[state.run.mode]?.label || '运行结果'}</span></div>`;
}

function currentRows() {
  if (!state.run) return [];
  if (state.run.regression) {
    return state.run.regression.map((item) => ({
      caseId: item.case_id,
      title: item.title,
      outcome: item.regression,
      item,
      execution: state.model === 'V1' ? item.baseline : item.candidate,
      definition: state.run.cases.find((definition) => definition.id === item.case_id),
    }));
  }
  return [{
    caseId: state.run.execution.case_id,
    title: state.run.execution.title,
    outcome: state.run.execution.status,
    item: state.run.execution,
    execution: state.run.execution,
    definition: state.run.case,
  }];
}

function renderCaseList() {
  const rows = currentRows();
  $('#cases').innerHTML = rows.map((row) => `
    <button class="case ${row.caseId === state.selected ? 'selected' : ''}" data-id="${row.caseId}">
      <span>${row.title}</span><b class="tag-${row.outcome}">${LABELS[row.outcome] || row.outcome}</b>
    </button>
  `).join('') || '<div class="empty">没有结果</div>';
  document.querySelectorAll('.case').forEach((button) => {
    button.onclick = () => selectCase(button.dataset.id);
  });
}

function renderDetail(row) {
  const item = row.item;
  const execution = row.execution;
  const definition = row.definition || {};
  const authority = execution.rule_authority || definition.rule?.authority || '—';
  const source = definition.source_ref || '—';
  const regressionFacts = row.item.baseline ? `
      <dt>V1</dt><dd>${row.item.baseline.value ?? '—'} ${row.item.baseline.unit} · ${LABELS[row.item.baseline.status]}</dd>
      <dt>V2</dt><dd>${row.item.candidate.value ?? '—'} ${row.item.candidate.unit} · ${LABELS[row.item.candidate.status]}</dd>
      <dt>变化量</dt><dd>${row.item.delta ?? '—'} ${row.item.candidate.unit}</dd>
  ` : `
      <dt>测量值</dt><dd>${execution.value ?? '—'} ${execution.unit}</dd>
      <dt>运行模式</dt><dd>${MODES[execution.mode]?.label || execution.mode}</dd>
  `;
  $('#detail').innerHTML = `
    <h2>${row.title}</h2>
    <p class="result ${row.outcome}"><b>${LABELS[row.outcome] || row.outcome}</b></p>
    <dl class="facts">
      <dt>执行器</dt><dd>${definition.executor || execution.executor}</dd>
      <dt>规则权限</dt><dd>${authority}</dd>
      ${regressionFacts}
      <dt>规则来源</dt><dd>${source}</dd>
    </dl>
    <div class="detail-actions">
      <button id="trace">查看 Trace</button>
      <button id="shot">保存 Evidence PNG</button>
    </div>
    <pre id="out" aria-live="polite"></pre>
  `;
  $('#measure').textContent = execution.evidence?.annotation || '';
  $('#trace').onclick = async () => {
    try {
      const text = await api(`/api/runs/${state.run.run_id}/trace`);
      const lines = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
      $('#out').textContent = lines.split('\n')
        .filter((line) => line.includes(`"case_id": "${row.caseId}"`))
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
      const source = new Image();
      source.src = image.dataUrl;
      await new Promise((resolve, reject) => {
        source.onload = resolve;
        source.onerror = reject;
      });
      const canvas = document.createElement('canvas');
      canvas.width = source.naturalWidth || source.width;
      canvas.height = source.naturalHeight || source.height;
      const context = canvas.getContext('2d');
      context.drawImage(source, 0, 0);
      context.fillStyle = 'rgba(255, 255, 255, 0.92)';
      context.fillRect(18, 18, 330, 116);
      context.fillStyle = '#172033';
      context.font = 'bold 18px sans-serif';
      context.fillText(row.title, 32, 44);
      context.font = '14px sans-serif';
      context.fillText(`A: ${execution.evidence?.focus_ids?.[0] || '—'}`, 32, 68);
      context.fillText(`B: ${execution.evidence?.focus_ids?.[1] || '—'}`, 32, 88);
      context.fillText(`Value: ${execution.evidence?.annotation || '—'}`, 32, 108);
      context.font = 'bold 14px sans-serif';
      const negative = ['FAIL', 'NEW_FAIL', 'REGRESSED', 'BLOCKED'];
      const review = ['REVIEW_REQUIRED', 'NON_COMPARABLE'];
      context.fillStyle = negative.includes(row.outcome)
        ? '#b91c1c'
        : review.includes(row.outcome) ? '#a16207' : '#166534';
      context.fillText(`Status: ${LABELS[row.outcome] || row.outcome}`, 32, 128);
      const saved = await api(`/api/runs/${state.run.run_id}/evidence/${row.caseId}/screenshot`, {
        method: 'POST',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify({data_url: canvas.toDataURL('image/png')}),
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
  const row = currentRows().find((item) => item.caseId === caseId);
  if (!row) return;
  state.selected = caseId;
  renderCaseList();
  renderDetail(row);
  $('#vt').textContent = `${state.model} · ${row.title}`;
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

function parseSelectedObject(selectId) {
  return JSON.parse($(selectId).value);
}

async function runMode() {
  if (state.busy) return;
  setBusy(true);
  resetSteps();
  state.run = null;
  state.selected = null;
  state.viewerReady = false;
  $('#cases').innerHTML = '<div class="empty">正在运行…</div>';
  $('#detail').innerHTML = '<p class="hint">正在生成结果和证据…</p>';
  setStatus(`正在运行${MODES[state.mode].label}…`, 'working');
  try {
    let response;
    if (state.mode === 'EXPLORE_MEASURE') {
      const model = $('#explore-model').value;
      state.model = model;
      response = await api('/api/runs/explore', {
        method: 'POST',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify({
          model,
          target: 'explore_a',
          counterpart: 'explore_b',
          executor: $('#explore-executor').value,
          axis: $('#explore-axis')?.value || null,
          angle_axis: $('#explore-angle-axis')?.value || null,
          bindings: {
            bindings: {
              explore_a: {default: parseSelectedObject('#explore-a')},
              explore_b: {default: parseSelectedObject('#explore-b')},
            },
          },
        }),
      });
    } else if (state.mode === 'ENGINEERING_CHECK') {
      const model = $('#check-model').value;
      state.model = model;
      response = await api('/api/runs/check', {
        method: 'POST',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify({model, card_id: $('#check-card').value}),
      });
    } else {
      const scope = $('#regression-scope')?.value;
      const caseIds = scope === 'mvp'
        ? ['CLR_BAT_BRACKET', 'DIR_BAT_GROUND', 'ANG_MOTOR_YAW']
        : null;
      response = await api('/api/runs/regression', {
        method: 'POST',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify({baseline: 'V1', candidate: 'V2', case_ids: caseIds}),
      });
    }
    state.run = response;
    $('#rid').textContent = `Run ${response.run_id}`;
    renderSummary();
    setStep('run', 'done');
    const first = currentRows().find((row) => row.outcome === 'NEW_FAIL') || currentRows()[0];
    setStatus(`校验完成：${MODES[state.mode].label}`, 'ok');
    if (first) await selectCase(first.caseId);
  } catch (error) {
    setStep('run', 'error');
    setStatus(`校验失败：${error.message}`, 'error');
    $('#cases').innerHTML = `<div class="empty error-text">${error.message}</div>`;
  } finally {
    setBusy(false);
  }
}

async function switchModel(model) {
  setModel(model);
  try {
    await renderViewer();
  } catch (error) {
    state.viewerReady = false;
    setStep('model', 'error');
    setStatus(`三维加载失败：${error.message}`, 'error');
  }
}

async function switchMode(mode) {
  if (state.busy) return;
  state.mode = mode;
  state.run = null;
  state.selected = null;
  $('#rid').textContent = '尚未运行';
  $('#sum').innerHTML = '';
  $('#cases').innerHTML = '<div class="empty">尚未运行</div>';
  $('#detail').innerHTML = '<p class="hint">选择配置并运行校验。</p>';
  resetSteps();
  await renderModeConfig();
  setModel(state.model);
  await renderViewer();
}

async function boot() {
  try {
    const readiness = await api('/api/system/readiness');
    state.models = await api('/api/models');
    state.cards = await api('/api/check-cards');
    if (!state.models.V1 || !state.models.V2) throw new Error('缺少 V1/V2 模型，请先运行 bootstrap');
    setStatus(`运行环境 READY · OCP ${readiness.python_packages['cadquery-ocp']}`, 'ok');
    await renderModeConfig();
    await renderViewer();
  } catch (error) {
    setStep('model', 'error');
    setStatus(`启动检查失败：${error.message}`, 'error');
    $('#cad').innerHTML = `<div class="viewer-empty error-text">${error.message}</div>`;
  }
}

$('#run').onclick = runMode;
$('#v1').onclick = () => switchModel('V1');
$('#v2').onclick = () => switchModel('V2');
document.querySelectorAll('.mode-tab').forEach((button) => {
  button.onclick = () => switchMode(button.dataset.mode);
});
boot();
