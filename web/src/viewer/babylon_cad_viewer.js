import {
  ArcRotateCamera,
  Color3,
  Color4,
  Engine,
  HemisphericLight,
  Mesh,
  MeshBuilder,
  Plane,
  PointerEventTypes,
  Quaternion,
  Scene,
  StandardMaterial,
  Vector3,
  VertexData,
} from '@babylonjs/core';

/**
 * Replaceable Electron CAD Viewer adapter.
 *
 * Contract:
 * - Canonical AssemblyTree owns hierarchy and occurrence identity.
 * - Python/OCP owns STEP parsing and engineering truth.
 * - Babylon owns only display/picking/view state.
 * - Whole-vehicle representation is cheap bbox proxies.
 * - Native-OCP detail is admitted on demand under a bounded resident set.
 */
export class BabylonCadViewer {
  constructor(host, {onPick, maxResidentDetails = 24} = {}) {
    this.host = host;
    this.onPick = onPick || (() => {});
    this.maxResidentDetails = maxResidentDetails;

    this.canvas = document.createElement('canvas');
    this.canvas.className = 'babylon-canvas';
    this.canvas.setAttribute('aria-label', 'CAD 3D Viewer');
    this.annotation = document.createElement('div');
    this.annotation.className = 'viewer-annotation hidden';
    host.replaceChildren(this.canvas, this.annotation);

    this.engine = new Engine(this.canvas, true, {
      preserveDrawingBuffer: true,
      stencil: true,
      antialias: true,
    });
    this.scene = new Scene(this.engine);
    this.scene.clearColor = new Color4(0.965, 0.972, 0.98, 1);

    this.camera = new ArcRotateCamera(
      'camera', Math.PI * 0.75, Math.PI * 0.34, 1000, Vector3.Zero(), this.scene,
    );
    this.camera.minZ = 0.1;
    this.camera.maxZ = 1e8;
    this.camera.wheelPrecision = 20;
    this.camera.panningSensibility = 80;
    this.camera.attachControl(this.canvas, true);

    const light = new HemisphericLight('hemi', new Vector3(0.35, 0.8, 0.55), this.scene);
    light.intensity = 0.92;

    this.proxyMaterial = this._material('proxy', new Color3(0.46, 0.54, 0.62), 0.20);
    this.detailMaterial = this._material('detail', new Color3(0.66, 0.70, 0.74), 1.0);
    this.contextMaterial = this._material('context', new Color3(0.68, 0.72, 0.76), 0.16);
    this.selectedMaterial = this._material('selected', new Color3(0.96, 0.58, 0.18), 1.0);
    this.evidenceMaterial = this._material('evidence', new Color3(0.86, 0.18, 0.18), 1.0);

    this.proxies = new Map();
    this.details = new Map();
    this.detailOrder = [];
    this.selected = new Set();
    this.hidden = new Set();
    this.isolated = null;
    this.evidenceMeshes = [];
    this.sectionPlane = null;

    this.scene.onPointerObservable.add((info) => {
      if (info.type !== PointerEventTypes.POINTERPICK) return;
      const pick = info.pickInfo;
      const occurrenceId = pick?.pickedMesh?.metadata?.occurrence_id;
      if (!occurrenceId) return;
      this.onPick(
        occurrenceId,
        pick?.pickedPoint || null,
        Number.isInteger(pick?.faceId) ? {face_id: pick.faceId} : null,
      );
    });

    this._resize = () => this.engine.resize();
    window.addEventListener('resize', this._resize);
    this.engine.runRenderLoop(() => this.scene.render());
  }

