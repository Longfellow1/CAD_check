import {
  FastNavPlugin,
  LineSet,
  NavCubePlugin,
  SceneModel,
  SectionPlanesPlugin,
  Viewer,
} from '@xeokit/xeokit-sdk';

const BOX_POSITIONS = [
  // front
  -0.5,-0.5, 0.5,  0.5,-0.5, 0.5,  0.5, 0.5, 0.5, -0.5, 0.5, 0.5,
  // right
   0.5,-0.5, 0.5,  0.5,-0.5,-0.5,  0.5, 0.5,-0.5,  0.5, 0.5, 0.5,
  // back
   0.5,-0.5,-0.5, -0.5,-0.5,-0.5, -0.5, 0.5,-0.5,  0.5, 0.5,-0.5,
  // left
  -0.5,-0.5,-0.5, -0.5,-0.5, 0.5, -0.5, 0.5, 0.5, -0.5, 0.5,-0.5,
  // top
  -0.5, 0.5, 0.5,  0.5, 0.5, 0.5,  0.5, 0.5,-0.5, -0.5, 0.5,-0.5,
  // bottom
  -0.5,-0.5,-0.5,  0.5,-0.5,-0.5,  0.5,-0.5, 0.5, -0.5,-0.5, 0.5,
];
const BOX_NORMALS = [
   0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1,
   1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0,
   0, 0,-1, 0, 0,-1, 0, 0,-1, 0, 0,-1,
  -1, 0, 0,-1, 0, 0,-1, 0, 0,-1, 0, 0,
   0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0,
   0,-1, 0, 0,-1, 0, 0,-1, 0, 0,-1, 0,
];
const BOX_INDICES = [
   0, 1, 2,  0, 2, 3,
   4, 5, 6,  4, 6, 7,
   8, 9,10,  8,10,11,
  12,13,14, 12,14,15,
  16,17,18, 16,18,19,
  20,21,22, 20,22,23,
];

const vec = (value) => Array.from(value || []).flat(Infinity).map(Number);
const finiteBBox = (bbox) => Array.isArray(bbox) && bbox.length === 6 && bbox.every(Number.isFinite);

/**
 * xeokit-based CAD Viewer adapter for the Electron product.
 *
 * Engineering contract remains unchanged:
 * - Python/OCP owns STEP parsing and exact engineering truth.
 * - Canonical AssemblyTree owns hierarchy and occurrence identity.
 * - xeokit owns navigation, rendering, picking, sectioning and emphasis only.
 * - Whole vehicle overview is one instanced SceneModel of canonical bbox proxies.
 * - Native OCP detail is loaded per occurrence and evicted with a resident budget.
 */
