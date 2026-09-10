# CAD Check MVP 技术方案 V1.1

> V1.1 为 V1.0 增量加固：Electron、Python/OCP、Viewer 可替换等主架构不变，补齐 Canonical AssemblyTree、对象身份、后台 Job、Evidence 可复现信息和硬 Gate，并把 Electron 产品形态提升为不可违反的技术合同。

## 0. 不可违反的产品形态合同

CAD Check MVP 的**唯一产品入口**是 Electron Desktop App。

- `Electron Main` 是产品进程根节点，负责启动/守护/关闭 Python Runtime。
- `Electron Renderer` 是唯一用户界面运行环境；`web/` 只是现有 Renderer 源码目录名。
- FastAPI 只允许作为 Electron 内部 `127.0.0.1` sidecar，不是独立产品服务。
- Standalone Browser 只允许开发调试；任何仅在浏览器中成立的能力一律 **NOT DONE**。
- 功能验收、Viewer Gate、工程师手测、Mac/Windows Smoke 必须从 Electron 启动。
- Electron 启动 sidecar 时必须使用随机 loopback port + session token；用户不管理端口或 URL。
- `./start.sh` / `start.cmd` 必须直接启动 Electron；Uvicorn standalone 入口只能存在于显式标记为 debug-only 的脚本中。

标准启动拓扑：

```text
User
 ↓
Electron App
 ├─ Main: app lifecycle / native OS / runtime supervisor
 ├─ Renderer: CAD Check UX + Viewer
 └─ Python/OCP Runtime @ random 127.0.0.1 port
      └─ internal API only
```

## 1. 技术目标

在不继续自研重型 CAD Viewer 的前提下，构建一个可跨 macOS / Windows 运行的 Electron 桌面工具，并复用现有 Python/OCP Verification Core。

核心原则：

- Electron 是产品容器和进程根，不是几何内核。
- Viewer 是可替换组件，不参与工程真值计算，也不拥有装配树真值。
- Python + OCP/OCCT 是当前确定性 Geometry / Check Runtime。
- Canonical AssemblyTree / Object Identity 独立于 Viewer Mesh。
- Verification Case / Evidence / Replay 与具体 CAD、Viewer 解耦。
- Web 技术可以作为 Renderer 实现，但不得反向定义产品为 Web。

## 2. 总体架构

