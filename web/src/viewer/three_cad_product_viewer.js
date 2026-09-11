import { Display, Viewer } from 'three-cad-viewer';
import 'three-cad-viewer/css';

const ROOT_ID = '/CADCheck';
const IDENTITY = [[0, 0, 0], [0, 0, 0, 1]];

const finiteBBox = (bbox) => Array.isArray(bbox) && bbox.length === 6 && bbox.every(Number.isFinite);
const safeName = (value) => String(value || 'occ').replace(/[^A-Za-z0-9_.-]+/g, '_');

function boxShape(bbox) {
  const [xmin, ymin, zmin, xmax, ymax, zmax] = bbox;
  const vertices = [
    xmin,ymin,zmin, xmin,ymin,zmax, xmin,ymax,zmin, xmin,ymax,zmax,
    xmax,ymin,zmin, xmax,ymin,zmax, xmax,ymax,zmin, xmax,ymax,zmax,
  ];
  const triangles = [
    0,1,3, 0,3,2,
    4,6,7, 4,7,5,
    0,4,5, 0,5,1,
    2,3,7, 2,7,6,
    0,2,6, 0,6,4,
    1,5,7, 1,7,3,
  ];
  const normals = new Array(vertices.length).fill(0);
  for (let i = 0; i < triangles.length; i += 3) {
    const ia = triangles[i] * 3, ib = triangles[i + 1] * 3, ic = triangles[i + 2] * 3;
    const ax = vertices[ia], ay = vertices[ia + 1], az = vertices[ia + 2];
    const bx = vertices[ib], by = vertices[ib + 1], bz = vertices[ib + 2];
    const cx = vertices[ic], cy = vertices[ic + 1], cz = vertices[ic + 2];
    const ux = bx - ax, uy = by - ay, uz = bz - az;
    const vx = cx - ax, vy = cy - ay, vz = cz - az;
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    for (const index of [ia, ib, ic]) {
      normals[index] += nx; normals[index + 1] += ny; normals[index + 2] += nz;
    }
  }
  for (let i = 0; i < normals.length; i += 3) {
    const length = Math.hypot(normals[i], normals[i + 1], normals[i + 2]) || 1;
    normals[i] /= length; normals[i + 1] /= length; normals[i + 2] /= length;
  }
  return {
    vertices,
    normals,
    triangles,
    triangles_per_face: [triangles.length / 3],
    edges: [],
    segments_per_edge: [],
    obj_vertices: [],
    face_types: [0],
    edge_types: [],
  };
}

function normalizeShape(shape = {}) {
  const vertices = Array.from(shape.vertices || []).flat(Infinity).map(Number);
  const triangles = Array.from(shape.triangles || []).flat(Infinity).map(Number);
  const normals = Array.from(shape.normals || []).flat(Infinity).map(Number);
  const edges = Array.from(shape.edges || []).flat(Infinity).map(Number);
  const result = {
    ...shape,
    vertices,
    triangles,
    normals,
    edges,
    obj_vertices: Array.from(shape.obj_vertices || []).flat(Infinity).map(Number),
    face_types: Array.from(shape.face_types || []).flat(Infinity).map(Number),
    edge_types: Array.from(shape.edge_types || []).flat(Infinity).map(Number),
  };
  if (triangles.length && !result.triangles_per_face?.length) {
    result.triangles_per_face = [triangles.length / 3];
  }
  if (edges.length && !result.segments_per_edge?.length) {
    result.segments_per_edge = [edges.length / 6];
  }
  if (!result.triangles_per_face) result.triangles_per_face = [];
  if (!result.segments_per_edge) result.segments_per_edge = [];
  return result;
}

function partForOccurrence(occurrenceId, shape, { color = '#9aa6b2', alpha = 1, proxy = false } = {}) {
  const name = safeName(occurrenceId);
  return {
    version: 3,
    id: `${ROOT_ID}/${name}`,
    name,
    type: 'shapes',
    subtype: 'solid',
    state: [1, 1],
    color,
    alpha,
    renderback: true,
    texture: null,
    accuracy: null,
    bb: null,
    loc: IDENTITY,
    shape: normalizeShape(shape),
    _cadcheck_occurrence_id: occurrenceId,
    _cadcheck_proxy: proxy,
  };
}

function flattenTree(nodes, out = []) {
  for (const node of nodes || []) {
    out.push(node);
    flattenTree(node.children, out);
  }
  return out;
}

function flattenParts(node, out = []) {
  for (const part of node?.parts || []) {
    if (part?.parts?.length) flattenParts(part, out);
    else if (part?.shape) out.push(part);
  }
  return out;
}

