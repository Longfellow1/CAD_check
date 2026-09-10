# CAD Check MVP 技术方案 V1.0

## 1. 技术目标

在不继续自研重型 CAD Viewer 的前提下，构建一个可跨 macOS / Windows 运行的 Electron 桌面工具，并复用现有 Python/OCP Verification Core。

核心原则：

- Electron 是产品容器，不是几何内核。
- Viewer 是可替换组件，不参与工程真值计算。
- Python + OCP/OCCT 是当前确定性 Geometry / Check Runtime。
- Verification Case / Evidence / Replay 与具体 CAD、Viewer 解耦。

## 2. 总体架构

```text
CAD Check Desktop
│
├─ Electron Main
│  ├─ App 生命周期
│  ├─ 文件打开/保存
│  ├─ CAD Runtime 启停
│  ├─ Job/Cancel
│  ├─ Cache/Log 路径
│  └─ Crash Recovery
│
├─ Electron Renderer
│  ├─ Project / Model UI
│  ├─ 3D Viewer
│  ├─ Check Results
│  ├─ Annotation / Evidence
│  └─ Replay / Regression
│
└─ Python CAD Runtime / Worker
   ├─ STEP/AP242 Reader
   ├─ XCAF / BRep Inventory
   ├─ Geometry Executors
   ├─ Check Engine
   ├─ Regression
   └─ Evidence Geometry
```

## 3. 进程边界

### Electron Main

只做桌面系统职责：

- 拉起并守护 Python Runtime。
- 选择本地 STEP 文件。
- 管理随机 localhost 端口和 session token。
- App 退出时关闭 Runtime。
- Runtime 崩溃时允许重启，不带崩 Renderer。
- 统一 cache、workspace、log 路径。

### Electron Renderer

只做交互和可视化：

- 不直接执行重型 STEP 解析。
- 不直接做工程真值测量。
- 接收 Viewer Derivative / Viewer Runtime 数据。
- 调用 Check / Evidence / Replay API。

### Python CAD Runtime

MVP 继续复用 FastAPI + OCP/OCCT，后续再决定是否收敛到 stdio/socket/IPC。

MVP 通信：

```text
Electron Renderer/Main
      ↓ localhost HTTP + session token
Python FastAPI Runtime
```

只监听 `127.0.0.1`，不绑定外网地址。

## 4. Geometry Backend

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

建议最小接口：

```python
open_model()
get_inventory()
resolve_object()
get_shape()
minimum_clearance()
directional_distance()
angle()
closest_points()
```

Viewer 操作如 visibility/camera 不进入 GeometryBackend，由 Renderer/View State 管理。

## 5. Verification Core

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

结果状态：

- PASS
- FAIL
- REVIEW_REQUIRED
- BLOCKED

Regression 状态：

- NEW_FAIL
- FIXED
- IMPROVED
- REGRESSED
- UNCHANGED
- NON_COMPARABLE

## 6. Viewer 选型

### 已锁定边界

- 不再把 three-cad-viewer 大模型优化作为主研发任务。
- 不采用 FreeCAD / Obsidian 作为宿主。
- Viewer 必须可嵌入 Electron、支持 Assembly / Picking / Visibility / Highlight，并允许我们叠加 Evidence。

### Candidate A：NARU Runtime

优点：

- 面向 massive engineering scene。
- WebGPU。
- Progressive streaming。
- Prototype/Occurrence Instancing。
- 固定 decoded/GPU residency budget。
- Picking、selection、hide/isolate、section 已有。
- Apache-2.0。

风险：

- Alpha。
- Measurement / Annotation 仍需我们补。
- Windows GPU / WebGPU 兼容性需实测。
- 真实大 STEP 直接案例不足。

### Candidate B：cad-3d-viewer / Babylon.js Core

优点：

- 结构简单。
- Assembly tree、visibility、picking、explode、measure、screenshot 已有。
- MIT。
- MVP 改造代码量低。

风险：

- 原始 STEP 导入依赖 occt-import-js/WASM，大模型风险高。
- 缺乏严格的大模型 residency / streaming 机制。

### 选型规则

首日只做 Scania Bake-off，不进入业务开发。

同一模型对比：

1. Time To First Geometry。
2. 峰值内存。
3. 旋转/缩放稳定性。
4. Assembly Tree。
5. Hide / Isolate。
6. Picking。
7. 500+ occurrence 操作。
8. Windows x64 可运行性。
9. 接入 Check Highlight / Annotation 的改造量。

决策：

- NARU 若性能明显占优且 Electron/Windows 稳定 → 选 NARU。
- NARU 若 Alpha 风险阻断，cad-3d-viewer 能稳定达到 MVP → 选 cad-3d-viewer。
- Gate 后冻结 Viewer，不继续横向调研。

## 7. STEP 与 Viewer 数据边界

原则：一个 STEP 不应同时在 Renderer 和 Python Runtime 内重复作为工程真值解析。

推荐：

```text
STEP/AP242
   ↓
Python/OCP Native
   ├─ BRep Truth → Check
   ├─ Assembly / Identity
   └─ Viewer Derivative / Compiled Scene
            ↓
        Electron Viewer
```

Viewer 的交互测量可以存在，但只作为辅助；最终工程数值由 OCP Executor 返回。

## 8. 大模型策略

目标从“整车全部高精度常驻”调整为：

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
- 不需要的 detail 可卸载。
- 首次生成允许慢，但不能阻塞 UI；Warm Open 优先缓存。

## 9. Evidence 数据契约

建议统一：

```json
{
  "evidence_id": "...",
  "case_id": "...",
  "model_version": "V2",
  "objects": ["target-id", "counterpart-id"],
  "result": "FAIL",
  "value": 8.0,
  "unit": "mm",
  "threshold": 10.0,
  "closest_points": [[0,0,0],[0,0,8]],
  "view_state": {
    "camera": {},
    "visible": [],
    "hidden": [],
    "highlight": []
  },
  "annotation": {},
  "trace_id": "..."
}
```

Replay 只重建这个状态，不依赖录屏。

## 10. Packaging

MVP：

- Electron 负责桌面包。
- Python Runtime 后期可用 PyInstaller/Nuitka 等打包成 sidecar executable。
- macOS arm64 在 Mac 构建。
- Windows x64 在 Windows 构建。
- 当前不做签名、notarization、auto-update。

开发阶段允许先通过本地 Python 环境启动 sidecar，待主闭环稳定后再冻结安装包。

## 11. CATIA 后续接入

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

优先能力：

- 当前 Product/Part。
- Assembly Tree。
- 选择/高亮/显隐。
- CATIA 测量对标。
- 对象跳转。
- 必要时 STEP 导出。

只有 COM 能力明显不足时，再评估 CAA。

## 12. 当前禁止投入

- 继续扩建自研 Web streaming protocol。
- 自研通用 CAD Viewer。
- Electron IPC 全量重写。
- CATIA/CAA 联调。
- Binary Mesh Protocol。
- Windows ARM。
- 云端 CAD Runtime。

## 13. 技术验收 Gate

技术方案通过条件：

1. Electron 在 Mac 与 Windows x64 启动。
2. Python Runtime 被 Main 正确拉起、关闭、重启。
3. STEP 能打开并返回 Inventory。
4. Viewer 能稳定完成 Overview / Pick / Hide / Isolate。
5. Minimum Clearance 能由 OCP 精确执行。
6. FAIL 能自动定位并叠加 Evidence。
7. Worker/Runtime 重任务不导致 UI 假死。
8. Scania 级模型不会因一次显隐/选择直接导致应用崩溃。