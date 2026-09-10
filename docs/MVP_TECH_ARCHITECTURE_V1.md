# CAD Check MVP 技术方案 V1.1

> V1.1 为 V1.0 增量加固：Electron、Python/OCP、Viewer 可替换等主架构不变，补齐 Canonical AssemblyTree、对象身份、后台 Job、Evidence 可复现信息和硬 Gate。

## 1. 技术目标

在不继续自研重型 CAD Viewer 的前提下，构建一个可跨 macOS / Windows 运行的 Electron 桌面工具，并复用现有 Python/OCP Verification Core。

核心原则：

- Electron 是产品容器，不是几何内核。
- Viewer 是可替换组件，不参与工程真值计算，也不拥有装配树真值。
- Python + OCP/OCCT 是当前确定性 Geometry / Check Runtime。
- Canonical AssemblyTree / Object Identity 独立于 Viewer Mesh。
- Verification Case / Evidence / Replay 与具体 CAD、Viewer 解耦。

## 2. 总体架构

```text
CAD Check Desktop
│
├─ Electron Main
│  ├─ App 生命周期
│  ├─ 文件打开/保存
│  ├─ Runtime Controller 启停
│  ├─ Job / Cancel / Restart
│  ├─ Cache / Log 路径
│  └─ Crash Recovery
│
├─ Electron Renderer
│  ├─ Project / Model UI
│  ├─ Canonical AssemblyTree UI
│  ├─ 3D Viewer
│  ├─ Check Results
│  ├─ Annotation / Evidence
│  └─ Replay / Regression
│
└─ Python Runtime
   ├─ Runtime Controller / FastAPI
   │  ├─ Health / Heartbeat
   │  ├─ Job State
   │  └─ Worker Lifecycle
   └─ CAD Worker Process
      ├─ STEP/AP242 Reader
      ├─ XCAF / BRep Inventory
      ├─ Canonical AssemblyTree
      ├─ Geometry Executors
      ├─ Check Engine
      └─ Evidence Geometry
```

## 3. 进程边界与后台任务

### Electron Main

只做桌面系统职责：

- 拉起并守护 Python Runtime Controller。
- 选择本地 STEP 文件。
- 管理随机 localhost 端口和 session token。
- App 退出时关闭 Runtime。
- Runtime/Worker 崩溃时允许重启，不带崩 Renderer。
- 统一 cache、workspace、log 路径。

### Electron Renderer

只做交互和可视化：

- 不直接执行重型 STEP 解析。
- 不直接做工程真值测量。
- 接收 Canonical AssemblyTree 与 Viewer Derivative / Viewer Runtime 数据。
- 调用 Check / Evidence / Replay API。

### Python Runtime Controller

MVP 继续复用 FastAPI，监听 `127.0.0.1`，通过 localhost HTTP + session token 与 Electron 通信。

Controller 必须与重型 CAD Worker 分离，保证即使某个 OCCT 任务长时间运行，以下接口仍可响应：

- health / heartbeat。
- job status。
- cancel。
- worker restart。

### CAD Worker Process

所有可能长时间阻塞的 STEP/XCAF、Tessellation、复杂 Geometry Check 均进入 Worker Process。

Job 最小状态机：

```text
QUEUED
  ↓
RUNNING
  ├─ SUCCEEDED
  ├─ FAILED
  ├─ CANCELLED
  └─ TIMED_OUT
```

每个 Job 至少返回：

- `job_id`
- `state`
- `progress_phase`
- `message`
- `started_at / updated_at`
- `error_code / error_message`（失败时）

Progress 不要求虚构精确百分比；STEP/XCAF 无可靠细粒度回调时，使用阶段型 Progress，例如 `READING / INVENTORY / TESSELLATING / CHECKING / FINALIZING`。

若底层 OCCT 调用无法安全软取消，Cancel 允许终止 CAD Worker 并重启，由 Controller 保持可用。

## 4. Canonical AssemblyTree 与对象身份

AssemblyTree 是 P0 工程数据骨架，必须由 XCAF/STEP 原生结构生成，不从 Viewer Scene 反推。

最小节点 Schema：

```json
{
  "occurrence_id": "occ:...",
  "parent_id": "occ:...",
  "name": "original-name",
  "original_path": ["root", "subasm", "part"],
  "geometry_ref": "geom:...",
  "transform": [16],
  "is_leaf": true
}
```