/**
 * dev-3 viewer spike.
 *
 * three-cad-viewer owns CAD navigation / camera / clipping UX. CAD Check owns
 * Canonical AssemblyTree, OCP tessellation, proxy/preview/detail policy and all
 * engineering truth. This intentionally reuses the normalized derivative from
 * dev-2 instead of reviving the retired all-geometry streaming architecture.
 */
export class ThreeCadProductViewer {
  constructor(host, { onPick, maxResidentDetails = 24 } = {}) {
    this.host = host;
    this.onPick = onPick || (() => {});
    this.maxResidentDetails = maxResidentDetails;
    this.display = null;
    this.viewer = null;
    this.root = null;
    this.occurrencePaths = new Map();
    this.pathOccurrences = new Map();
    this.occurrenceBounds = new Map();
    this.proxyOccurrences = new Set();
    this.previewOccurrences = new Set();
    this.detailOccurrences = new Set();
    this.detailOrder = [];
    this.selected = new Set();
    this.hidden = new Set();
    this.isolated = null;
    this.renderMode = 'solid';
    this.sectionPlane = null;
    this.evidence = null;
    this._initViewer();
    this._stampProductUI();
  }

  _initViewer() {
    this.host.innerHTML = '';
    this.display = new Display(this.host, {
      cadWidth: Math.max(700, this.host.clientWidth || 900),
      height: Math.max(560, this.host.clientHeight || 620),
      treeWidth: 0,
      theme: 'browser',
      glass: true,
      tools: true,
      measureTools: false,
      selectTool: true,
      explodeTool: false,
      zscaleTool: false,
      zebraTool: false,
      studioTool: false,
    });
    this.viewer = new Viewer(this.display, { tools: true }, (changes) => this._onViewerChanges(changes));
  }

  _onViewerChanges(changes) {
    const candidate = changes?.lastObject?.new || changes?.selected?.new || changes?.path?.new;
    const path = typeof candidate === 'string' ? candidate : candidate?.path || candidate?.backendId;
    if (!path) return;
    const occurrenceId = this.pathOccurrences.get(path);
    if (occurrenceId) this.onPick(occurrenceId, candidate?.point || null, null);
  }

  _stampProductUI() {
    const badge = document.querySelector('#viewer-badge');
    if (badge) badge.textContent = 'THREE-CAD · NATIVE OCP · PROXY/DETAIL';
    const status = document.querySelector('#status-viewer');
    if (status) status.textContent = status.textContent.replace(/xeokit|Babylon/gi, 'three-cad');
    const meta = document.querySelector('#viewer-meta');
    if (meta) meta.textContent = meta.textContent.replace(/xeokit|Babylon/gi, 'three-cad');
  }

  _renderOptions() {
    return [
      {
        ambientIntensity: 1.0,
        directIntensity: 1.1,
        metalness: 0.18,
        roughness: 0.72,
        edgeColor: 0x606975,
        defaultOpacity: 0.78,
        normalLen: 0,
      },
      {
        ortho: true,
        control: 'trackball',
        up: 'Z',
        collapse: 1,
        reset_camera: 'iso',
      },
    ];
  }

  _leafNodes(assembly) {
    return flattenTree(assembly?.roots || []).filter((node) => !node.children?.length);
  }

  _registerPath(occurrenceId) {
    const path = `${ROOT_ID}/${safeName(occurrenceId)}`;
    this.occurrencePaths.set(occurrenceId, path);
    this.pathOccurrences.set(path, occurrenceId);
    return path;
  }

  loadOverview(assembly) {
    this.clear({ keepViewer: true });
    const parts = [];
    for (const node of this._leafNodes(assembly)) {
      if (!finiteBBox(node.bbox) || !node.occurrence_id) continue;
      const occurrenceId = node.occurrence_id;
      this._registerPath(occurrenceId);
      this.occurrenceBounds.set(occurrenceId, [...node.bbox]);
      parts.push(partForOccurrence(occurrenceId, boxShape(node.bbox), {
        color: '#a7b1bc',
        alpha: 0.16,
        proxy: true,
      }));
      this.proxyOccurrences.add(occurrenceId);
    }
    this.root = {
      version: 3,
      name: 'CADCheck',
      id: ROOT_ID,
      loc: IDENTITY,
      normal_len: 0,
      parts,
    };
    const [appearance, view] = this._renderOptions();
    this.viewer.render(this.root, appearance, view);
    this.viewer.setView?.('iso');
    this.viewer.presetCamera?.('iso');
    this._stampProductUI();
    return {
      occurrences: parts.length,
      representation: 'three-cad proxy + normalized preview + demand detail',
      max_resident_details: this.maxResidentDetails,
    };
  }