export class XeokitCadViewer {
  constructor(host, {onPick, maxResidentDetails = 24} = {}) {
    this.host = host;
    this.onPick = onPick || (() => {});
    this.maxResidentDetails = maxResidentDetails;
    this._seq = 0;

    this.canvas = document.createElement('canvas');
    this.canvas.id = `xeokit-cad-${Math.random().toString(36).slice(2)}`;
    this.canvas.className = 'xeokit-canvas';
    this.canvas.setAttribute('aria-label', 'CAD 3D Viewer');

    this.navCanvas = document.createElement('canvas');
    this.navCanvas.width = 130;
    this.navCanvas.height = 130;
    this.navCanvas.className = 'xeokit-navcube';
    this.navCanvas.setAttribute('aria-label', 'CAD view cube');

    this.annotation = document.createElement('div');
    this.annotation.className = 'viewer-annotation hidden';
    this.controls = this._createViewControls();
    // style_v3 keeps legacy viewer roots at height:100%; these two overlay
    // elements must remain content-sized or the control bar becomes a full
    // height layer and visually masks the canvas.
    this.controls.style.height = 'auto';
    this.annotation.style.height = 'auto';
    host.replaceChildren(this.canvas, this.navCanvas, this.controls, this.annotation);

    this.viewer = new Viewer({
      canvasId: this.canvas.id,
      transparent: false,
      dtxEnabled: true,
    });
    this.viewer.camera.projection = 'ortho';
    const cameraControl = this.viewer.cameraControl;
    cameraControl.navMode = 'orbit';
    cameraControl.followPointer = true;
    cameraControl.doublePickFlyTo = true;
    // Match the retired three-cad-viewer controls: left-button rotate,
    // right-button or shift+left pan, middle-button drag zoom, and wheel zoom.
    // xeokit builds its qwerty keyMap before applying panRightClick, so merely
    // changing panRightClick leaves the default map pointing at the wrong
    // button. Set the map explicitly after the config is applied.
    cameraControl.panRightClick = true;
    const input = this.viewer.scene.input;
    cameraControl.keyMap = {
      ...cameraControl.keyMap,
      [cameraControl.MOUSE_PAN]: [
        [input.MOUSE_LEFT_BUTTON, input.KEY_SHIFT],
        input.MOUSE_RIGHT_BUTTON,
      ],
      [cameraControl.MOUSE_ROTATE]: [input.MOUSE_LEFT_BUTTON],
      [cameraControl.MOUSE_DOLLY]: [],
    };
    cameraControl.panInertia = 0;
    cameraControl.rotationInertia = 0;
    cameraControl.dollyInertia = 0;

    // xeokit does not assign a drag action to the middle button. Keep it out
    // of MOUSE_PAN and provide the missing CAD-style middle-drag zoom here.
    // Direct camera updates are intentional: this is presentation state, not
    // an engineering measurement operation.
    let middleDragY = null;
    const zoomByMiddleDrag = (deltaY) => {
      const camera = this.viewer.camera;
      const factor = Math.exp(Math.max(-120, Math.min(120, deltaY)) * 0.006);
      if (camera.projection === 'ortho') {
        camera.ortho.scale = Math.max(0.001, Math.min(1e9, camera.ortho.scale * factor));
        return;
      }
      const look = Array.from(camera.look || [0, 0, 0]);
      const eye = Array.from(camera.eye || [0, 0, 1]);
      const offset = eye.map((value, index) => value - look[index]);
      const distance = Math.hypot(...offset);
      if (!Number.isFinite(distance) || distance <= 1e-6) return;
      const nextDistance = Math.max(0.001, Math.min(1e9, distance * factor));
      camera.eye = look.map((value, index) => value + offset[index] * nextDistance / distance);
    };
    this._onMiddleDown = (event) => {
      if (event.button !== 1) return;
      middleDragY = event.clientY;
      event.preventDefault();
    };
    this._onMiddleMove = (event) => {
      if (middleDragY === null || !(event.buttons & 4)) return;
      const deltaY = event.clientY - middleDragY;
      middleDragY = event.clientY;
      if (deltaY) zoomByMiddleDrag(deltaY);
      event.preventDefault();
    };
    this._onMiddleUp = (event) => {
      if (event.button !== 1) return;
      middleDragY = null;
      event.preventDefault();
    };
    this.canvas.addEventListener('mousedown', this._onMiddleDown);
    document.addEventListener('mousemove', this._onMiddleMove);
    document.addEventListener('mouseup', this._onMiddleUp);

    // Reduce GPU pressure while the camera is moving. This is deliberately a
    // navigation plugin only; it never changes OCP measurement truth.
    this.fastNav = new FastNavPlugin(this.viewer, {
      hideEdges: true,
      hideSAO: true,
      hidePBR: true,
      hideColorTexture: true,
      scaleCanvasResolution: true,
      scaleCanvasResolutionFactor: 0.72,
      defaultScaleCanvasResolutionFactor: 1.0,
      delayBeforeRestore: true,
      delayBeforeRestoreSeconds: 0.35,
    });

    try {
      this.viewer.scene.canvas.backgroundColor = [0.965, 0.972, 0.98];
      const selected = this.viewer.scene.selectedMaterial;
      selected.fill = true;
      selected.fillColor = [1.0, 0.45, 0.05];
      selected.fillAlpha = 0.88;
      selected.edges = true;
      selected.edgeColor = [1.0, 0.28, 0.02];
      selected.edgeAlpha = 1.0;

      const xray = this.viewer.scene.xrayMaterial;
      xray.fill = true;
      xray.fillColor = [0.67, 0.72, 0.78];
      xray.fillAlpha = 0.13;
      xray.edges = true;
      xray.edgeColor = [0.40, 0.45, 0.50];
      xray.edgeAlpha = 0.23;

      const edge = this.viewer.scene.edgeMaterial;
      edge.edgeColor = [0.18, 0.22, 0.27];
      edge.edgeAlpha = 0.70;
    } catch (error) {
      console.warn('xeokit emphasis material setup skipped', error);
    }

    this.sectionPlanes = new SectionPlanesPlugin(this.viewer);
    this.navCube = new NavCubePlugin(this.viewer, {
      canvasElement: this.navCanvas,
      visible: true,
      cameraFly: false,
      cameraFitFOV: 48,
      fitVisible: true,
      synchProjection: true,
      color: '#e8edf2',
      hoverColor: 'rgba(37,99,235,0.35)',
      textColor: '#27313d',
    });

    this.overviewModel = null;
    this.previewModel = null;
    this.previewModels = new Map();
    this.previewEntityIds = new Map();
    this.detailModels = new Map();
    this.detailOrder = [];
    this.proxyEntityIds = new Map();
    this.detailEntityIds = new Map();
    this.entityToOccurrence = new Map();
    this.occurrenceBounds = new Map();
    this.selected = new Set();
    this.hidden = new Set();
    this.isolated = null;
    this.evidenceObjects = [];
    this.sectionPlane = null;
    this.bounds = null;
    this.renderMode = 'solid';

    this._pointerStart = null;
    this._dragged = false;
    this._suppressNextPick = false;

    this._onClick = (event) => {
      if (this._suppressNextPick) {
        this._suppressNextPick = false;
        return;
      }
      const rect = this.canvas.getBoundingClientRect();
      const canvasPos = [event.clientX - rect.left, event.clientY - rect.top];
      const hit = this.viewer.scene.pick({canvasPos, pickSurface: true});
      const entityId = hit?.entity?.id;
      const occurrenceId = this.entityToOccurrence.get(entityId);
      if (!occurrenceId) return;
      this.onPick(
        occurrenceId,
        hit?.worldPos ? Array.from(hit.worldPos) : null,
        Number.isInteger(hit?.primIndex) ? {face_id: hit.primIndex} : null,
      );
    };
    this._onAuxClick = (event) => {
      // Prevent Chromium's auxiliary-click/autoscroll behavior from stealing
      // the CAD pan gesture after xeokit has handled the mouse button.
      if (event.button === 1 || event.button === 2) event.preventDefault();
    };
    this._onContextMenu = (event) => event.preventDefault();
    this.canvas.addEventListener('click', this._onClick);
    this.canvas.addEventListener('auxclick', this._onAuxClick);
    this.canvas.addEventListener('contextmenu', this._onContextMenu);
    this._onMouseDown = (event) => {
      if (event.button !== 0) return;
      this._pointerStart = [event.clientX, event.clientY];
      this._dragged = false;
    };
    this._onMouseMove = (event) => {
      if (!this._pointerStart || !(event.buttons & 1)) return;
      const dx = event.clientX - this._pointerStart[0];
      const dy = event.clientY - this._pointerStart[1];
      if (Math.hypot(dx, dy) > 5) this._dragged = true;
    };
    this._onMouseUp = (event) => {
      if (event.button !== 0) return;
      if (this._dragged) this._suppressNextPick = true;
      this._pointerStart = null;
      this._dragged = false;
    };
    this.canvas.addEventListener('mousedown', this._onMouseDown);
    document.addEventListener('mousemove', this._onMouseMove);
    document.addEventListener('mouseup', this._onMouseUp);

    this._stampProductUI();
  }

