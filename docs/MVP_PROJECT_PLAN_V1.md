# CAD Check MVP 项目排期 V1.1

> V1.1 为 V1.0 增量加固：总体 3–4 周节奏不变，只把 Windows Smoke、Canonical AssemblyTree、后台 Job 和 Golden Gate 前置为硬验收。

## 1. 项目目标

用 3–4 周完成一个可在 macOS / Windows x64 运行的 Electron MVP，验证：

`STEP → 自动检测 → 自动定位/标注 → Evidence → Replay → V1/V2 Regression`

排期原则：

- Viewer Gate 首轮关闭，之后冻结接口，不持续横向调研。
- Windows 基础链路 Week 1 必须通过，不拖到 Week 3 首次验证。
- 先证明工程真值，再扩大到 15–25 条 Coverage Case。
- Scania 只承担复杂模型规模/稳定性 Gate，不作为规则真值。
- 不把生产级 Viewer、CATIA、企业基建带入 MVP。

## 2. 总体节奏

```text
D0–D2   Viewer Bake-off + Electron/Windows Smoke
W1      Desktop Shell + Canonical Tree/Identity + Runtime Job
W2      3 Executor Golden + Auto Annotation + Evidence
W3      Replay + Regression + 15–25 Case Coverage + 双平台完整闭环
W4      Scania/真实工程案例收口与 Buffer（如需要）
```

3 周为挑战目标，第 4 周作为真实数据、Windows 差异和 Scania 稳定性 Buffer，不新增大功能。

## 3. Gate 0：Viewer 选型（0.5–1 天）

### 目标

关闭 NARU vs cad-3d-viewer 首轮选型，不开发业务功能。

### 输入

- 小型 Controlled STEP。
- Scania 约 295MB STEP。
- Mac M4 Pro 24GB。
- Windows x64 验证机。

### 测试项

- Electron 内运行。
- Time To Overview / 首批几何时间。
- 峰值与常驻内存。
- 加载时旋转/缩放稳定性。
- Canonical Tree 可独立显示完整层级。
- Pick → occurrence ID 映射。
- 500+ occurrence Hide / Isolate。
- FAIL Evidence Highlight/Detail 可扩展性。
- 连续切换多个对象/Case 不出现整场景空白或失效。
- Windows x64 可运行性。

### Scania 树回归基线

在同一解析基线下检查：

- 644 occurrences。
- 80 个父节点。
- 564 个叶件。
- 最大深度 5。

不允许 Canonical Tree/Viewer UI 再退化成 564 个扁平 root parts。

### 决策

- NARU 性能/稳定性明显占优且 Electron/Windows Gate 通过 → NARU。
- NARU Alpha / WebGPU 风险阻断，cad-3d-viewer 达到 MVP 稳定线 → cad-3d-viewer。
- Gate 后冻结 Viewer Interface；后续候选若失败可替换实现，但不改 Verification Core。

### Exit Criteria

- 保留一个主 Viewer 实现。
- 输出 benchmark 结果。
- Viewer 最小接口冻结。
- 不再扩建自研通用 Viewer 基建。

## 4. Gate 0B：Windows Smoke（D1–D2，硬 Gate）

Week 1 不结束前必须在 Windows x64 跑通：

`Electron 启动 → Python Runtime 启动 → 小 STEP → Minimum Clearance → Evidence → Worker/Runtime Restart → 正常退出`

同时覆盖：

- Python/OCP DLL。
- sidecar 启停。
- 临时目录/缓存目录。
- 中文路径与基础长路径。
- GPU / WebGL 或 WebGPU 基础启动。

若此 Gate 不通过，M1 不允许标记完成。

## 5. Week 1：桌面、数据骨架与 Runtime

### 目标

完成“Electron 可运行 + Canonical Tree/Identity 成立 + OCP 重任务不阻塞控制面”。

### Electron

- Main / Renderer 基础工程。
- 本地文件选择。
- Runtime Controller 启停。
- localhost 随机端口 + session token。
- Runtime health / heartbeat / restart。

### Canonical AssemblyTree / Identity

