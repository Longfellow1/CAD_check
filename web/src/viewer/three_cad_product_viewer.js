import { Display, Viewer } from 'three-cad-viewer';
import 'three-cad-viewer/css';

const ROOT_ID = '/CADCheck';
const IDENTITY = [[0, 0, 0], [0, 0, 0, 1]];

const finiteBBox = (bbox) => Array.isArray(bbox) && bbox.length === 6 && bbox.every(Number.isFinite);
const safeName = (value) => String(value || 'occ').replace(/[^A-Za-z0-9_.-]+/g, '_');
const flatNumbers = (value) => Array.from(value || []).flat(Infinity).map(Number);

function extendBounds(current, bbox) {
  if (!finiteBBox(bbox)) return current;
  if (!current) return [...bbox];
  return [
    Math.min(current[0], bbox[0]), Math.min(current[1], bbox[1]), Math.min(current[2], bbox[2]),
    Math.max(current[3], bbox[3]), Math.max(current[4], bbox[4]), Math.max(current[5], bbox[5]),
  ];
}

function bboxForPoints(points) {
  if (!points?.length) return null;
  let bbox = null;
  for (let i = 0; i + 2 < points.length; i += 3) {
    const x = Number(points[i]), y = Number(points[i + 1]), z = Number(points[i + 2]);
    if (![x, y, z].every(Number.isFinite)) continue;
    bbox = extendBounds(bbox, [x, y, z, x, y, z]);
  }
  return bbox;
}

function rotateVector(v, q) {
  const [x, y, z] = v;
  const [qx, qy, qz, qw] = q;
  const tx = 2 * (qy * z - qz * y);
  const ty = 2 * (qz * x - qx * z);
  const tz = 2 * (qx * y - qy * x);
  return [
    x + qw * tx + (qy * tz - qz * ty),
    y + qw * ty + (qz * tx - qx * tz),
    z + qw * tz + (qx * ty - qy * tx),
  ];
}

function transformTriples(values, position, quaternion, translate = true) {
  const out = [];
  for (let i = 0; i + 2 < values.length; i += 3) {
    const rotated = rotateVector([values[i], values[i + 1], values[i + 2]], quaternion);
    out.push(
      rotated[0] + (translate ? position[0] : 0),
      rotated[1] + (translate ? position[1] : 0),
      rotated[2] + (translate ? position[2] : 0),
    );
  }
  return out;
}

function computeVertexNormals(vertices, triangles) {
  const normals = new Array(vertices.length).fill(0);
  for (let i = 0; i + 2 < triangles.length; i += 3) {
    const ia = triangles[i] * 3, ib = triangles[i + 1] * 3, ic = triangles[i + 2] * 3;
    if (ic + 2 >= vertices.length) continue;
    const ax = vertices[ia], ay = vertices[ia + 1], az = vertices[ia + 2];
    const bx = vertices[ib], by = vertices[ib + 1], bz = vertices[ib + 2];
    const cx = vertices[ic], cy = vertices[ic + 1], cz = vertices[ic + 2];
    const ux = bx - ax, uy = by - ay, uz = bz - az;
    const vx = cx - ax, vy = cy - ay, vz = cz - az;
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    for (const index of [ia, ib, ic]) {
      normals[index] += nx;
      normals[index + 1] += ny;
      normals[index + 2] += nz;
    }
  }
  for (let i = 0; i < normals.length; i += 3) {
    const length = Math.hypot(normals[i], normals[i + 1], normals[i + 2]) || 1;
    normals[i] /= length;
    normals[i + 1] /= length;
    normals[i + 2] /= length;
  }
  return normals;
}