对象身份分三层：

- `geometry_ref`：单次导入中的几何实体引用，可随重新解析变化。
- `occurrence_id`：模型版本内稳定的装配 occurrence 身份，Tree / Viewer / Evidence 必须统一使用。
- `semantic_binding_id`：跨 V1/V2 用于工程绑定的业务身份；MVP 可人工映射，自动 Semantic Binding 放 P1。

Viewer Geometry Chunk 只持有 `occurrence_id → mesh/prototype` 映射，不拥有父子关系。

Scania 当前已知结构基线作为回归项：

- 644 occurrences。
- 80 个父节点。
- 564 个叶件。
- 最大深度 5。

在同一输入/解析基线下，Canonical AssemblyTree 不允许退化为 564 个扁平 root parts；若源解析结果变化，必须显式记录原因而不是静默扁平化。

## 5. Geometry Backend

当前实现：

```text
CadAdapter / GeometryBackend
└─ OcpAdapter
```

预留但不实现：

```text
└─ CatiaComAdapter   # P1
└─ NxAdapter         # Future
└─ CreoAdapter       # Future
```

最小接口：

```python
open_model()
get_inventory()
get_assembly_tree()
resolve_object()
get_shape()
minimum_clearance()
directional_distance()
angle()
closest_points()
```

Viewer 操作如 visibility/camera 不进入 GeometryBackend，由 Renderer/View State 管理。

## 6. Verification Core

保持 CAD-independent：

```text
RuleSource
   ↓
VerificationCase
   ↓
Executor
   ↓
ExecutionResult
   ↓
Evidence
   ↓
Regression / Replay
```

Rule Maturity：

- FORMAL
- PROVISIONAL
- EXPLORATORY

结果状态：

- PASS
- FAIL
- REVIEW_REQUIRED
- BLOCKED

仅 FORMAL Case 可以输出正式 PASS/FAIL 并进入正式 Regression。

Regression 状态：

- NEW_FAIL
- FIXED
- IMPROVED
- REGRESSED
- UNCHANGED
- NON_COMPARABLE

## 7. Viewer 选型

### 已锁定边界

- 不再把 three-cad-viewer 大模型优化作为主研发任务。
- 不采用 FreeCAD / Obsidian 作为宿主。
- Viewer 必须可嵌入 Electron，消费 Canonical AssemblyTree/Object Identity，支持 Picking / Visibility / Highlight，并允许叠加 Evidence。
- 冻结的是 Viewer Interface / Architecture，不是永久冻结某个开源项目；候选不达 Gate 可替换，但 Verification Core 不变。

### Candidate A：NARU Runtime

优点：massive engineering scene、WebGPU、Progressive streaming、Instancing、resident budget、Picking/selection/hide/isolate/section、Apache-2.0。

风险：Alpha；Measurement/Annotation 需补；Windows GPU/WebGPU 兼容需实测；真实大 STEP 案例不足。

### Candidate B：cad-3d-viewer / Babylon.js Core

优点：结构简单；Assembly/visibility/picking/explode/measure/screenshot 已有；MIT；MVP 改造量低。

风险：原始 STEP 导入依赖 occt-import-js/WASM，大模型风险高；缺乏严格 residency/streaming 机制。

### Viewer 最小接口

```text
loadOverview()
setSelection(occurrence_id)
setVisibility(occurrence_ids, visible)
isolate(occurrence_ids)
focusObjects(occurrence_ids)
showEvidenceGeometry(evidence)
captureView()
disposeDetail()
```

### Gate 0 通过线

同一模型至少验证：

1. Time To Overview / 首批几何出现时间。
2. 峰值与常驻内存。
3. 加载时旋转/缩放不假死。
4. Canonical Tree 层级可完整展示，不依赖 Mesh 是否已加载。
5. Viewer Pick 能准确返回 occurrence ID。
6. 500+ occurrence Hide/Isolate 稳定，不因批量更新出现整场景空白/消失。
7. FAIL → Evidence 局部 Detail/Highlight 可叠加。
8. 连续切换多个 Case 不出现明显泄漏或场景失效。
9. Windows x64 可运行。

564 个叶件全部 Detail 是否最终加载完成作为 benchmark 记录项，不作为 MVP 生死 Gate。