  _replaceOccurrence(occurrenceId, sourcePart, kind) {
    const path = this.occurrencePaths.get(occurrenceId) || this._registerPath(occurrenceId);
    const normalized = partForOccurrence(occurrenceId, sourcePart.shape, {
      color: kind === 'detail' ? '#b7bec6' : '#929fac',
      alpha: 1,
    });
    normalized.loc = Array.isArray(sourcePart.loc) ? sourcePart.loc : IDENTITY;
    try {
      this.viewer.removePart?.(path);
    } catch {}
    try {
      this.viewer.addPart?.(ROOT_ID, normalized);
      this.proxyOccurrences.delete(occurrenceId);
      if (kind === 'detail') {
        this.previewOccurrences.delete(occurrenceId);
        this.detailOccurrences.add(occurrenceId);
        this.detailOrder = this.detailOrder.filter((id) => id !== occurrenceId);
        this.detailOrder.push(occurrenceId);
      } else if (!this.detailOccurrences.has(occurrenceId)) {
        this.previewOccurrences.add(occurrenceId);
      }
      return true;
    } catch (error) {
      console.warn(`three-cad ${kind} replacement failed for ${occurrenceId}`, error);
      return false;
    }
  }

  loadPreview(payload) {
    const loaded = [];
    for (const part of flattenParts(payload?.shapes || payload?.detail?.shapes || {})) {
      const occurrenceId = part.occurrence_id;
      if (!occurrenceId || this.detailOccurrences.has(occurrenceId)) continue;
      if (this._replaceOccurrence(occurrenceId, part, 'preview')) loaded.push(occurrenceId);
    }
    return loaded;
  }

  finishPreview() {}

  loadDetail(payload, { replace = false } = {}) {
    if (replace) this.disposeDetail();
    const loaded = [];
    for (const part of flattenParts(payload?.shapes || payload?.detail?.shapes || {})) {
      const occurrenceId = part.occurrence_id;
      if (!occurrenceId) continue;
      if (this._replaceOccurrence(occurrenceId, part, 'detail')) loaded.push(occurrenceId);
    }
    this._enforceDetailBudget();
    return loaded;
  }

  _restoreProxy(occurrenceId) {
    const bbox = this.occurrenceBounds.get(occurrenceId);
    if (!bbox) return;
    const path = this.occurrencePaths.get(occurrenceId);
    try { this.viewer.removePart?.(path); } catch {}
    try {
      this.viewer.addPart?.(ROOT_ID, partForOccurrence(occurrenceId, boxShape(bbox), {
        color: '#a7b1bc', alpha: 0.16, proxy: true,
      }));
      this.proxyOccurrences.add(occurrenceId);
    } catch {}
    this.previewOccurrences.delete(occurrenceId);
    this.detailOccurrences.delete(occurrenceId);
  }

  _enforceDetailBudget() {
    let guard = this.detailOrder.length * 3 + 3;
    while (this.detailOrder.length > this.maxResidentDetails && guard-- > 0) {
      const candidate = this.detailOrder.shift();
      if (!candidate) break;
      if (this.selected.has(candidate)) {
        this.detailOrder.push(candidate);
        continue;
      }
      this._restoreProxy(candidate);
    }
  }

  disposeDetail(except = []) {
    const keep = new Set(except);
    for (const occurrenceId of [...this.detailOccurrences]) {
      if (!keep.has(occurrenceId)) this._restoreProxy(occurrenceId);
    }
    this.detailOrder = this.detailOrder.filter((id) => keep.has(id));
  }

  disposePreview(except = []) {
    const keep = new Set(except);
    for (const occurrenceId of [...this.previewOccurrences]) {
      if (!keep.has(occurrenceId)) this._restoreProxy(occurrenceId);
    }
  }

  setSelection(occurrenceIds) {
    this.selected = new Set(Array.isArray(occurrenceIds) ? occurrenceIds : [occurrenceIds].filter(Boolean));
    this._enforceDetailBudget();
  }

  setVisibility(occurrenceIds, visible) {
    for (const id of occurrenceIds || []) {
      if (visible) this.hidden.delete(id);
      else this.hidden.add(id);
    }
    // three-cad's native double-click/tree visibility remains authoritative in
    // this spike. Product-driven visibility sync is deliberately deferred until
    // camera/navigation quality passes the dev-3 gate.
  }