  _stampProductUI() {
    const stamp = () => {
      const badge = document.querySelector('#viewer-badge');
      if (badge) badge.textContent = 'XEOKIT · NATIVE OCP · PROXY/DETAIL';
      const status = document.querySelector('#status-viewer');
      if (status?.textContent?.includes('Babylon')) status.textContent = status.textContent.replace(/Babylon/gi, 'xeokit');
      const meta = document.querySelector('#viewer-meta');
      if (meta?.textContent?.includes('Babylon')) meta.textContent = meta.textContent.replace(/Babylon/gi, 'xeokit');
    };
    stamp();
  }

  _createViewControls() {
    const bar = document.createElement('div');
    bar.className = 'xeokit-view-controls';
    const specs = [
      ['fit', '适合窗口'],
      ['iso', 'ISO'],
      ['front', '前'],
      ['right', '右'],
      ['top', '顶'],
      ['projection', '正交'],
      ['render', '渲染：实体'],
    ];
    for (const [action, label] of specs) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.viewAction = action;
      button.textContent = label;
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        if (action === 'fit') this.fitAll();
        else if (action === 'projection') {
          const camera = this.viewer.camera;
          camera.projection = camera.projection === 'ortho' ? 'perspective' : 'ortho';
          button.textContent = camera.projection === 'ortho' ? '正交' : '透视';
        } else if (action === 'render') {
          const modes = ['solid', 'edges', 'transparent'];
          const next = modes[(modes.indexOf(this.renderMode) + 1) % modes.length];
          this.setRenderMode(next);
        } else this.presetView(action);
      });
      bar.appendChild(button);
    }
    const help = document.createElement('span');
    help.className = 'xeokit-view-help';
    help.textContent = '左键旋转 · 右键/Shift+左键平移 · 中键拖拽缩放 · 滚轮缩放';
    bar.appendChild(help);
    return bar;
  }

  _flattenTree(nodes, out = []) {
    for (const node of nodes || []) {
      out.push(node);
      this._flattenTree(node.children, out);
    }
    return out;
  }

  _flattenShapeParts(node, out = []) {
    for (const part of node?.parts || []) {
      if (part?.parts?.length) this._flattenShapeParts(part, out);
      else if (part?.shape) out.push(part);
    }
    return out;
  }

  _extendBounds(current, bbox) {
    if (!finiteBBox(bbox)) return current;
    if (!current) return [...bbox];
    return [
      Math.min(current[0], bbox[0]), Math.min(current[1], bbox[1]), Math.min(current[2], bbox[2]),
      Math.max(current[3], bbox[3]), Math.max(current[4], bbox[4]), Math.max(current[5], bbox[5]),
    ];
  }

  _boundsForIds(occurrenceIds) {
    let bounds = null;
    for (const id of occurrenceIds || []) bounds = this._extendBounds(bounds, this.occurrenceBounds.get(id));
    return bounds;
  }

  _fitBounds(bbox, direction = [1, -1, 0.72], up = [0, 0, 1]) {
    if (!finiteBBox(bbox)) return;
    const center = [
      (bbox[0] + bbox[3]) / 2,
      (bbox[1] + bbox[4]) / 2,
      (bbox[2] + bbox[5]) / 2,
    ];
    const size = [bbox[3]-bbox[0], bbox[4]-bbox[1], bbox[5]-bbox[2]];
    const maxSize = Math.max(...size, 1);
    const length = Math.hypot(...direction) || 1;
    const dir = direction.map((value) => value / length);
    const distance = maxSize * 2.4;
    this.viewer.camera.look = center;
    this.viewer.camera.eye = center.map((value, index) => value + dir[index] * distance);
    this.viewer.camera.up = up;
    if (this.viewer.camera.projection === 'ortho') this.viewer.camera.ortho.scale = maxSize * 1.35;
  }

  fitAll() {
    this._fitBounds(this.bounds);
  }

  presetView(view) {
    const presets = {
      iso:   {dir:[1,-1,0.72], up:[0,0,1]},
      // Scania's longitudinal axis is Y. Keep the CAD convention used by
      // the retired three-cad viewer: front/rear look along Y, left/right
      // look along X, and Z is up. The previous mapping swapped Front and
      // Right, making a right-side view look like a thin, vertically stacked
      // cross-section and giving the impression that the vehicle was split.
      front: {dir:[0,-1,0],    up:[0,0,1]},
      rear:  {dir:[0,1,0],     up:[0,0,1]},
      left:  {dir:[-1,0,0],    up:[0,0,1]},
      right: {dir:[1,0,0],     up:[0,0,1]},
      top:   {dir:[0,0,1],     up:[1,0,0]},
      bottom:{dir:[0,0,-1],    up:[1,0,0]},
    };
    const preset = presets[view] || presets.iso;
    this.viewer.camera.projection = 'ortho';
    this._fitBounds(this.bounds, preset.dir, preset.up);
  }

  loadOverview(assembly) {
    this.clear();
    // A newly opened model must never inherit a section plane from a prior
    // run/replay. Replay is allowed to restore one explicitly afterwards.
    this.setSectionPlane(null);
    const leaves = this._flattenTree(assembly?.roots || []).filter(
      (node) => node.is_leaf !== false && !node.children?.length,
    );
    const model = new SceneModel(this.viewer.scene, {
      id:`cadcheck-overview-${++this._seq}`,
      isModel:true,
      dtxEnabled:true,
    });
    model.createGeometry({
      id:'unit-box',
      primitive:'triangles',
      positions:BOX_POSITIONS,
      normals:BOX_NORMALS,
      indices:BOX_INDICES,
    });

    let bounds = null;
    let count = 0;
    for (const node of leaves) {
      const bbox = node.bbox;
      if (!finiteBBox(bbox)) continue;
      const [xmin,ymin,zmin,xmax,ymax,zmax] = bbox;
      const occurrenceId = node.occurrence_id;
      const meshId = `proxy-mesh-${count}`;
      const entityId = `proxy::${occurrenceId}`;
      model.createMesh({
        id:meshId,
        geometryId:'unit-box',
        position:[(xmin+xmax)/2,(ymin+ymax)/2,(zmin+zmax)/2],
        scale:[Math.max(0.1,xmax-xmin),Math.max(0.1,ymax-ymin),Math.max(0.1,zmax-zmin)],
        color:[0.62,0.68,0.74],
        opacity:0.18,
      });
      model.createEntity({id:entityId,meshIds:[meshId],isObject:true,edges:false,pickable:true});
      this.proxyEntityIds.set(occurrenceId, entityId);
      this.entityToOccurrence.set(entityId, occurrenceId);
      this.occurrenceBounds.set(occurrenceId, [...bbox]);
      bounds = this._extendBounds(bounds, bbox);
      count += 1;
    }
    model.finalize();
    this.overviewModel = model;
    this.bounds = bounds;
    this.presetView('iso');
    this._applyVisibilityAndMaterials();
    this._stampProductUI();
    return {occurrences:count,representation:'xeokit-dtx-instanced-bbox-proxy',max_resident_details:this.maxResidentDetails};
  }

  _createOccurrenceEntity(model, occurrenceId, parts, entityPrefix = 'detail') {
    const isPreview = entityPrefix === 'preview';
    const meshIds = [];
    let index = 0;
    for (const part of parts) {
      const positions = vec(part.shape?.vertices);
      const indices = vec(part.shape?.triangles);
      if (!positions.length || !indices.length) continue;
      const normals = vec(part.shape?.normals);
      const loc = part.loc || [];
      const cfg = {
        id:`${entityPrefix}-mesh-${++this._seq}-${index++}`,
        primitive:'triangles',
        positions,
        indices,
        color:isPreview ? [0.58,0.66,0.74] : [0.72,0.75,0.79],
        opacity:1.0,
      };
      if (normals.length === positions.length) cfg.normals = normals;
      if (Array.isArray(loc[0]) && loc[0].length === 3) cfg.position = loc[0].map(Number);
      if (Array.isArray(loc[1]) && loc[1].length === 4) cfg.quaternion = loc[1].map(Number);
      model.createMesh(cfg);
      meshIds.push(cfg.id);
    }
    if (!meshIds.length) return null;
    const entityId = `${entityPrefix}::${occurrenceId}`;
    model.createEntity({
      id:entityId,
      meshIds,
      isObject:true,
      edges:this.renderMode === 'edges',
      pickable:true,
    });
    return {entityId, meshCount:meshIds.length};
  }

  _createDetailModel(occurrenceId, parts, entityPrefix = 'detail') {
    const model = new SceneModel(this.viewer.scene, {
      id:`cadcheck-detail-${++this._seq}`,
      isModel:false,
      dtxEnabled:true,
      // Imported STEP surfaces are not guaranteed to be watertight.  The
      // compatibility tessellator marks these parts render-back; keep that
      // semantic when they enter xeokit so a cab shell is not half invisible
      // merely because its face winding is inconsistent.
      backfaces:true,
    });
    const created = this._createOccurrenceEntity(model, occurrenceId, parts, entityPrefix);
    if (!created) {
      model.destroy();
      return null;
    }
    model.finalize();
    return {model,entityId:created.entityId};
  }

  _ensurePreviewModel() {
    if (!this.previewModel) {
      this.previewModel = new SceneModel(this.viewer.scene, {
        id:`cadcheck-preview-${++this._seq}`,
        isModel:false,
        dtxEnabled:true,
        // See _createDetailModel: preview geometry must retain open/imported
        // surface faces instead of culling one side of an invalid BRep.
        backfaces:true,
      });
      this._previewFinalized = false;
    }
    return this.previewModel;
  }

  _appendPreviewEntities(grouped) {
    const model = this._ensurePreviewModel();
    const loaded = [];
    for (const [occurrenceId, occurrenceParts] of grouped.entries()) {
      // A user-requested detail model has priority over the medium preview.
      // The shared preview SceneModel stays resident and its entity is hidden
      // while detail is loaded; destroying one SceneModel per leaf was the
      // main long-session source of WebGL churn on Scania.
      if (this.detailModels.has(occurrenceId) || this.previewModels.has(occurrenceId)) continue;
      const created = this._createOccurrenceEntity(model, occurrenceId, occurrenceParts, 'preview');
      if (!created) continue;
      const preview = {model,entityId:created.entityId};
      this.previewModels.set(occurrenceId, preview);
      this.previewEntityIds.set(occurrenceId, preview.entityId);
      this.entityToOccurrence.set(preview.entityId, occurrenceId);
      this.detailOrder = this.detailOrder.filter((id) => id !== occurrenceId);
      loaded.push(occurrenceId);
    }
    if (loaded.length && !this._previewFinalized) {
      // preFinalize is the xeokit-supported progressive-loading path. It
      // makes the first chunk renderable while allowing later chunks to append
      // to the same SceneModel.
      try { model.preFinalize(); } catch (error) { console.warn('preview preFinalize skipped', error); }
    }
    return loaded;
  }

  finishPreview() {
    if (!this.previewModel || this._previewFinalized) return;
    try {
      this.previewModel.finalize();
      this._previewFinalized = true;
    } catch (error) {
      console.warn('preview finalize skipped', error);
    }
  }

  loadDetail(payload, {replace = false} = {}) {
    if (replace) {
      this.disposeDetail();
      this.disposePreview();
    }
    const parts = this._flattenShapeParts(payload?.shapes || payload?.detail?.shapes || {});
    const grouped = new Map();
    for (const part of parts) {
      if (!part.occurrence_id) continue;
      if (!grouped.has(part.occurrence_id)) grouped.set(part.occurrence_id, []);
      grouped.get(part.occurrence_id).push(part);
    }
    const loaded = [];
    for (const [occurrenceId, occurrenceParts] of grouped.entries()) {
      this._disposeOccurrenceDetail(occurrenceId);
      const detail = this._createDetailModel(occurrenceId, occurrenceParts);
      if (!detail) continue;
      this.detailModels.set(occurrenceId, detail);
      this.detailEntityIds.set(occurrenceId, detail.entityId);
      this.entityToOccurrence.set(detail.entityId, occurrenceId);
      this.detailOrder = this.detailOrder.filter((id) => id !== occurrenceId);
      this.detailOrder.push(occurrenceId);
      loaded.push(occurrenceId);
    }
    this._enforceDetailBudget();
    this._applyVisibilityAndMaterials();
    this._stampProductUI();
    return loaded;
  }

  loadPreview(payload) {
    const parts = this._flattenShapeParts(payload?.shapes || payload?.detail?.shapes || {});
    const grouped = new Map();
    for (const part of parts) {
      if (!part.occurrence_id) continue;
      if (!grouped.has(part.occurrence_id)) grouped.set(part.occurrence_id, []);
      grouped.get(part.occurrence_id).push(part);
    }
    const loaded = this._appendPreviewEntities(grouped);
    this._applyVisibilityAndMaterials();
    this._stampProductUI();
    return loaded;
  }

  _disposeOccurrenceDetail(occurrenceId) {
    const detail = this.detailModels.get(occurrenceId);
    if (detail) {
      try { detail.model.destroy(); } catch {}
      this.entityToOccurrence.delete(detail.entityId);
    }
    this.detailModels.delete(occurrenceId);
    this.detailEntityIds.delete(occurrenceId);
    this.detailOrder = this.detailOrder.filter((id) => id !== occurrenceId);
  }

  _disposeOccurrencePreview(occurrenceId) {
    const preview = this.previewModels.get(occurrenceId);
    if (preview) {
      // Preview entities share one progressive SceneModel. They cannot be
      // destroyed independently without tearing down all Scania preview
      // geometry; retire only the identity mapping and hide the entity.
      const entity = this._entityById(preview.entityId);
      if (entity) entity.visible = false;
    }
    this.previewModels.delete(occurrenceId);
    this.previewEntityIds.delete(occurrenceId);
    if (preview) this.entityToOccurrence.delete(preview.entityId);
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
      this._disposeOccurrenceDetail(candidate);
    }
  }

  disposeDetail(except = []) {
    const keep = new Set(except);
    for (const id of [...this.detailModels.keys()]) if (!keep.has(id)) this._disposeOccurrenceDetail(id);
    this._applyVisibilityAndMaterials();
  }

  disposePreview(except = []) {
    const keep = new Set(except);
    if (keep.size) {
      for (const [id, preview] of this.previewModels.entries()) {
        if (keep.has(id)) continue;
        const entity = this._entityById(preview.entityId);
        if (entity) entity.visible = false;
        this.entityToOccurrence.delete(preview.entityId);
        this.previewModels.delete(id);
        this.previewEntityIds.delete(id);
      }
    } else {
      if (this.previewModel) {
        try { this.previewModel.destroy(); } catch {}
      }
      for (const preview of this.previewModels.values()) this.entityToOccurrence.delete(preview.entityId);
      this.previewModels.clear();
      this.previewEntityIds.clear();
      this.previewModel = null;
      this._previewFinalized = false;
    }
    this._applyVisibilityAndMaterials();
  }

  _entityById(entityId) {
    return entityId ? this.viewer.scene.objects[entityId] : null;
  }

  _entitiesForOccurrence(occurrenceId) {
    return [
      this._entityById(this.proxyEntityIds.get(occurrenceId)),
      this._entityById(this.previewEntityIds.get(occurrenceId)),
      this._entityById(this.detailEntityIds.get(occurrenceId)),
    ].filter(Boolean);
  }

  setSelection(occurrenceIds) {
    this.selected = new Set(Array.isArray(occurrenceIds) ? occurrenceIds : [occurrenceIds].filter(Boolean));
    this._enforceDetailBudget();
    this._applyVisibilityAndMaterials();
  }

  setVisibility(occurrenceIds, visible) {
    for (const id of occurrenceIds || []) {
      if (visible) this.hidden.delete(id);
      else this.hidden.add(id);
    }
    this._applyVisibilityAndMaterials();
  }

  isolate(occurrenceIds) {
    this.isolated = occurrenceIds?.length ? new Set(occurrenceIds) : null;
    this._applyVisibilityAndMaterials();
  }

  showAll() {
    this.hidden.clear();
    this.isolated = null;
    this._applyVisibilityAndMaterials();
  }

  setRenderMode(mode) {
    const modes = new Set(['solid', 'edges', 'transparent']);
    if (!modes.has(mode)) return false;
    this.renderMode = mode;
    const button = this.controls.querySelector('[data-view-action="render"]');
    if (button) {
      const label = {solid:'实体',edges:'实体+边线',transparent:'半透明'}[mode];
      button.textContent = `渲染：${label}`;
    }
    this._applyVisibilityAndMaterials();
    return true;
  }

  _applyEntityDisplay(entity) {
    entity.edges = this.renderMode === 'edges';
    entity.opacity = this.renderMode === 'transparent' ? 0.48 : 1.0;
  }

  _applyVisibilityAndMaterials() {
    const hasSelection = this.selected.size > 0;
    for (const occurrenceId of this.proxyEntityIds.keys()) {
      const visible = !this.hidden.has(occurrenceId) && (!this.isolated || this.isolated.has(occurrenceId));
      const selected = this.selected.has(occurrenceId);
      const proxy = this._entityById(this.proxyEntityIds.get(occurrenceId));
      const preview = this._entityById(this.previewEntityIds.get(occurrenceId));
      const detail = this._entityById(this.detailEntityIds.get(occurrenceId));
      if (proxy) {
        this._applyEntityDisplay(proxy);
        proxy.visible = visible && !preview && !detail;
        proxy.selected = selected;
        proxy.xrayed = visible && hasSelection && !selected;
      }
      if (preview) {
        this._applyEntityDisplay(preview);
        preview.visible = visible && !detail;
        preview.selected = selected;
        preview.xrayed = visible && hasSelection && !selected;
      }
      if (detail) {
        this._applyEntityDisplay(detail);
        detail.visible = visible;
        detail.selected = selected;
        detail.xrayed = visible && hasSelection && !selected;
      }
    }
  }

  focusObjects(occurrenceIds) {
    const bbox = this._boundsForIds(occurrenceIds);
    if (bbox) this._fitBounds(bbox);
  }

  _clearEvidence() {
    for (const object of this.evidenceObjects) {
      try { object.destroy(); } catch {}
    }
    this.evidenceObjects = [];
    this.annotation.textContent = '';
    this.annotation.classList.add('hidden');
  }

  showEvidenceGeometry(execution) {
    this._clearEvidence();
    const evidence = execution?.evidence || execution || {};
    const p1 = evidence.line_start;
    const p2 = evidence.line_end;
    if (p1?.length === 3 && p2?.length === 3) {
      const markerSize = Math.max((this.bounds?.[3] - this.bounds?.[0] || 1000) * 0.006, 1);
      const positions = [
        ...p1, ...p2,
        p1[0]-markerSize,p1[1],p1[2], p1[0]+markerSize,p1[1],p1[2],
        p1[0],p1[1]-markerSize,p1[2], p1[0],p1[1]+markerSize,p1[2],
        ...p2, p2[0]+markerSize,p2[1],p2[2],
        p2[0],p2[1]-markerSize,p2[2], p2[0],p2[1]+markerSize,p2[2],
      ];
      this.evidenceObjects.push(new LineSet(this.viewer.scene, {positions,color:[0.86,0.12,0.10],opacity:1.0}));
    } else {
      const axisName = evidence.executor_params?.angle_axis;
      const bbox = this._boundsForIds(evidence.focus_occurrence_ids || []);
      const axis = {X:[1,0,0],Y:[0,1,0],Z:[0,0,1]}[axisName];
      if (axis && bbox) {
        const center = [(bbox[0]+bbox[3])/2,(bbox[1]+bbox[4])/2,(bbox[2]+bbox[5])/2];
        const size = Math.max(bbox[3]-bbox[0],bbox[4]-bbox[1],bbox[5]-bbox[2],1) * 0.65;
        const end = center.map((value,index) => value + axis[index] * size);
        this.evidenceObjects.push(new LineSet(this.viewer.scene, {positions:[...center,...end],color:[0.86,0.12,0.10],opacity:1.0}));
      }
    }
    const text = evidence.annotation || (execution?.value != null ? `${execution.value} ${execution.unit || ''}` : '');
    if (text) {
      this.annotation.textContent = text;
      this.annotation.classList.remove('hidden');
    }
  }

  setSectionPlane(plane) {
    if (this.sectionPlane) {
      try { this.sectionPlane.destroy(); } catch {}
      this.sectionPlane = null;
    }
    if (!plane) return;
    const normal = plane.normal?.length === 3 ? plane.normal.map(Number) : [0,0,1];
    const point = plane.point?.length === 3 ? plane.point.map(Number) : [0,0,0];
    this.sectionPlane = this.sectionPlanes.createSectionPlane({
      id:`cadcheck-section-${++this._seq}`,
      pos:point,
      dir:normal,
    });
  }

  captureView() {
    return this.viewer.getSnapshot({format:'png'});
  }

  getViewState() {
    const camera = this.viewer.camera;
    return {
      viewer:'xeokit-native-ocp-v1',
      camera:{
        eye:Array.from(camera.eye),
        look:Array.from(camera.look),
        up:Array.from(camera.up),
        projection:camera.projection,
        ortho_scale:camera.ortho?.scale,
      },
      selected:[...this.selected],
      hidden:[...this.hidden],
      isolated:this.isolated ? [...this.isolated] : [],
      render_mode:this.renderMode,
      section_plane:this.sectionPlane ? {normal:Array.from(this.sectionPlane.dir),point:Array.from(this.sectionPlane.pos)} : null,
      resident_preview_occurrences:[...this.previewModels.keys()],
      resident_detail_occurrences:[...this.detailModels.keys()],
    };
  }

  applyViewState(state) {
    if (!state || (state.viewer && !String(state.viewer).startsWith('xeokit'))) return false;
    const camera = state.camera || {};
    if (camera.eye?.length === 3) this.viewer.camera.eye = camera.eye;
    if (camera.look?.length === 3) this.viewer.camera.look = camera.look;
    if (camera.up?.length === 3) this.viewer.camera.up = camera.up;
    if (camera.projection) this.viewer.camera.projection = camera.projection;
    if (Number.isFinite(camera.ortho_scale) && this.viewer.camera.ortho) this.viewer.camera.ortho.scale = camera.ortho_scale;
    if (state.render_mode) this.setRenderMode(state.render_mode);
    this.selected = new Set(state.selected || []);
    this.hidden = new Set(state.hidden || []);
    this.isolated = state.isolated?.length ? new Set(state.isolated) : null;
    this.setSectionPlane(state.section_plane || null);
    this._applyVisibilityAndMaterials();
    return true;
  }

  hasOccurrence(occurrenceId) {
    return this.proxyEntityIds.has(occurrenceId)
      || this.previewModels.has(occurrenceId)
      || this.detailModels.has(occurrenceId);
  }

  getStats() {
    return {
      viewer:'xeokit',
      proxy_count:this.proxyEntityIds.size,
      preview_occurrences:this.previewModels.size,
      resident_detail_occurrences:this.detailModels.size,
      selected_count:this.selected.size,
      hidden_count:this.hidden.size,
      isolated_count:this.isolated?.size || 0,
      preview_scene_models:this.previewModel ? 1 : 0,
      render_mode:this.renderMode,
      max_resident_details:this.maxResidentDetails,
      representation:'SceneModel DTX proxy + batched preview + demand detail',
    };
  }

  clear() {
    this.disposeDetail();
    this.disposePreview();
    if (this.overviewModel) {
      try { this.overviewModel.destroy(); } catch {}
      this.overviewModel = null;
    }
    this._clearEvidence();
    this.setSectionPlane(null);
    this.proxyEntityIds.clear();
    this.previewEntityIds.clear();
    this.detailEntityIds.clear();
    this.entityToOccurrence.clear();
    this.occurrenceBounds.clear();
    this.detailOrder = [];
    this.selected.clear();
    this.hidden.clear();
    this.isolated = null;
    this.bounds = null;
  }

  dispose() {
    this.canvas.removeEventListener('click', this._onClick);
    this.canvas.removeEventListener('auxclick', this._onAuxClick);
    this.canvas.removeEventListener('contextmenu', this._onContextMenu);
    this.canvas.removeEventListener('mousedown', this._onMiddleDown);
    document.removeEventListener('mousemove', this._onMiddleMove);
    document.removeEventListener('mouseup', this._onMiddleUp);
    this.canvas.removeEventListener('mousedown', this._onMouseDown);
    document.removeEventListener('mousemove', this._onMouseMove);
    document.removeEventListener('mouseup', this._onMouseUp);
    this._labelObserver?.disconnect();
    this.clear();
    try { this.fastNav?.destroy(); } catch {}
    try { this.navCube?.destroy(); } catch {}
    try { this.sectionPlanes?.destroy(); } catch {}
    try { this.viewer?.destroy(); } catch {}
    this.controls.remove();
    this.annotation.remove();
    this.navCanvas.remove();
    this.canvas.remove();
  }
}