- XCAF → Canonical AssemblyTree。
- occurrence ID / parent-child / original path / geometry reference / transform。
- Tree 与 Viewer occurrence 映射。
- geometry_ref / occurrence_id / semantic_binding_id 三层身份边界。
- Scania 树回归测试加入自动/半自动验证。

### Runtime Job

- Controller 与 CAD Worker Process 分离。
- Job 状态：QUEUED / RUNNING / SUCCEEDED / FAILED / CANCELLED / TIMED_OUT。
- 阶段型 Progress。
- Cancel。
- Heartbeat。
- Worker Crash/Timeout Restart。
- 已知超长 Tessellation 不允许阻塞 health/job API。

### Week 1 验收 / M1

Mac：

`Electron → STEP → Canonical Tree → Viewer → Pick occurrence → OCP Minimum Clearance`

Windows：必须通过 Gate 0B Smoke。

同时满足：

- UI 不因 OCP 重任务假死。
- Runtime Controller 在 Worker 忙时仍可响应。
- Worker 可失败/取消/重启。
- Tree 不依赖 Mesh 是否已加载。

## 6. Week 2：Golden Check + Auto Annotation + Evidence

### 目标

证明 3 类 Executor “算得对”，并完成核心产品闭环。

### Golden Case

3 个 Executor 各至少 1 个 FORMAL Golden：

1. Minimum Clearance。
2. Directional Distance。
3. Angle / Orientation。

每个 Golden 必须记录：

- A/B 具体对象/必要的 Face/Sub-shape。
- Measurement Method。
- Coordinate System。
- Unit / Tolerance。
- Truth Source / 操作来源。

信息不完整的案例标记 PROVISIONAL/EXPLORATORY，不进入 Golden。

### Verification

- 单 Case + Batch Run。
- FORMAL / PROVISIONAL / EXPLORATORY。
- PASS / FAIL / REVIEW_REQUIRED / BLOCKED。

### Auto Focus / Annotation

FAIL 自动：

- occurrence ID 定位。
- isolate / context 弱化。
- highlight。
- Frame Camera。
- closest-points / distance / direction / angle marker。
- value / threshold / margin。

### Evidence

Evidence 至少保存：

- Model SHA / Model Version。
- Rule Version / Executor Version。
- Binding Snapshot。
- occurrence IDs。
- Value / Threshold / Unit / Source Unit / Tolerance / Coordinate System。
- Geometry Evidence。
- Camera / Visibility / Highlight。
- Screenshot / Trace / Runtime-Kernel Version。

### Week 2 验收 / M2

- 3 个 Golden 在约定公差内通过。
- FORMAL FAIL 一键进入 Evidence。
- Evidence 不需要人工重新选择对象才能复核。
- 保存后可完整重建关键工程上下文。

## 7. Week 3：Replay / Regression / Coverage / 双平台

### Replay

恢复：

- Model Version。
- occurrence selection。
- Camera。
- Visibility / Isolate。
- Highlight。
- Annotation / Measurement。
- Evidence。

### Regression

- V1 / V2 同一 FORMAL Check Set。
- NEW_FAIL / FIXED / IMPROVED / REGRESSED / UNCHANGED / NON_COMPARABLE。
- V1/V2 Evidence 切换。
- Delta 展示。

### Coverage Matrix

扩展到 15–25 条真实风格 Case，建立：

| Case | Maturity | Executor | Binding | Input Objects | Threshold/Tolerance | Expected | Evidence Type |
|---|---|---|---|---|---|---|---|

目标是证明 3 个 Executor 能复用覆盖多条规则，不允许演化为 15–25 套定制 Python。

### Windows 完整闭环

同一 Controlled V1/V2：

`打开 → Run → FAIL → Evidence → Replay → Regression`

### Week 3 验收 / M3

- Replay 可恢复工程状态。
- Regression 结果稳定。
- Coverage Matrix 完整。
- Mac / Windows 同一闭环均通过。

## 8. Week 4：Scania / 真实工程案例收口 Buffer

仅在前三周核心闭环成立后进入。

重点：