## 8. STEP 与 Viewer 数据边界

原则：一个 STEP 不应同时在 Renderer 和 Python Runtime 内重复作为工程真值解析。

推荐：

```text
STEP/AP242
   ↓
Python/OCP Native
   ├─ BRep Truth → Check
   ├─ Canonical AssemblyTree / Identity
   └─ Viewer Derivative / Compiled Scene
            ↓ occurrence_id mapping
        Electron Viewer
```

Viewer 的交互测量可以存在，但只作为辅助；最终工程数值由 OCP Executor 返回。

## 9. 大模型策略

```text
Overview：整车粗览
Detail：按需加载
Evidence：局部高精度
```

要求：

- Assembly/Hierarchy 可先于高精几何可用。
- 重复零件优先 Instancing。
- Overview 默认 Edge OFF。
- Evidence 局部 Edge ON。
- Renderer 设置 resident geometry budget。
- 不需要的 Detail 可卸载。
- 首次生成允许慢，但不能阻塞 UI；Warm Open 优先缓存。

## 10. Evidence 数据契约

统一保存：

```json
{
  "evidence_id": "...",
  "case_id": "...",
  "rule_version": "...",
  "executor_version": "...",
  "model_version": "V2",
  "model_sha": "...",
  "binding_snapshot": {
    "target": "occ:...",
    "counterpart": "occ:...",
    "semantic_binding_ids": []
  },
  "result": "FAIL",
  "value": 8.0,
  "unit": "mm",
  "source_unit": "mm",
  "threshold": 10.0,
  "tolerance": 0.1,
  "coordinate_system": "vehicle",
  "closest_points": [[0,0,0],[0,0,8]],
  "view_state": {
    "camera": {},
    "visible": [],
    "hidden": [],
    "highlight": []
  },
  "annotation": {},
  "trace_id": "...",
  "runtime_version": "...",
  "kernel_version": "..."
}
```

Replay 只重建工程状态，不依赖录屏。

## 11. Packaging 与双平台

MVP：

- Electron 负责桌面包。
- Python Runtime 后期可用 PyInstaller/Nuitka 等打包为 sidecar executable。
- macOS arm64 在 Mac 构建。
- Windows x64 在 Windows 构建。
- 当前不做签名、notarization、auto-update。

Windows Smoke 必须在 Week 1 完成，不等 Week 3：

`Electron → Runtime → 小 STEP → Minimum Clearance → Evidence → Worker/Runtime Restart → 正常退出`

同时覆盖：中文路径、缓存/临时目录、Python/OCP DLL、GPU/Viewer 基础启动。

## 12. CATIA 后续接入

MVP 不实现 CATIA。

P1 在 Windows 增加：

```text
Electron
  ↓
CAD Runtime
  ↓
CatiaComAdapter
  ↓ Python + COM/Automation
CATIA
```

优先能力：当前 Product/Part、Assembly Tree、选择/高亮/显隐、CATIA 测量对标、对象跳转、必要时 STEP 导出。只有 COM 能力明显不足时，再评估 CAA。

## 13. 当前禁止投入

- 继续扩建自研 Web streaming protocol。
- 自研通用 CAD Viewer。
- Electron IPC 全量重写。
- CATIA/CAA 联调。
- Binary Mesh Protocol。
- Windows ARM。
- 云端 CAD Runtime。

## 14. 技术验收 Gate

技术方案通过条件：

1. Electron 在 Mac 与 Windows x64 启动。
2. Windows Week 1 Smoke 全链路通过。
3. Runtime Controller 在 CAD Worker 重任务期间保持 Health/Heartbeat/Job API 响应。
4. Job 支持成功、失败、取消、超时与 Worker Restart。
5. Canonical AssemblyTree 独立于 Viewer Mesh，并通过 Scania 层级回归。
6. Viewer Pick / Visibility / Evidence 均以 occurrence ID 对齐。
7. Minimum Clearance / Directional Distance / Angle 各有至少 1 个可信 Golden Case。
8. FAIL 能自动定位并叠加 Evidence。
9. Scania 级模型完成 Overview / Pick / Hide/Isolate / Evidence 定位时应用不崩溃。
10. Viewer 可替换而不改 Verification Core / Evidence Contract。