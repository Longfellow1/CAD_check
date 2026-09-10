# CAD Check MVP 项目排期 V1.0

## 1. 项目目标

用 3–4 周完成一个可在 macOS / Windows x64 运行的 Electron MVP，验证：

`STEP → 自动检测 → 自动定位/标注 → Evidence → Replay → V1/V2 Regression`

排期原则：

- Viewer 选型首日关闭，不持续横向调研。
- 优先打通端到端闭环，再补完整度。
- 不把生产级 Viewer、CATIA、企业基建带入 MVP。

## 2. 总体节奏

```text
D0–D1   Viewer Gate + Electron Spike
W1      Desktop Shell + CAD Runtime + Viewer
W2      Check + Auto Annotation + Evidence
W3      Replay + Regression + Windows 验证
W4      真实模型收口 / Buffer（如需要）
```

基础周期按 3 周执行，第 4 周仅作为真实数据问题和演示打磨 Buffer。

## 3. Gate 0：Viewer 选型（0.5–1 天）

### 目标

关闭 NARU vs cad-3d-viewer 选型，不开发业务功能。

### 输入

- 小型 Controlled STEP。
- Scania 约 295MB STEP。
- Mac M4 Pro 24GB。
- Windows x64 验证机。

### 测试项

- Electron 内运行。
- 首次可见时间。
- 峰值内存。
- 旋转/缩放是否稳定。
- Assembly Tree。
- Hide / Isolate。
- Picking。
- 500+ occurrence 操作。
- Highlight 接口可扩展性。
- Windows 可运行性。

### 决策

- NARU 明显更稳定且性能优势成立 → NARU。
- NARU Alpha / WebGPU 风险阻断，cad-3d-viewer 达到 MVP 稳定线 → cad-3d-viewer。

### Exit Criteria

- 只能保留一个主 Viewer。
- 输出一页 benchmark 结果。
- Gate 后停止 Viewer 横向选型。

## 4. Week 1：桌面与模型主链

### 目标

在 Electron 中完成“打开 STEP → Viewer 可浏览 → Python/OCP 可计算”。

### 开发

#### Electron

- Main / Renderer 基础工程。
- 本地文件选择。
- 启动 / 关闭 Python FastAPI Runtime。
- localhost 随机端口 + session token。
- Runtime health / restart。

#### CAD Runtime

- 复用现有 STEP/XCAF/OCP。
- Inventory / Readiness。
- 最小 GeometryBackend/CadAdapter 边界。
- OCP Minimum Clearance 接口跑通。

#### Viewer

- 接入 Gate 胜出底座。
- Assembly Tree。
- Pick / Hide / Show / Isolate。
- Overview。
- 对象 ID 与 Python Inventory 建立映射。

### Week 1 验收

Mac：

`Electron 打开 → 选择 STEP → 看到模型 → Pick 两个对象 → Python 返回最小距离`

同时满足：

- UI 不因 OCP 重任务直接假死。
- Runtime 可被重启。
- Viewer 与 Check Geometry 数据边界清楚。

## 5. Week 2：MVP 核心价值闭环

### 目标

完成“自动检测 → 自动定位/标注 → Evidence”。

### 开发

#### Verification

- 固定 15–25 条 Case。
- 3 个 Executor：Minimum Clearance / Directional Distance / Angle。
- 单 Case + Batch Run。
- PASS / FAIL / REVIEW_REQUIRED / BLOCKED。

#### Auto Focus / Annotation

点击结果自动：

- 定位 Target / Counterpart。
- isolate / 半透明 Context。
- highlight。
- Frame Camera。
- 画 closest-points / measurement line。
- 展示 value / threshold / margin。

#### Evidence

- Evidence JSON。
- Screenshot。
- Trace ID。
- View State。
- 本地保存。

### Week 2 验收

使用 Controlled Fixture：

- Batch Run 可执行。
- 每个可执行 FAIL 均能一键进入证据视图。
- 数值来自 OCP BRep。
- Evidence 截图和结构化记录一致。
- 不需要人工重新选择对象才能理解结果。

