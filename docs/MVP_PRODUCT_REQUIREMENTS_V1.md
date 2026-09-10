# CAD Check MVP 产品需求 V1.1

> V1.1 为 V1.0 增量加固：产品主线不变，只补齐工程真值、Case 成熟度、对象身份和验收 Gate。

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
- 由 STEP/XCAF 生成独立于 Viewer 的 Canonical AssemblyTree。
- 显示模型 Readiness：可预览 / 可校核 / 阻断原因。
- 支持同一车型 V1 / V2 两个版本进入回归。
- 同一模型二次打开优先命中本地缓存。

对象身份至少区分：

- `geometry_ref`：单次导入中的几何引用。
- `occurrence_id`：当前模型版本内的装配对象身份。
- `semantic_binding_id`：跨版本用于工程绑定的业务身份；MVP 可人工定义，不做自动语义绑定。

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
- 参数 / 阈值 / 单位 / 公差。
- 适用模型版本。
- Rule Maturity。

Rule Maturity：

- `FORMAL`：规则来源、对象、方法、单位、公差和真值定义完整，可输出正式 PASS/FAIL 并进入 Regression。
- `PROVISIONAL`：定义仍有缺口，只允许输出 REVIEW_REQUIRED / BLOCKED，不作为正式工程结论。
- `EXPLORATORY`：探索或临时测量，不进入正式 Regression。

### 5.3 Case 验证分层

MVP 不把所有 Case 混成一种测试资产：

- **Golden Case**：验证计算是否正确；3 个 Executor 各至少 1 个可信 Golden。
- **Coverage Case**：15–25 条 Case 验证少量 Executor 能否覆盖一类真实规则，而不是每条规则写一套代码。
- **Scale Case**：Scania 约 295MB STEP 只验证复杂模型加载、定位、显隐和稳定性，不作为规则真值。
- **Regression Fixture**：受控 V1/V2 验证 NEW_FAIL / FIXED / IMPROVED / REGRESSED 等版本逻辑。

Golden Case 必须明确对象、方法、坐标系、单位、公差和外部/人工真值来源；信息不完整的案例不得标为 Golden。

### 5.4 自动检测

- 单 Case 执行。
- Check Set 批量执行。
- 结果状态：`PASS / FAIL / REVIEW_REQUIRED / BLOCKED`。
- 几何判定必须来自 OCP/OCCT B-Rep，不使用 Viewer Mesh 作为工程真值。
- 只有 `FORMAL` Case 可作为正式 PASS/FAIL 进入 Regression。

### 5.5 自动定位与标注

点击任一检测结果后，系统自动：

- 定位 Target / Counterpart。
- 隐藏或弱化无关对象。
- Highlight 检测对象。
- 显示最近点、测量线、方向或角度基准。
- 显示测量值、阈值、Margin 和结果。

### 5.6 Evidence

每条可执行结果产生结构化 Evidence：

- Case ID、模型版本、对象 ID/Path。
- Model SHA、Rule Version、Executor Version。
- Binding Snapshot。
- 计算值、阈值、单位、公差、坐标系、结果。
- 最近点 / 基准信息。
- Camera / Visibility / Highlight 状态。
- 截图。
- Trace / Runtime 信息。

Evidence 必须能追溯到 Case、模型版本、规则版本和当次绑定状态。

### 5.7 Record / Replay

MVP 记录工程状态，不录制鼠标轨迹或视频。

Replay State 至少包含：

- 模型版本。
- Case ID。
- Target / Counterpart occurrence ID。
- Camera。
- Visible / Hidden / Isolated Objects。
- Annotation / Measurement Geometry。
- 结果及 Evidence ID。

点击历史记录后应自动恢复到可复核状态。

### 5.8 Regression

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

Viewer 只服务于理解和复核，不承担工程判定，也不拥有装配树真值。

MVP 必须具备：

- 整车粗览。
- 显示来自 Canonical AssemblyTree 的层级。
- Orbit / Pan / Zoom。
- Part / Face Picking，并映射回 occurrence ID。
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
- 长任务必须可观察、可取消、失败可恢复；取消不了的底层 OCCT 任务允许通过终止并重启 Worker 实现。
- Overview 默认关闭全车 Edge；Evidence 局部可开启高质量 Edge。

Scania 约 295MB STEP 作为当前压力测试基线，不要求 MVP 首次打开达到秒级，但要求稳定、可取消、可恢复。

## 8. 明确不做

- AI Rule Compiler。
- 自动 Semantic Binding。
- CATIA COM / CAA 真实集成。
- BRep 几何编辑器。
- Headroom / Visibility / Dynamic DMU / CAE 等复杂 Executor。
- 企业账号、权限、审批、云部署。
- 生产级 Auto Update / Code Signing。

## 9. MVP 成功标准与四级 Gate

产品成功不是“Viewer 做得像 CATIA”，而是四级 Gate 均成立：

### G1 工程真值

- 3 个 Executor 各至少 1 个 `FORMAL` Golden Case。
- Golden 的对象、方法、单位、坐标系、公差和真值来源完整。
- OCP/OCCT 结果在约定公差内与真值一致。

### G2 产品闭环

`FAIL → 自动定位/标注 → Evidence → 保存 → Replay` 可一键完成，不需要工程师重新人工选择对象复现证据。

### G3 工程规模

Scania 级复杂模型可以完成 Overview、Pick、Hide/Isolate 和 FAIL Evidence 定位；连续交互不出现应用崩溃或整场景丢失。

### G4 可交付性

同一最小闭环在 Mac 与 Windows x64 均跑通；Runtime 可启动、取消/失败处理、重启并正常退出。

Coverage 成功信号：3 类 Executor 能覆盖 15–25 条 Case，而不是形成 15–25 套定制代码。

最终业务信号：Engineering Owner 愿意提供真实车型数据继续 Pilot。

## 10. 后续路线

MVP 后优先进入：

- 更多 Check Archetype / Executor。
- Binding Reuse / Semantic Binding。
- Windows CATIA Adapter：优先 Python + COM/Automation。
- 必要时再评估 CAA 深集成。
- Rule digitization / Agent orchestration。

长期核心资产保持 CAD-independent：`Verification Case / Rule / Executor / Evidence / Replay / Regression`。