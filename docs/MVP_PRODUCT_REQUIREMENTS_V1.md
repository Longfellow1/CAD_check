# CAD Check MVP 产品需求 V1.0

## 1. 产品定位

CAD Check 是面向汽车工程校核场景的独立桌面工具。MVP 不做 CAD 建模软件，而是验证：能否把高频、规则明确的人工校核工作转成可执行、可复核、可回放的 Verification Case。

核心闭环：

`导入模型 → 自动检测 → 自动定位/标注 → Evidence 留证 → 记录/回放 → V1/V2 Regression`

## 2. MVP 要回答的问题

1. 15–25 条真实风格工程规则能否收敛到少量可复用 Executor。
2. STEP/AP242 + OCP/OCCT 是否能稳定执行所选几何校核。
3. 自动标注和 Evidence 是否足以让工程师快速理解、复核结果。
4. V1→V2 回归是否能清晰识别新增问题、修复、改善、退化和不可比较。
5. 该工具是否值得工程业务方提供真实车型数据进入 Pilot。

## 3. 产品形态

- 独立 Electron Desktop App。
- macOS Apple Silicon 为主开发环境。
- Windows x64 为必须通过的验证环境和后续主交付环境。
- MVP 本地运行，模型默认不上传云端。
- FreeCAD、Obsidian、CATIA 均不作为宿主。

## 4. 核心用户

第一目标用户：整车总布置 / DMU 校核工程师及 Engineering Owner。

核心 JTBD：

> 当车型版本发生变化时，我希望系统自动重新执行冻结的 Check Set，告诉我新增了什么问题、修复了什么、哪里退化，并给出可直接复核的几何证据，而不是重新人工逐项测量、截图和记录。

## 5. MVP 功能范围

### 5.1 模型与项目

- 导入 `.stp/.step`。
- 读取 STEP/AP242 基础装配、单位、对象名称和几何。
- 显示模型 Readiness：可预览 / 可校核 / 阻断原因。
- 支持同一车型 V1 / V2 两个版本进入回归。
- 同一模型二次打开优先命中本地缓存。

### 5.2 Verification Case

MVP 使用人工定义的 15–25 条 Case，不做 AI 自动规则编译。

首批 Executor：

1. Minimum Clearance：最小间隙。
2. Directional Distance：指定方向距离。
3. Angle / Orientation：角度与姿态关系。

每个 Case 至少包含：

- Case ID / 标题。
- Rule Source。
- Target / Counterpart Binding。
- Executor。
- 参数 / 阈值 / 单位。
- 适用模型版本。

### 5.3 自动检测

- 单 Case 执行。
- Check Set 批量执行。
- 结果状态：`PASS / FAIL / REVIEW_REQUIRED / BLOCKED`。
- 几何判定必须来自 OCP/OCCT B-Rep，不使用 Viewer Mesh 作为工程真值。

### 5.4 自动定位与标注

点击任一检测结果后，系统自动：

- 定位 Target / Counterpart。
- 隐藏或弱化无关对象。
- Highlight 检测对象。
- 显示最近点、测量线、方向或角度基准。
- 显示测量值、阈值、Margin 和结果。

### 5.5 Evidence

每条可执行结果产生结构化 Evidence：

- Case ID、模型版本、对象 ID/Path。
- 计算值、阈值、单位、结果。
- 最近点 / 基准信息。
- Camera / Visibility / Highlight 状态。
- 截图。
- Trace / Executor 信息。

Evidence 必须能追溯到 Case 和模型版本。

### 5.6 Record / Replay

MVP 记录工程状态，不录制鼠标轨迹或视频。

Replay State 至少包含：

- 模型版本。
- Case ID。
- Target / Counterpart。
- Camera。
- Visible / Hidden / Isolated Objects。
- Annotation / Measurement Geometry。
- 结果及 Evidence ID。

点击历史记录后应自动恢复到可复核状态。

### 5.7 Regression

支持冻结 Check Set 对 V1 / V2 执行并比较。

输出：

- `NEW_FAIL`
- `FIXED`
- `IMPROVED`
- `REGRESSED`
- `UNCHANGED`
- `NON_COMPARABLE`

用户可以从 Regression 结果直接进入 Evidence Replay。

## 6. Viewer 能力边界

Viewer 只服务于理解和复核，不承担工程判定。

MVP 必须具备：

- 整车粗览。
- Assembly Tree。
- Orbit / Pan / Zoom。
- Part / Face Picking。
- Hide / Show / Isolate。
- Section。
- Highlight。
- 局部高精度 Evidence 展示。
- 测量线 / 标注 / 截图。

不要求：

- CATIA 级建模编辑。
- 整车全精度、全边线永久常驻。
- 全车型工业级超大模型性能。

## 7. 性能与稳定性要求

- 首次 STEP 导入 1–3 分钟可接受，但 UI 不得假死。
- 第一批可视几何出现后必须允许旋转/缩放。
- 二次打开应显著快于首次导入。
- 大模型加载不能无限增加 Renderer 常驻内存。
- CAD 计算异常或 Worker 崩溃不能带崩 Electron UI。
- Overview 默认关闭全车 Edge；Evidence 局部可开启高质量 Edge。

Scania 约 295MB STEP 作为当前压力测试基线，不要求 MVP 首次打开达到秒级，但要求稳定、可取消、可恢复。

## 8. 明确不做

- AI Rule Compiler。
- 自动 Semantic Binding。
- CATIA COM / CAA 真实集成。
- BRep 几何编辑器。
- Headroom / Visibility / Dynamic DMU / CAE 等复杂 Executor。
- 企业账号、权限、审批、队列、云部署。
- 生产级 Auto Update / Code Signing。

## 9. MVP 成功标准

产品成功不是“Viewer 做得像 CATIA”，而是满足以下条件：

1. 3 类 Executor 能覆盖 15–25 条 Case。
2. 一次 Batch Run 能输出可信结果。
3. FAIL 可自动定位、标注并生成 Evidence。
4. Evidence 能一键 Replay。
5. V1/V2 Regression 能稳定输出变化类别。
6. Scania 级复杂模型不因一次查看/显隐导致应用崩溃。
7. Mac 与 Windows x64 均能跑通同一最小闭环。
8. Engineering Owner 愿意提供真实车型数据继续 Pilot。

## 10. 后续路线

MVP 后优先进入：

- 更多 Check Archetype / Executor。
- Binding Reuse / Semantic Binding。
- Windows CATIA Adapter：优先 Python + COM/Automation。
- 必要时再评估 CAA 深集成。
- Rule digitization / Agent orchestration。

长期核心资产保持 CAD-independent：`Verification Case / Rule / Executor / Evidence / Replay / Regression`。