  _material(name, color, alpha) {
    const material = new StandardMaterial(name, this.scene);
    material.diffuseColor = color;
    material.specularColor = new Color3(0.12, 0.12, 0.12);
    material.alpha = alpha;
    material.backFaceCulling = false;
    return material;
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

  _applyLocation(mesh, loc) {
    if (!Array.isArray(loc) || loc.length !== 2) return;
    const [position, rotation] = loc;
    if (position?.length === 3) mesh.position.set(position[0], position[1], position[2]);
    if (rotation?.length === 4) {
      mesh.rotationQuaternion = new Quaternion(rotation[0], rotation[1], rotation[2], rotation[3]);
    }
  }

  _extendBounds(current, bbox) {
    if (!current) return [...bbox];
    return [
      Math.min(current[0], bbox[0]), Math.min(current[1], bbox[1]), Math.min(current[2], bbox[2]),
      Math.max(current[3], bbox[3]), Math.max(current[4], bbox[4]), Math.max(current[5], bbox[5]),
    ];
  }

  _frameBounds(bbox) {
    const center = new Vector3(
      (bbox[0] + bbox[3]) / 2,
      (bbox[1] + bbox[4]) / 2,
      (bbox[2] + bbox[5]) / 2,
    );
    const size = Math.max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2], 1);
    this.camera.setTarget(center);
    this.camera.radius = size * 1.7;
  }

  loadOverview(assembly) {
    this.clear();
    const leaves = this._flattenTree(assembly?.roots || []).filter(
      (node) => node.is_leaf !== false && !node.children?.length,
    );
    let bounds = null;

    // Hundreds of proxy boxes are deliberately much cheaper than full CAD
    // detail while still preserving per-occurrence pick/material/visibility.
    for (const node of leaves) {
      const bbox = node.bbox || [];
      if (bbox.length !== 6 || !bbox.every(Number.isFinite)) continue;
      const [xmin, ymin, zmin, xmax, ymax, zmax] = bbox;
      const sx = Math.max(0.1, xmax - xmin);
      const sy = Math.max(0.1, ymax - ymin);
      const sz = Math.max(0.1, zmax - zmin);
      const proxy = MeshBuilder.CreateBox(`proxy:${node.occurrence_id}`, {size: 1}, this.scene);
      proxy.position.set((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2);
      proxy.scaling.set(sx, sy, sz);
      proxy.material = this.proxyMaterial;
      proxy.isPickable = true;
      proxy.metadata = {
        occurrence_id: node.occurrence_id,
        source_path: node.original_path,
        representation: 'proxy',
      };
      this.proxies.set(node.occurrence_id, proxy);
      bounds = this._extendBounds(bounds, bbox);
    }
    if (bounds) this._frameBounds(bounds);
    this._applyVisibilityAndMaterials();
    return {
      occurrences: this.proxies.size,
      representation: 'canonical-bbox-proxy',
      max_resident_details: this.maxResidentDetails,
    };
  }

  _surfaceMesh(part) {
    const positions = Array.from(part.shape?.vertices || []).flat(Infinity).map(Number);
    const indices = Array.from(part.shape?.triangles || []).flat(Infinity).map(Number);
    if (!positions.length || !indices.length) return null;
    const mesh = new Mesh(`detail:${part.occurrence_id}`, this.scene);
    const vertexData = new VertexData();
    vertexData.positions = positions;
    vertexData.indices = indices;
    const normals = Array.from(part.shape?.normals || []).flat(Infinity).map(Number);
    if (normals.length === positions.length) vertexData.normals = normals;
    else {
      const generated = [];
      VertexData.ComputeNormals(positions, indices, generated);
      vertexData.normals = generated;
    }
    vertexData.applyToMesh(mesh, true);
    mesh.material = this.detailMaterial;
    mesh.isPickable = true;
    mesh.metadata = {
      occurrence_id: part.occurrence_id,
      source_path: part.source_path,
      representation: 'detail',
      kind: 'surface',
    };
    this._applyLocation(mesh, part.loc);
    return mesh;
  }

  _edgeMesh(part) {
    const values = Array.from(part.shape?.edges || []).flat(Infinity).map(Number);
    if (values.length < 6 || values.length % 3 !== 0) return null;
    const lines = [];
    for (let index = 0; index + 5 < values.length; index += 6) {
      lines.push([
        new Vector3(values[index], values[index + 1], values[index + 2]),
        new Vector3(values[index + 3], values[index + 4], values[index + 5]),
      ]);
    }
    if (!lines.length) return null;
    const mesh = MeshBuilder.CreateLineSystem(`edges:${part.occurrence_id}`, {lines}, this.scene);
    mesh.color = new Color3(0.24, 0.28, 0.33);
    mesh.isPickable = false;
    mesh.metadata = {
      occurrence_id: part.occurrence_id,
      source_path: part.source_path,
      representation: 'detail',
      kind: 'edge',
    };
    this._applyLocation(mesh, part.loc);
    return mesh;
  }

  loadDetail(payload, {replace = false} = {}) {
    if (replace) this.disposeDetail();
    const parts = this._flattenShapeParts(payload?.shapes || payload?.detail?.shapes || {});
    const loaded = [];
    for (const part of parts) {
      const occurrenceId = part.occurrence_id;
      if (!occurrenceId) continue;
      this._disposeOccurrenceDetail(occurrenceId);
      const meshes = [this._surfaceMesh(part), this._edgeMesh(part)].filter(Boolean);
      if (!meshes.length) continue;
      this.details.set(occurrenceId, meshes);
      this.detailOrder = this.detailOrder.filter((id) => id !== occurrenceId);
      this.detailOrder.push(occurrenceId);
      this.proxies.get(occurrenceId)?.setEnabled(false);
      loaded.push(occurrenceId);
    }
    this._enforceDetailBudget();
    this._applyVisibilityAndMaterials();
    return loaded;
  }

  _disposeOccurrenceDetail(occurrenceId) {
    const meshes = this.details.get(occurrenceId) || [];
    for (const mesh of meshes) mesh.dispose(false, true);
    this.details.delete(occurrenceId);
    this.detailOrder = this.detailOrder.filter((id) => id !== occurrenceId);
    const proxy = this.proxies.get(occurrenceId);
    if (proxy) proxy.setEnabled(true);
  }

  _enforceDetailBudget() {
    let guard = this.detailOrder.length * 2 + 1;
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
    for (const occurrenceId of [...this.details.keys()]) {
      if (!keep.has(occurrenceId)) this._disposeOccurrenceDetail(occurrenceId);
    }
    this._applyVisibilityAndMaterials();
  }

  setSelection(occurrenceIds) {
    const ids = Array.isArray(occurrenceIds) ? occurrenceIds : [occurrenceIds].filter(Boolean);
    this.selected = new Set(ids);
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

  _applyVisibilityAndMaterials() {
    const hasSelection = this.selected.size > 0;
    const ids = new Set([...this.proxies.keys(), ...this.details.keys()]);
    for (const id of ids) {
      const visible = !this.hidden.has(id) && (!this.isolated || this.isolated.has(id));
      const selected = this.selected.has(id);
      const proxy = this.proxies.get(id);
      const detail = this.details.get(id) || [];
      const detailResident = detail.length > 0;
      if (proxy) {
        proxy.setEnabled(visible && !detailResident);
        proxy.material = selected ? this.selectedMaterial : (hasSelection ? this.contextMaterial : this.proxyMaterial);
      }
      for (const mesh of detail) {
        mesh.setEnabled(visible);
        if (mesh.metadata?.kind === 'surface') {
          mesh.material = selected ? this.selectedMaterial : (hasSelection ? this.contextMaterial : this.detailMaterial);
        } else {
          mesh.visibility = selected ? 1.0 : (hasSelection ? 0.25 : 0.75);
          mesh.color = selected ? new Color3(0.96, 0.58, 0.18) : new Color3(0.24, 0.28, 0.33);
        }
      }
    }
  }

  _boundsForIds(occurrenceIds) {
    let bounds = null;
    for (const id of occurrenceIds || []) {
      const proxy = this.proxies.get(id);
      const meshes = (this.details.get(id) || []).filter((mesh) => mesh.metadata?.kind !== 'edge');
      const targets = meshes.length ? meshes : (proxy ? [proxy] : []);
      for (const mesh of targets) {
        mesh.computeWorldMatrix(true);
        const box = mesh.getBoundingInfo().boundingBox;
        const min = box.minimumWorld;
        const max = box.maximumWorld;
        bounds = this._extendBounds(bounds, [min.x, min.y, min.z, max.x, max.y, max.z]);
      }
    }
    return bounds;
  }

  focusObjects(occurrenceIds) {
    const bounds = this._boundsForIds(occurrenceIds);
    if (bounds) this._frameBounds(bounds);
  }

  _clearEvidence() {
    for (const mesh of this.evidenceMeshes) mesh.dispose(false, true);
    this.evidenceMeshes = [];
    this.annotation.textContent = '';
    this.annotation.classList.add('hidden');
  }

  showEvidenceGeometry(execution) {
    this._clearEvidence();
    const evidence = execution?.evidence || execution || {};
    const p1 = evidence.line_start;
    const p2 = evidence.line_end;
    if (p1?.length === 3 && p2?.length === 3) {
      const points = [Vector3.FromArray(p1), Vector3.FromArray(p2)];
      const line = MeshBuilder.CreateLines('__evidence_line__', {points}, this.scene);
      line.color = new Color3(0.86, 0.18, 0.18);
      line.isPickable = false;
      this.evidenceMeshes.push(line);
      const span = Vector3.Distance(points[0], points[1]);
      const radius = Math.max(span * 0.035, this.camera.radius * 0.002, 0.5);
      for (const [index, point] of points.entries()) {
        const marker = MeshBuilder.CreateSphere(`__evidence_point_${index}__`, {diameter: radius * 2}, this.scene);
        marker.position.copyFrom(point);
        marker.material = this.evidenceMaterial;
        marker.isPickable = false;
        this.evidenceMeshes.push(marker);
      }
    } else {
      const axisName = evidence.executor_params?.angle_axis;
      const bounds = this._boundsForIds(evidence.focus_occurrence_ids || []);
      if (axisName && bounds) {
        const center = new Vector3((bounds[0] + bounds[3]) / 2, (bounds[1] + bounds[4]) / 2, (bounds[2] + bounds[5]) / 2);
        const size = Math.max(bounds[3] - bounds[0], bounds[4] - bounds[1], bounds[5] - bounds[2], 1);
        const direction = {X:new Vector3(1,0,0),Y:new Vector3(0,1,0),Z:new Vector3(0,0,1)}[axisName];
        if (direction) {
          const axis = MeshBuilder.CreateLines('__evidence_axis__', {points:[center, center.add(direction.scale(size * 0.55))]}, this.scene);
          axis.color = new Color3(0.86, 0.18, 0.18);
          axis.isPickable = false;
          this.evidenceMeshes.push(axis);
        }
      }
    }
    const text = evidence.annotation || (execution?.value != null ? `${execution.value} ${execution.unit || ''}` : '');
    if (text) {
      this.annotation.textContent = text;
      this.annotation.classList.remove('hidden');
    }
  }

  setSectionPlane(plane) {
    this.sectionPlane = plane || null;
    if (!plane) {
      this.scene.clipPlane = null;
      return;
    }
    const normal = Vector3.FromArray(plane.normal || [0, 0, 1]).normalize();
    const point = Vector3.FromArray(plane.point || [0, 0, 0]);
    this.scene.clipPlane = Plane.FromPositionAndNormal(point, normal);
  }

  captureView() {
    return this.canvas.toDataURL('image/png');
  }

  getViewState() {
    return {
      viewer: 'babylon-native-ocp-v1',
      camera: {alpha:this.camera.alpha,beta:this.camera.beta,radius:this.camera.radius,target:this.camera.target.asArray()},
      selected: [...this.selected],
      hidden: [...this.hidden],
      isolated: this.isolated ? [...this.isolated] : [],
      section_plane: this.sectionPlane,
      resident_detail_occurrences: [...this.details.keys()],
    };
  }

  applyViewState(state) {
    if (!state) return false;
    const camera = state.camera || {};
    if (Number.isFinite(camera.alpha)) this.camera.alpha = camera.alpha;
    if (Number.isFinite(camera.beta)) this.camera.beta = camera.beta;
    if (Number.isFinite(camera.radius)) this.camera.radius = camera.radius;
    if (camera.target?.length === 3) this.camera.setTarget(Vector3.FromArray(camera.target));
    this.selected = new Set(state.selected || []);
    this.hidden = new Set(state.hidden || []);
    this.isolated = state.isolated?.length ? new Set(state.isolated) : null;
    this.setSectionPlane(state.section_plane || null);
    this._applyVisibilityAndMaterials();
    return true;
  }

  hasOccurrence(occurrenceId) {
    return this.proxies.has(occurrenceId) || this.details.has(occurrenceId);
  }

  getStats() {
    return {
      proxy_count: this.proxies.size,
      resident_detail_occurrences: this.details.size,
      resident_detail_meshes: [...this.details.values()].reduce((sum, items) => sum + items.length, 0),
      selected_count: this.selected.size,
      hidden_count: this.hidden.size,
      isolated_count: this.isolated?.size || 0,
      max_resident_details: this.maxResidentDetails,
    };
  }

  clear() {
    for (const meshes of this.details.values()) for (const mesh of meshes) mesh.dispose(false, true);
    for (const proxy of this.proxies.values()) proxy.dispose(false, true);
    this._clearEvidence();
    this.proxies.clear();
    this.details.clear();
    this.detailOrder = [];
    this.selected.clear();
    this.hidden.clear();
    this.isolated = null;
    this.setSectionPlane(null);
  }

  dispose() {
    window.removeEventListener('resize', this._resize);
    this.clear();
    this.scene.dispose();
    this.engine.dispose();
    this.canvas.remove();
    this.annotation.remove();
  }
}