function boxShape(bbox) {
  const [xmin, ymin, zmin, xmax, ymax, zmax] = bbox;
  const vertices = [
    xmin,ymin,zmin, xmin,ymin,zmax, xmin,ymax,zmin, xmin,ymax,zmax,
    xmax,ymin,zmin, xmax,ymin,zmax, xmax,ymax,zmin, xmax,ymax,zmax,
  ];
  const triangles = [
    0,1,3, 0,3,2, 4,6,7, 4,7,5,
    0,4,5, 0,5,1, 2,3,7, 2,7,6,
    0,2,6, 0,6,4, 1,5,7, 1,7,3,
  ];
  const edgePairs = [[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]];
  const edges = [];
  for (const [a, b] of edgePairs) edges.push(...vertices.slice(a * 3, a * 3 + 3), ...vertices.slice(b * 3, b * 3 + 3));
  return {
    vertices,
    normals: computeVertexNormals(vertices, triangles),
    triangles,
    triangles_per_face: [2, 2, 2, 2, 2, 2],
    edges,
    segments_per_edge: new Array(edgePairs.length).fill(1),
    obj_vertices: [...vertices],
    face_types: new Array(6).fill(0),
    edge_types: new Array(edgePairs.length).fill(0),
  };
}

function normalizeShape(shape = {}, loc = IDENTITY) {
  const vertices0 = flatNumbers(shape.vertices);
  const triangles = flatNumbers(shape.triangles).map((value) => Math.trunc(value));
  const normals0 = flatNumbers(shape.normals);
  const edges0 = flatNumbers(shape.edges);
  const objVertices0 = flatNumbers(shape.obj_vertices);
  const position = Array.isArray(loc?.[0]) && loc[0].length === 3 ? loc[0].map(Number) : [0, 0, 0];
  const quaternion = Array.isArray(loc?.[1]) && loc[1].length === 4 ? loc[1].map(Number) : [0, 0, 0, 1];
  const identity = position.every((value) => Math.abs(value) < 1e-12)
    && Math.abs(quaternion[0]) < 1e-12 && Math.abs(quaternion[1]) < 1e-12
    && Math.abs(quaternion[2]) < 1e-12 && Math.abs(quaternion[3] - 1) < 1e-12;
  const vertices = identity ? vertices0 : transformTriples(vertices0, position, quaternion, true);
  let normals = identity ? normals0 : transformTriples(normals0, [0, 0, 0], quaternion, false);
  const edges = identity ? edges0 : transformTriples(edges0, position, quaternion, true);
  const objVertices = identity ? objVertices0 : transformTriples(objVertices0, position, quaternion, true);
  if (triangles.length && normals.length !== vertices.length) normals = computeVertexNormals(vertices, triangles);
  const trianglesPerFace = flatNumbers(shape.triangles_per_face).map((value) => Math.trunc(value));
  const segmentsPerEdge = flatNumbers(shape.segments_per_edge).map((value) => Math.trunc(value));
  const faceTypes = flatNumbers(shape.face_types).map((value) => Math.trunc(value));
  const edgeTypes = flatNumbers(shape.edge_types).map((value) => Math.trunc(value));
  return {
    vertices,
    normals,
    triangles,
    edges,
    obj_vertices: objVertices,
    triangles_per_face: trianglesPerFace.length ? trianglesPerFace : (triangles.length ? [triangles.length / 3] : []),
    segments_per_edge: segmentsPerEdge.length ? segmentsPerEdge : (edges.length ? new Array(edges.length / 6).fill(1) : []),
    face_types: faceTypes.length ? faceTypes : (triangles.length ? [0] : []),
    edge_types: edgeTypes.length ? edgeTypes : (edges.length ? new Array(edges.length / 6).fill(0) : []),
  };
}

