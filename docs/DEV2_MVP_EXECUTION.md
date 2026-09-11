# dev-2 MVP Execution Goal

> 本文件是 dev-2 的执行清单，不重新定义四份 V1.1 产品合同。四份核心 MD 仍是需求真源；本清单只用于防止开发过程偏航。

## /goal

在 `dev-2` 上完成 PRD V1.1 所要求的可实现模块，并在交给本地手测前满足自动化开发 Gate：

`Electron Desktop → local STEP/AP242 → Canonical AssemblyTree → isolated CAD Worker Job → 3 Executors / 18 Coverage Cases → FAIL auto focus → Evidence → Replay → V1/V2 Regression`

同时保证：

- 唯一产品入口仍是 Electron；Web 仅为 Renderer 技术。
- Python/OCP/OCCT 是工程真值；Viewer 不解析 STEP、不参与工程判定。
- 大模型采用 Proxy Overview + Demand Detail，禁止恢复“全车所有 Detail 顺序加载并永久常驻”。
- Runtime Controller 与 CAD Worker 进程隔离；长任务可观察、可取消、可超时、可恢复。
- Canonical AssemblyTree / occurrence identity 独立于 Viewer。
- 失败不得被 UI/CI 的绿色状态掩盖；未验证项必须明确保留为 Gate。

## /list

### P0 — Architecture & Runtime

- [x] Runtime Controller / CAD Worker 独立进程闭环
- [x] Job 状态：QUEUED / RUNNING / SUCCEEDED / FAILED / CANCELLED / TIMED_OUT
- [x] Progress phase / heartbeat age / cancel / timeout / worker restart
- [x] Electron Main 管理 Runtime 生命周期；退出无残留 sidecar/worker
- [x] Electron Desktop 禁止调用 legacy synchronous heavy CAD endpoints

### P0 — Model / Identity / Readiness

- [x] Electron 原生打开本地 STEP，不走 Web upload
- [x] Canonical AssemblyTree 保留 parent-child / path / transform / bbox / geometry_ref
- [x] `occurrence_id` 对同一 Model SHA + import schema 确定性复现
- [x] Readiness 区分 preview 与 engineering check；局部坏 B-Rep / binding 只阻断受影响 Case
- [x] Replay 校验 model_sha + import_schema_version + occurrence_id，不按名称猜测

### P0 — Verification / Evidence / Regression

- [x] Minimum Clearance Golden
- [x] Directional Distance Golden
- [x] Angle / Orientation Golden
- [x] 15–25 Coverage Cases 仅依赖 3 个 Executor
- [x] 单 Case + Check Set
- [x] FAIL / REVIEW_REQUIRED 自动定位、标注、Evidence、截图、View State
- [x] Evidence 记录 Run / Check Set / Case / model SHA / binding / rule / method / executor / coordinate / unit / tolerance / runtime
- [x] Replay 恢复工程状态；不兼容时降级为结构化记录 + 原截图
- [x] Regression 严格可比；不兼容输出 NON_COMPARABLE，不整批误杀其它 Case

### P0 — Viewer

- [x] `three-cad-viewer` 不再是产品 Renderer 依赖
- [x] Babylon 退出产品依赖；xeokit SDK 进入 dev-2 Viewer Trial
- [x] Xeokit Viewer Adapter 满足 loadOverview / selection / visibility / isolate / focus / section / evidence / capture / replay state
- [x] Overview 使用 xeokit `SceneModel` + DTX + shared unit-box instancing，Canonical bbox 作为轻量整车代理
- [x] Detail 继续由 Python/OCP 按需生成；Viewer resident budget 限制常驻 detail，不随叶件数量无限增长
- [x] 复用 xeokit CameraControl / NavCube / SectionPlanes / selection/xray/edge emphasis，不重复手搓通用 3D 能力
- [x] 选中结果默认目标高亮 + Context X-Ray；Isolate 仅由用户显式触发
- [x] Regression 单 Viewer V1/V2 切换
- [ ] xeokit 最终冻结：必须通过本地 Scania 规模与 CAD 交互体验 Gate 后才能从 Trial 升级为 Frozen

### Automated delivery Gate

- [x] Python full suite green
- [x] Renderer production build green
- [x] Electron Main/runtime Node tests green
- [x] Electron controlled-flow E2E：FAIL → Evidence → Replay → Regression green
- [x] macOS CI smoke green
- [x] Windows x64 CI smoke green
- [x] Ubuntu integration CI green
- [x] Product-form guard：browser-only / legacy viewer / sync heavy path 回归会直接失败
- [ ] Xeokit migration CI：Linux / macOS / Windows Electron E2E 必须确认 `viewer=xeokit` 后才可交付本地手测

### Physical / business Gate（交付后由真实环境完成）

- [ ] G2：目标工程师无开发者代操作手测
- [ ] G3：本地约 295MB Scania Electron Scale Gate
- [ ] G4：真实 Windows GPU/中文路径补充手测（CI 之外）

## Xeokit Trial 边界

当前 xeokit 使用定位为 **企业内部 MVP/技术验证**：

- 使用官方 `@xeokit/xeokit-sdk` npm 包，不修改 xeokit SDK 源码。
- 不将 xeokit 作为 STEP/BRep 真值层；只作为 Electron Renderer 的显示与交互依赖。
- Python/OCP、规则、Evidence、Replay、Canonical Identity 与 xeokit 解耦，保留 Viewer 可替换性。
- 当前按 AGPL 内部验证边界使用；若进入外部分发、客户/供应商安装、SaaS/网络服务或正式闭源商业交付，必须重新进行 License Review，必要时切换 xeokit 商业许可。

## Delivery rule

只有 Automated delivery Gate 全绿后，才向本地手测交付新的 `dev-2 HEAD`。物理 Scania 与目标工程师 Gate 不伪造为 CI 已完成；交付版本必须提供明确的 Electron 手测清单和判定标准。