```text
CAD Check Desktop
│
├─ Electron Main
│  ├─ App 生命周期
│  ├─ 文件打开/保存
│  ├─ Runtime Controller 启停
│  ├─ random localhost port / session token
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

### 2.1 代码目录语义

当前仓库允许保留：

```text
desktop/   Electron Main / preload / runtime supervisor
web/       Electron Renderer source（历史目录名）
server/    Python Runtime / Verification Core
```

`web/` 不表示产品拥有 Web 交付形态。若未来重命名为 `renderer/`，只属于工程整理，不改变架构。

## 3. 进程边界与后台任务

### Electron Main

只做桌面系统职责：

- 拉起并守护 Python Runtime Controller。
- 选择本地 STEP 文件。
- 管理随机 localhost 端口和 session token。
- 对内部 Runtime 请求注入 session token。
- App 退出时关闭 Runtime。
- Runtime/Worker 崩溃时允许从 App 内重启，不带崩 Renderer。
- 统一 cache、workspace、log 路径。

产品启动顺序必须是：

```text
Electron Main
→ reserve random port
→ generate session token
→ spawn Python Runtime
→ /api/health READY
→ create/show product BrowserWindow
```

不能要求用户先手工启动 Python 再打开 Electron。

### Electron Renderer

只做交互和可视化：

- 不直接执行重型 STEP 解析。
- 不直接做工程真值测量。
- 接收 Canonical AssemblyTree 与 Viewer Derivative / Viewer Runtime 数据。
- 调用 Check / Evidence / Replay API。
- 不展示 localhost 地址、端口管理等 Web 产品概念。

### Python Runtime Controller

MVP 继续复用 FastAPI，监听 `127.0.0.1`，通过 localhost HTTP 与 Electron 通信。

当由 Electron 启动时：

- API 必须校验当前 Electron session token。
- sidecar URL 不作为支持的用户入口。
- Renderer/API 开发可通过无 token 的 Standalone Browser debug mode 启动，但该模式不计入任何产品 Gate。

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

控制面验收使用同一 Scania 长任务：Health/Job Status 响应 P95 不高于 1 秒，Cancel 请求 2 秒内得到确认；无法软取消时必须进入明确的 Worker Terminating/Restarting 状态，不能继续显示假进度。

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

身份不变量：

- 同一 `model_sha + import_schema_version` 的重复导入必须生成相同 occurrence ID。
- occurrence ID 不能来自内存地址、遍历数组下标或 Viewer Mesh ID。
- 同一 Prototype 的多个装配实例必须拥有不同 occurrence ID，但可共享 geometry/prototype 引用。
- Evidence 必须保存 `import_schema_version`；版本不兼容时 Replay/Regression fail closed，不做名称猜测绑定。

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
- Viewer benchmark 可以在浏览器中做低层调试，但 Gate 结论必须在 Electron Renderer 中复测后才有效。

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

1. Electron 内 Time To Overview / 首批几何出现时间。
2. 峰值与常驻内存。
3. 加载时旋转/缩放不假死。
4. Canonical Tree 层级可完整展示，不依赖 Mesh 是否已加载。
5. Viewer Pick 能准确返回 occurrence ID。
6. 500+ occurrence Hide/Isolate 稳定，不因批量更新出现整场景空白/消失。
7. FAIL → Evidence 局部 Detail/Highlight 可叠加。
8. 连续切换多个 Case 不出现明显泄漏或场景失效。
9. Windows x64 Electron 可运行。

564 个叶件全部 Detail 是否最终加载完成作为 benchmark 记录项，不作为 MVP 生死 Gate。

若两个候选均未通过 Tree、Pick→occurrence ID、连续交互或 Windows 任一硬项，则 Gate 结果为 `NO WINNER / M0 BLOCKED`，不得为了遵守二选一时间盒强行冻结一个失败实现。

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
        Electron Renderer / Viewer
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
- 首次生成允许慢，但不能阻塞 Electron UI；Warm Open 优先缓存。

## 10. Evidence 数据契约

统一保存：

```json
{
  "evidence_id": "...",
  "run_id": "...",
  "check_set_id": "...",
  "check_set_version": "...",
  "case_id": "...",
  "case_version": "...",
  "rule_maturity": "FORMAL",
  "rule_version": "...",
  "executor_version": "...",
  "model_version": "V2",
  "model_sha": "...",
  "import_schema_version": "...",
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
  "measurement_method": "minimum_distance",
  "executor_params": {},
  "coordinate_system": {
    "id": "vehicle",
    "transform_to_model": [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
  },
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

Regression 的可比键至少包含 Case/Rule/Executor/Measurement Method/单位/坐标系合同和两版 semantic binding。任一项不兼容或绑定无法解析时输出 `NON_COMPARABLE`；不得只靠对象名称、Tree 顺序或 Mesh ID 比较。

## 11. Packaging 与双平台

MVP：

- Electron 负责唯一桌面产品壳和主入口。
- Python Runtime 后期可用 PyInstaller/Nuitka 等打包为 sidecar executable；当前开发期可由 Electron Main 启动 `.venv` Python。
- macOS arm64 在 Mac 构建。
- Windows x64 在 Windows 构建。
- 当前不做签名、notarization、auto-update。
- Standalone Browser 不作为任何平台交付物。

Windows Smoke 必须在 Week 1 完成，不等 Week 3。Smoke 可复用现有最小 Evidence JSON/PNG，不要求在 Week 1 提前完成 Week 2 的完整 Evidence Contract：

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

- 独立 Web 产品化或浏览器交付。
- 继续扩建自研 Web streaming protocol。
- 自研通用 CAD Viewer。
- Electron IPC 全量重写。
- CATIA/CAA 联调。
- Binary Mesh Protocol。
- Windows ARM。
- 云端 CAD Runtime。

## 14. 技术验收 Gate

技术方案通过条件：

1. 唯一产品入口为 Electron；主启动脚本不得直接启动浏览器产品。
2. Electron 在 Mac 与 Windows x64 启动。
3. Windows Week 1 Smoke 全链路通过。
4. Runtime Controller 在 CAD Worker 重任务期间保持 Health/Heartbeat/Job API 响应。
5. Job 支持成功、失败、取消、超时与 Worker Restart。
6. Canonical AssemblyTree 独立于 Viewer Mesh，并通过 Scania 层级回归。
7. Viewer Pick / Visibility / Evidence 均以 occurrence ID 对齐。
8. Minimum Clearance / Directional Distance / Angle 各有至少 1 个可信 Golden Case。
9. FAIL 能自动定位并叠加 Evidence。
10. Scania 级模型完成 Overview / Pick / Hide/Isolate / 固定 occurrence pair Evidence 叠加时 Electron App 不崩溃；该项仅验证规模链路，不作为 FORMAL Check。
11. Viewer 可替换而不改 Verification Core / Evidence Contract。
12. 浏览器调试通过不能替代任何一项 Electron Gate；否则仍为 NOT DONE。