## 6. Week 3：Replay / Regression / 双平台

### 目标

把“单次检测 Demo”变成版本工程复核工具。

### 开发

#### Replay

持久化并恢复：

- Case / Model Version。
- Camera。
- Visibility / Isolate。
- Highlight。
- Annotation / Measurement。
- Evidence。

#### Regression

- V1 / V2 同一 Check Set。
- 输出 NEW_FAIL / FIXED / IMPROVED / REGRESSED / UNCHANGED / NON_COMPARABLE。
- V1/V2 Evidence 切换。
- Delta 展示。

#### Windows x64

- Electron 启动。
- Python/OCP Runtime。
- STEP 导入。
- Viewer。
- Minimum Clearance。
- Evidence / Replay。

### Week 3 验收

同一套 Controlled V1/V2 在 Mac 与 Windows 均跑通：

`打开 → Run → FAIL → Evidence → Replay → Regression`

并证明 CAD Runtime 崩溃/重启不会直接带崩 Electron 主界面。

## 7. Week 4：真实模型收口 Buffer

仅在前三周主闭环已完成后进入。

### 重点

- Scania 大模型稳定性。
- Viewer cache / warm open。
- 内存泄漏。
- Hide/Isolate 性能。
- 无效 B-Rep 降级。
- Windows 差异问题。
- 演示脚本和证据补齐。

不在 Week 4 新增大功能。

## 8. MVP 里程碑

| Milestone | 时间 | 通过标准 |
|---|---|---|
| M0 Viewer Freeze | D1 | NARU / cad-3d-viewer 二选一 |
| M1 Desktop Loop | W1 | Electron + STEP + Viewer + OCP Measure |
| M2 Verification Loop | W2 | Batch + Auto Annotation + Evidence |
| M3 Engineering Loop | W3 | Replay + Regression + Windows |
| M4 MVP Review | W3/W4 | 真实模型演示 + GO/PIVOT/STOP |

## 9. P0 优先级

必须做：

1. Electron Desktop。
2. STEP/OCP Runtime。
3. Viewer 基础浏览与对象定位。
4. 3 Executor。
5. Batch Check。
6. Auto Annotation。
7. Evidence。
8. Replay。
9. Regression。
10. Windows x64 闭环。

## 10. P1 / 延后

- CATIA COM Adapter。
- 自动 Semantic Binding。
- AI Rule Compiler。
- 更多复杂 Executor。
- 完整报告中心。
- Auto Update / 签名。
- 企业账号 / 权限。
- Cloud Runtime。
- CAD BRep 编辑。

## 11. 主要风险与处理

### R1 Viewer 继续拖慢项目

处理：D1 强制冻结选型；Viewer 只满足 MVP 能力，不做通用 CAD 平台。

### R2 Scania 大模型继续崩

处理：Overview / Detail / Evidence 分级；大模型是压力 Gate，不阻断小模型核心闭环开发。

### R3 Python/OCP 阻塞 Electron

处理：Runtime 独立进程；重任务与 UI 生命周期隔离。

### R4 macOS 通过但 Windows 失败

处理：Week 1 即做一次 Windows Hello World，Week 3 做全闭环，不等项目结束才测。

### R5 Evidence 只有截图、不可审计

处理：Evidence 必须同时保存结构化几何结果 + View State + Trace + Screenshot。

### R6 Scope 再次膨胀

处理：任何新需求必须回答是否直接提升“自动检测/标注/Evidence/Replay/Regression”验证；否则进入 P1。

## 12. 最终评审

MVP Review 只回答：

1. 规则是否可执行化。
2. 检测是否可信。
3. Evidence 是否减少人工复核成本。
4. Replay / Regression 是否形成版本价值。
5. 真实车型数据是否值得进入下一阶段。

如果上述成立，即使 Viewer 仍不是生产级，MVP 也视为成功。