  isolate(occurrenceIds) {
    this.isolated = occurrenceIds?.length ? new Set(occurrenceIds) : null;
  }

  showAll() {
    this.hidden.clear();
    this.isolated = null;
  }

  focusObjects(occurrenceIds) {
    const id = occurrenceIds?.[0];
    const path = id ? this.occurrencePaths.get(id) : null;
    try {
      if (path) this.viewer.setView?.('iso', path);
      else this.viewer.setView?.('iso');
    } catch {
      try { this.viewer.presetCamera?.('iso'); } catch {}
    }
  }

  setRenderMode(mode) {
    this.renderMode = mode;
    try {
      if (typeof this.viewer.setTransparent === 'function') this.viewer.setTransparent(mode === 'transparent');
      if (typeof this.viewer.setBlackEdges === 'function') this.viewer.setBlackEdges(mode === 'edges');
    } catch {}
    return true;
  }

  presetView(view) {
    try { this.viewer.setView?.(view); }
    catch { try { this.viewer.presetCamera?.(view); } catch {} }
  }

  fitAll() {
    try { this.viewer.resize?.(); }
    catch { try { this.viewer.recenterCamera?.(); } catch {} }
  }

  showEvidenceGeometry(execution) {
    this.evidence = execution?.evidence || execution || null;
    const text = this.evidence?.annotation || (execution?.value != null ? `${execution.value} ${execution.unit || ''}` : '');
    let annotation = this.host.querySelector('.viewer-annotation');
    if (!annotation) {
      annotation = document.createElement('div');
      annotation.className = 'viewer-annotation';
      annotation.style.position = 'absolute';
      annotation.style.right = '14px';
      annotation.style.bottom = '14px';
      annotation.style.zIndex = '8';
      this.host.appendChild(annotation);
    }
    annotation.textContent = text || '';
    annotation.classList.toggle('hidden', !text);
  }

  setSectionPlane(plane) {
    this.sectionPlane = plane || null;
    // Native three-cad clipping UI is available in the toolbar. Programmatic
    // Evidence-plane sync is a phase-2 task after this branch proves CAD UX.
  }

  async captureView() {
    const image = await this.viewer.getImage?.('cadcheck');
    return image?.dataUrl || image?.dataURL || image || null;
  }

  getViewState() {
    return {
      viewer: 'three-cad-proxy-detail-v1',
      selected: [...this.selected],
      hidden: [...this.hidden],
      isolated: this.isolated ? [...this.isolated] : [],
      render_mode: this.renderMode,
      section_plane: this.sectionPlane,
      resident_preview_occurrences: [...this.previewOccurrences],
      resident_detail_occurrences: [...this.detailOccurrences],
    };
  }

  applyViewState(state) {
    if (!state) return false;
    this.selected = new Set(state.selected || []);
    this.hidden = new Set(state.hidden || []);
    this.isolated = state.isolated?.length ? new Set(state.isolated) : null;
    this.renderMode = state.render_mode || 'solid';
    this.sectionPlane = state.section_plane || null;
    return true;
  }

  hasOccurrence(occurrenceId) {
    return this.occurrencePaths.has(occurrenceId);
  }

  getStats() {
    return {
      viewer: 'three-cad',
      proxy_count: this.proxyOccurrences.size,
      preview_occurrences: this.previewOccurrences.size,
      resident_detail_occurrences: this.detailOccurrences.size,
      selected_count: this.selected.size,
      hidden_count: this.hidden.size,
      isolated_count: this.isolated?.size || 0,
      render_mode: this.renderMode,
      max_resident_details: this.maxResidentDetails,
      representation: 'three-cad proxy + normalized preview + demand detail',
    };
  }

  clear({ keepViewer = false } = {}) {
    try { this.viewer?.clear?.(); } catch {}
    this.root = null;
    this.occurrencePaths.clear();
    this.pathOccurrences.clear();
    this.occurrenceBounds.clear();
    this.proxyOccurrences.clear();
    this.previewOccurrences.clear();
    this.detailOccurrences.clear();
    this.detailOrder = [];
    this.selected.clear();
    this.hidden.clear();
    this.isolated = null;
    this.sectionPlane = null;
    this.evidence = null;
    this.host.querySelector('.viewer-annotation')?.remove();
    if (!keepViewer && !this.viewer) this._initViewer();
  }

  dispose() {
    try { this.viewer?.dispose?.(); } catch {}
    try { this.display?.dispose?.(); } catch {}
    this.viewer = null;
    this.display = null;
    this.host.replaceChildren();
  }
}