function mergeOccurrenceParts(parts) {
  const merged = {
    vertices: [], normals: [], triangles: [], edges: [], obj_vertices: [],
    triangles_per_face: [], segments_per_edge: [], face_types: [], edge_types: [],
  };
  for (const part of parts || []) {
    const shape = normalizeShape(part.shape || {}, part.loc || IDENTITY);
    const vertexOffset = merged.vertices.length / 3;
    merged.vertices.push(...shape.vertices);
    merged.normals.push(...shape.normals);
    merged.triangles.push(...shape.triangles.map((index) => index + vertexOffset));
    merged.edges.push(...shape.edges);
    merged.obj_vertices.push(...shape.obj_vertices);
    merged.triangles_per_face.push(...shape.triangles_per_face);
    merged.segments_per_edge.push(...shape.segments_per_edge);
    merged.face_types.push(...shape.face_types);
    merged.edge_types.push(...shape.edge_types);
  }
  if (merged.triangles.length && merged.normals.length !== merged.vertices.length) {
    merged.normals = computeVertexNormals(merged.vertices, merged.triangles);
  }
  return merged;
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
    shape: normalizeShape(shape, IDENTITY),
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

function groupedParts(payload) {
  const grouped = new Map();
  for (const part of flattenParts(payload?.shapes || payload?.detail?.shapes || {})) {
    const occurrenceId = part.occurrence_id;
    if (!occurrenceId) continue;
    if (!grouped.has(occurrenceId)) grouped.set(occurrenceId, []);
    grouped.get(occurrenceId).push(part);
  }
  return grouped;
}

/**
 * Product adapter for the dev-3 route.
 *
 * three-cad-viewer owns mature CAD camera/navigation/picking/clipping UX.
 * CAD Check owns Canonical AssemblyTree, stable occurrence identity, OCP truth,
 * normalized display derivatives and the proxy/preview/detail residency policy.
 * This is deliberately NOT the retired all-detail streaming architecture.
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
    this.previewCache = new Map();
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
    this.evidenceObjects = [];
    this.bounds = null;
    this._resizeRaf = null;
    this._initViewer();
    this._stampProductUI(true);
  }

  _initViewer() {
    this.host.innerHTML = '';
    const width = Math.max(700, this.host.clientWidth || 900);
    const height = Math.max(520, this.host.clientHeight || 620);
    this.display = new Display(this.host, {
      cadWidth: width,
      height,
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
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver((entries) => {
        const rect = entries?.[0]?.contentRect;
        if (!rect || !this.viewer?.ready) return;
        const nextWidth = Math.max(320, Math.floor(rect.width));
        const nextHeight = Math.max(320, Math.floor(rect.height));
        cancelAnimationFrame(this._resizeRaf);
        this._resizeRaf = requestAnimationFrame(() => {
          try { this.viewer.resizeCadView?.(nextWidth, 0, nextHeight, true); } catch {}
        });
      });
      this.resizeObserver.observe(this.host);
    }
  }

  _onViewerChanges(changes) {
    const pick = changes?.lastPick?.new || changes?.lastObject?.new || changes?.selected?.new;
    if (!pick) return;
    let path = typeof pick === 'string' ? pick : pick.path || pick.backendId || null;
    if (path && pick.name && !String(path).endsWith(`/${pick.name}`)) path = `${String(path).replace(/\/$/, '')}/${pick.name}`;
    if (!path) return;
    const occurrenceId = this.pathOccurrences.get(path);
    if (!occurrenceId) return;
    const point = pick.point?.toArray?.() || pick.point || null;
    this.onPick(occurrenceId, point, null);
  }

  _stampProductUI(deferred = false) {
    const stamp = () => {
      const badge = document.querySelector('#viewer-badge');
      if (badge) badge.textContent = 'THREE-CAD · NATIVE OCP · PROXY/PREVIEW/DETAIL';
      for (const selector of ['#status-viewer', '#viewer-meta']) {
        const element = document.querySelector(selector);
        if (element) element.textContent = element.textContent.replace(/xeokit|Babylon/gi, 'three-cad');
      }
    };
    stamp();
    if (deferred) setTimeout(stamp, 0);
  }

  _renderOptions() {
    return [
      {
        ambientIntensity: 1.05,
        directIntensity: 1.1,
        metalness: 0.12,
        roughness: 0.78,
        edgeColor: 0x56616f,
        defaultOpacity: 1.0,
        normalLen: 0,
      },
      {
        ortho: true,
        ticks: 5,
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

  _boundsForIds(occurrenceIds) {
    let bounds = null;
    for (const id of occurrenceIds || []) bounds = extendBounds(bounds, this.occurrenceBounds.get(id));
    return bounds;
  }

  _tuneNavigation() {
    try { this.viewer.setRotateSpeed?.(1.0, false); } catch {}
    try { this.viewer.setPanSpeed?.(1.0, false); } catch {}
    try { this.viewer.setZoomSpeed?.(1.15, false); } catch {}
  }

  loadOverview(assembly) {
    this.clear({ keepViewer: true });
    const parts = [];
    let bounds = null;
    for (const node of this._leafNodes(assembly)) {
      if (!finiteBBox(node.bbox) || !node.occurrence_id) continue;
      const occurrenceId = node.occurrence_id;
      this._registerPath(occurrenceId);
      this.occurrenceBounds.set(occurrenceId, [...node.bbox]);
      bounds = extendBounds(bounds, node.bbox);
      parts.push(partForOccurrence(occurrenceId, boxShape(node.bbox), {
        color: '#a7b1bc',
        alpha: 0.12,
        proxy: true,
      }));
      this.proxyOccurrences.add(occurrenceId);
    }
    this.bounds = bounds;
    this.root = { version: 3, name: 'CADCheck', id: ROOT_ID, loc: IDENTITY, normal_len: 0, parts };
    const [appearance, view] = this._renderOptions();
    this.viewer.render(this.root, appearance, view);
    this._tuneNavigation();
    this.viewer.presetCamera?.('iso');
    this._applyVisibility();
    this._stampProductUI(true);
    return {
      occurrences: parts.length,
      representation: 'three-cad proxy + normalized preview + demand detail',
      max_resident_details: this.maxResidentDetails,
    };
  }

  _setRepresentation(occurrenceId, shape, kind, { skipBounds = true } = {}) {
    const path = this.occurrencePaths.get(occurrenceId) || this._registerPath(occurrenceId);
    const part = partForOccurrence(occurrenceId, shape, {
      color: kind === 'detail' ? '#bcc4cc' : kind === 'preview' ? '#98a5b2' : '#a7b1bc',
      alpha: kind === 'proxy' ? 0.12 : 1,
      proxy: kind === 'proxy',
    });
    try {
      this.viewer.updatePart(path, part, { skipBounds });
    } catch (updateError) {
      try {
        this.viewer.removePart(path, { skipBounds: true });
        this.viewer.addPart(ROOT_ID, part, { skipBounds });
      } catch (replaceError) {
        console.warn(`three-cad ${kind} replacement failed for ${occurrenceId}`, updateError, replaceError);
        return false;
      }
    }
    this.proxyOccurrences.delete(occurrenceId);
    this.previewOccurrences.delete(occurrenceId);
    this.detailOccurrences.delete(occurrenceId);
    if (kind === 'proxy') this.proxyOccurrences.add(occurrenceId);
    if (kind === 'preview') this.previewOccurrences.add(occurrenceId);
    if (kind === 'detail') this.detailOccurrences.add(occurrenceId);
    return true;
  }

  _flushScene() {
    try { this.viewer.updateBounds?.(); } catch (error) { console.warn('three-cad updateBounds failed', error); }
    this._applyVisibility();
    this._syncSelectionBox();
    this._stampProductUI(true);
  }

  loadPreview(payload) {
    const loaded = [];
    let changed = false;
    for (const [occurrenceId, parts] of groupedParts(payload)) {
      const shape = mergeOccurrenceParts(parts);
      this.previewCache.set(occurrenceId, shape);
      if (this.detailOccurrences.has(occurrenceId)) continue;
      if (this._setRepresentation(occurrenceId, shape, 'preview', { skipBounds: true })) {
        loaded.push(occurrenceId);
        changed = true;
      }
    }
    if (changed) this._flushScene();
    return loaded;
  }

  finishPreview() {
    this._applyVisibility();
    this._stampProductUI(true);
  }

  loadDetail(payload, { replace = false } = {}) {
    if (replace) this.disposeDetail();
    const loaded = [];
    let changed = false;
    for (const [occurrenceId, parts] of groupedParts(payload)) {
      const shape = mergeOccurrenceParts(parts);
      if (this._setRepresentation(occurrenceId, shape, 'detail', { skipBounds: true })) {
        this.detailOrder = this.detailOrder.filter((id) => id !== occurrenceId);
        this.detailOrder.push(occurrenceId);
        loaded.push(occurrenceId);
        changed = true;
      }
    }
    if (changed) this._flushScene();
    this._enforceDetailBudget();
    this._stampProductUI(true);
    return loaded;
  }

  _restoreOccurrence(occurrenceId, { skipBounds = true } = {}) {
    const preview = this.previewCache.get(occurrenceId);
    if (preview) return this._setRepresentation(occurrenceId, preview, 'preview', { skipBounds });
    const bbox = this.occurrenceBounds.get(occurrenceId);
    if (!bbox) return false;
    return this._setRepresentation(occurrenceId, boxShape(bbox), 'proxy', { skipBounds });
  }

  _enforceDetailBudget() {
    const evicted = [];
    let guard = this.detailOrder.length * 3 + 3;
    while (this.detailOrder.length > this.maxResidentDetails && guard-- > 0) {
      const candidate = this.detailOrder.shift();
      if (!candidate) break;
      if (this.selected.has(candidate)) {
        this.detailOrder.push(candidate);
        continue;
      }
      if (this._restoreOccurrence(candidate, { skipBounds: true })) evicted.push(candidate);
    }
    if (evicted.length) this._flushScene();
  }

  disposeDetail(except = []) {
    const keep = new Set(except);
    let changed = false;
    for (const occurrenceId of [...this.detailOccurrences]) {
      if (keep.has(occurrenceId)) continue;
      changed = this._restoreOccurrence(occurrenceId, { skipBounds: true }) || changed;
    }
    this.detailOrder = this.detailOrder.filter((id) => keep.has(id));
    if (changed) this._flushScene();
  }

  disposePreview(except = []) {
    const keep = new Set(except);
    let changed = false;
    for (const occurrenceId of [...this.previewCache.keys()]) {
      if (keep.has(occurrenceId)) continue;
      this.previewCache.delete(occurrenceId);
      if (!this.detailOccurrences.has(occurrenceId) && this.previewOccurrences.has(occurrenceId)) {
        const bbox = this.occurrenceBounds.get(occurrenceId);
        if (bbox) changed = this._setRepresentation(occurrenceId, boxShape(bbox), 'proxy', { skipBounds: true }) || changed;
      }
    }
    if (changed) this._flushScene();
  }

  _visibleState(occurrenceId) {
    return !this.hidden.has(occurrenceId) && (!this.isolated || this.isolated.has(occurrenceId));
  }

  _applyVisibility() {
    if (!this.viewer?.ready) return;
    const states = {};
    for (const [occurrenceId, path] of this.occurrencePaths.entries()) {
      states[path] = this._visibleState(occurrenceId) ? [1, 1] : [0, 0];
    }
    try {
      this.viewer.setStates?.(states);
      this.viewer.update?.(true, false);
    } catch (error) {
      console.warn('three-cad visibility sync failed', error);
    }
  }

  _syncSelectionBox() {
    if (!this.viewer?.ready) return;
    try { this.viewer.removeLastBbox?.(); } catch {}
    const first = [...this.selected].find((id) => this._visibleState(id));
    const path = first ? this.occurrencePaths.get(first) : null;
    if (path) {
      try { this.viewer.setBoundingBox?.(path); } catch {}
    }
  }

  setSelection(occurrenceIds) {
    this.selected = new Set(Array.isArray(occurrenceIds) ? occurrenceIds : [occurrenceIds].filter(Boolean));
    this._enforceDetailBudget();
    this._syncSelectionBox();
  }

  setVisibility(occurrenceIds, visible) {
    for (const id of occurrenceIds || []) {
      if (visible) this.hidden.delete(id);
      else this.hidden.add(id);
    }
    this._applyVisibility();
    this._syncSelectionBox();
  }

  isolate(occurrenceIds) {
    this.isolated = occurrenceIds?.length ? new Set(occurrenceIds) : null;
    this._applyVisibility();
    this._syncSelectionBox();
    if (occurrenceIds?.length) this.focusObjects(occurrenceIds);
  }

  showAll() {
    this.hidden.clear();
    this.isolated = null;
    this._applyVisibility();
    this._syncSelectionBox();
  }

  focusObjects(occurrenceIds) {
    const bbox = this._boundsForIds(occurrenceIds);
    if (!finiteBBox(bbox) || !this.viewer?.ready) return;
    const center = [(bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2];
    const focusSize = Math.max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2], 1e-6);
    const modelSize = finiteBBox(this.bounds)
      ? Math.max(this.bounds[3] - this.bounds[0], this.bounds[4] - this.bounds[1], this.bounds[5] - this.bounds[2], focusSize)
      : focusSize;
    try {
      this.viewer.presetCamera?.('iso', null, false);
      this.viewer.setCameraTarget?.(center, false);
      this.viewer.setCameraZoom?.(Math.max(0.5, Math.min(40, (modelSize / focusSize) * 0.62)), false);
      this.viewer.update?.(true, false);
    } catch {
      const id = occurrenceIds?.[0];
      const path = id ? this.occurrencePaths.get(id) : null;
      try { if (path) this.viewer.setView?.('iso', path); } catch {}
    }
  }

  setRenderMode(mode) {
    if (!['solid', 'edges', 'transparent'].includes(mode)) return false;
    this.renderMode = mode;
    try {
      this.viewer.setTransparent?.(mode === 'transparent', false);
      this.viewer.setBlackEdges?.(mode === 'edges', false);
      this.viewer.update?.(true, false);
    } catch {}
    return true;
  }

  presetView(view) {
    try { this.viewer.presetCamera?.(view, null, true); }
    catch { try { this.viewer.setView?.(view); } catch {} }
  }

  fitAll() {
    if (!this.viewer?.ready) return;
    try {
      this.viewer.centerVisibleObjects?.(false);
      this.viewer.resize?.();
    } catch {
      try { this.viewer.presetCamera?.('iso'); } catch {}
    }
  }

  _clearEvidenceGeometry() {
    for (const object of this.evidenceObjects) {
      try { this.viewer?.scene?.remove(object); } catch {}
      try { object.geometry?.dispose?.(); } catch {}
      try { object.material?.dispose?.(); } catch {}
    }
    this.evidenceObjects = [];
    const annotation = this.host.querySelector('.viewer-annotation');
    if (annotation) annotation.remove();
  }

  _evidenceLinePositions(evidence) {
    const p1 = evidence?.line_start;
    const p2 = evidence?.line_end;
    if (p1?.length === 3 && p2?.length === 3) {
      const bbox = this._boundsForIds(evidence.focus_occurrence_ids || []) || this.bounds;
      const size = finiteBBox(bbox)
        ? Math.max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2], 1) * 0.035
        : 10;
      const positions = [...p1, ...p2];
      for (const point of [p1, p2]) {
        positions.push(
          point[0] - size, point[1], point[2], point[0] + size, point[1], point[2],
          point[0], point[1] - size, point[2], point[0], point[1] + size, point[2],
          point[0], point[1], point[2] - size, point[0], point[1], point[2] + size,
        );
      }
      return positions;
    }
    const axis = { X:[1,0,0], Y:[0,1,0], Z:[0,0,1] }[evidence?.executor_params?.angle_axis];
    const bbox = this._boundsForIds(evidence?.focus_occurrence_ids || []);
    if (axis && finiteBBox(bbox)) {
      const center = [(bbox[0]+bbox[3])/2, (bbox[1]+bbox[4])/2, (bbox[2]+bbox[5])/2];
      const length = Math.max(bbox[3]-bbox[0], bbox[4]-bbox[1], bbox[5]-bbox[2], 1) * 0.7;
      const end = center.map((value, index) => value + axis[index] * length);
      return [...center, ...end];
    }
    return [];
  }

  showEvidenceGeometry(execution) {
    this._clearEvidenceGeometry();
    this.evidence = execution?.evidence || execution || null;
    const positions = this._evidenceLinePositions(this.evidence);
    const THREE = window.THREE;
    if (THREE && positions.length >= 6 && this.viewer?.scene) {
      try {
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        const material = new THREE.LineBasicMaterial({ color: 0xd92d20, depthTest: false, depthWrite: false });
        const lines = new THREE.LineSegments(geometry, material);
        lines.name = 'CADCheckEvidence';
        lines.renderOrder = 10000;
        this.viewer.scene.add(lines);
        this.evidenceObjects.push(lines);
        this.viewer.update?.(true, false);
      } catch (error) {
        console.warn('three-cad Evidence overlay failed', error);
      }
    }
    const text = this.evidence?.annotation || (execution?.value != null ? `${execution.value} ${execution.unit || ''}` : '');
    const annotation = document.createElement('div');
    annotation.className = 'viewer-annotation';
    annotation.textContent = text || '';
    annotation.classList.toggle('hidden', !text);
    this.host.appendChild(annotation);
    this._stampProductUI(true);
  }

  setSectionPlane(plane) {
    this.sectionPlane = plane || null;
    if (!this.viewer?.ready) return;
    if (!plane) {
      try { this.viewer.setLocalClipping?.(false); } catch {}
      return;
    }
    const rawNormal = plane.normal?.length === 3 ? plane.normal.map(Number) : [0, 0, 1];
    const length = Math.hypot(...rawNormal) || 1;
    const normal = rawNormal.map((value) => value / length);
    const point = plane.point?.length === 3 ? plane.point.map(Number) : [0, 0, 0];
    const center = finiteBBox(this.bounds)
      ? [(this.bounds[0]+this.bounds[3])/2, (this.bounds[1]+this.bounds[4])/2, (this.bounds[2]+this.bounds[5])/2]
      : [0, 0, 0];
    const value = normal.reduce((sum, component, index) => sum + component * (center[index] - point[index]), 0);
    try {
      this.viewer.setClipNormal?.(2, normal, value, false);
      this.viewer.setClipIntersection?.(false, false);
      this.viewer.setClipPlaneHelpers?.(false, false);
      this.viewer.setLocalClipping?.(true);
    } catch (error) {
      console.warn('three-cad programmatic clipping failed', error);
    }
  }

  captureView() {
    try {
      this.viewer?.update?.(true, false);
      const canvas = this.viewer?.getCanvas?.();
      return typeof canvas?.toDataURL === 'function' ? canvas.toDataURL('image/png') : null;
    } catch (error) {
      console.warn('three-cad screenshot failed', error);
      return null;
    }
  }

  getViewState() {
    let camera = null;
    try {
      const state = this.viewer?.getCameraLocationSettings?.();
      if (state) camera = { ...state, projection: this.viewer.getCameraType?.() || 'ortho' };
    } catch {}
    return {
      viewer: 'three-cad-proxy-detail-v2',
      camera,
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
    if (!state || (state.viewer && !String(state.viewer).startsWith('three-cad'))) return false;
    this.selected = new Set(state.selected || []);
    this.hidden = new Set(state.hidden || []);
    this.isolated = state.isolated?.length ? new Set(state.isolated) : null;
    this.setRenderMode(state.render_mode || 'solid');
    this._applyVisibility();
    this.setSectionPlane(state.section_plane || null);
    const camera = state.camera;
    if (camera) {
      try {
        if (camera.projection) this.viewer.switchCamera?.(camera.projection === 'ortho', false);
        this.viewer.setCameraLocationSettings?.(
          camera.position || null,
          camera.quaternion || null,
          camera.target || null,
          Number.isFinite(camera.zoom) ? camera.zoom : null,
          false,
        );
      } catch (error) {
        console.warn('three-cad Replay camera restore failed', error);
      }
    }
    this._syncSelectionBox();
    this._stampProductUI(true);
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
      preview_cached_occurrences: this.previewCache.size,
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
    this._clearEvidenceGeometry();
    try { this.viewer?.clear?.(); } catch {}
    this.root = null;
    this.occurrencePaths.clear();
    this.pathOccurrences.clear();
    this.occurrenceBounds.clear();
    this.previewCache.clear();
    this.proxyOccurrences.clear();
    this.previewOccurrences.clear();
    this.detailOccurrences.clear();
    this.detailOrder = [];
    this.selected.clear();
    this.hidden.clear();
    this.isolated = null;
    this.sectionPlane = null;
    this.evidence = null;
    this.bounds = null;
    if (!keepViewer) this._stampProductUI(true);
  }

  dispose() {
    this.resizeObserver?.disconnect?.();
    if (this._resizeRaf) cancelAnimationFrame(this._resizeRaf);
    this._clearEvidenceGeometry();
    try { this.viewer?.dispose?.(); } catch {}
    try { this.display?.dispose?.(); } catch {}
    this.viewer = null;
    this.display = null;
    this.host.replaceChildren();
  }
}