- Scania Overview / Pick / Hide-Isolate / Evidence 定位稳定性。
- Warm Open / Cache。
- 连续 Case 切换内存泄漏。
- 无效 B-Rep 降级。
- Windows 差异问题。
- 一个真实且具备明确真值的工程间隙案例收口。
- 演示脚本和证据补齐。

不新增复杂 Executor、CATIA、AI Rule Compiler 或通用 CAD 编辑能力。

## 9. MVP 里程碑

| Milestone | 时间 | 通过标准 |
|---|---|---|
| M0 Viewer Architecture Freeze | D1–D2 | Viewer 主实现 + 接口冻结；Scania Gate 有记录 |
| M1 Desktop/Runtime Loop | W1 | Canonical Tree + Job Runtime + Mac Loop + Windows Smoke |
| M2 Trusted Verification Loop | W2 | 3 Golden + Auto Annotation + Evidence |
| M3 Engineering Loop | W3 | Replay + Regression + Coverage + 双平台完整闭环 |
| M4 MVP Review | W3/W4 | G1–G4 全部通过 + GO/PIVOT/STOP |

## 10. 四级 MVP Gate

### G1 工程真值
3 Executor 各至少 1 个可信 FORMAL Golden。

### G2 产品闭环
`FAIL → 自动定位 → Evidence → 保存 → Replay`。

### G3 工程规模
Scania 完成 Overview / Pick / 500+ occurrence 显隐 / Evidence 定位，不崩溃、不整场景丢失。

### G4 可交付性
Mac + Windows 同一最小闭环通过，Runtime/Worker 可取消、失败恢复、重启与正常退出。

四项都通过，MVP 即视为成功；15–25 Case 是复用覆盖证据，不是最前置生死 Gate。

## 11. P0 优先级

1. Electron Desktop。
2. Canonical AssemblyTree / Object Identity。
3. Runtime Controller + CAD Worker Job。
4. Windows Smoke。
5. Viewer 基础浏览与对象定位。
6. 3 Executor Golden。
7. Auto Annotation。
8. Evidence。
9. Replay。
10. Regression。
11. 15–25 Case Coverage。

## 12. P1 / 延后

- CATIA COM Adapter。
- 自动 Semantic Binding。
- AI Rule Compiler。
- 更多复杂 Executor。
- 完整报告中心。
- Auto Update / 签名。
- 企业账号 / 权限。
- Cloud Runtime。
- CAD BRep 编辑。

## 13. 主要风险与处理

### R1 Viewer 再次拖慢项目
冻结接口而非沉没成本；不达 Gate 可换实现，不改 Verification Core。

### R2 Assembly Tree 再次扁平
Canonical Tree 独立于 Mesh；Scania 644/80/564/depth5 纳入回归项。

### R3 Python/OCP 再次阻塞控制面
Controller 与 CAD Worker Process 分离；Job/Cancel/Heartbeat/Timeout/Restart 为 W1 P0。

### R4 macOS 通过但 Windows 失败
Windows Smoke 成为 W1/M1 硬 Exit Criteria；W3 再做完整闭环。

### R5 15–25 Case 变成定制代码
Coverage Matrix 必填 Executor/Binding/输入/阈值/Evidence，按 Executor 复用率评审。

### R6 Evidence 不可审计
Evidence 同时保存模型、规则、绑定、算法版本、工程数值、View State 和截图。

### R7 Scope 再膨胀
任何新增需求必须直接提升自动检测 / 标注 / Evidence / Replay / Regression 的验证，否则进入 P1。

## 14. 最终评审

MVP Review 只回答：

1. 工程真值是否可信。
2. FAIL 是否能自动定位并形成可复核 Evidence。
3. Replay / Regression 是否减少版本复查成本。
4. Scania 级复杂模型是否证明架构边界成立。
5. Mac / Windows 是否具备最小可交付性。
6. 3 Executor 是否能覆盖一批 Case，而非逐条定制。
7. Engineering Owner 是否愿意提供真实车型数据进入 Pilot。

即使 Viewer 仍不是生产级，只要 G1–G4 与业务信号成立，MVP 视为成功。