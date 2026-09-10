# CAD Check MVP 产品需求 V1.1

> V1.1 为 V1.0 增量加固：产品主线不变，只补齐工程真值、Case 成熟度、对象身份、验收 Gate，并把 Electron 产品形态收紧为不可违反的产品合同。

## 0. 不可违反的产品形态合同

CAD Check MVP 的**唯一产品入口**是 Electron Desktop App。

- 用户、工程师、评审人从 Electron App 进入产品，不通过系统浏览器访问 localhost。
- `web/` 目录只是 Electron Renderer 的前端源码/构建目录，不代表另一个 Web 产品。
- FastAPI/localhost 只是 Electron 内部 Python/OCP sidecar，不是用户可见产品入口。
- Standalone Browser 仅允许开发调试 Renderer/API，不能作为 Demo、用户测试、功能验收或 MVP Gate 证据。
- 任何功能若只在浏览器中跑通、需要用户手工启动 Uvicorn、复制 URL 或管理端口，状态一律为 **NOT DONE**。
- 功能 Done 至少满足：代码完成 + 自动测试 + Electron 内可操作 + Electron Main 正确管理 Runtime 生命周期。
- macOS / Windows 的验证结果均以 Electron 闭环为准；浏览器通过不能替代 Desktop 通过。

## 1. 产品定位

CAD Check 是面向汽车工程校核场景的独立 Electron 桌面工具。MVP 不做 CAD 建模软件，而是验证：能否把高频、规则明确的人工校核工作转成可执行、可复核、可回放的 Verification Case。

核心闭环：

`打开 Electron App → 导入模型 → 自动检测 → 自动定位/标注 → Evidence 留证 → 记录/回放 → V1/V2 Regression`

## 2. MVP 要回答的问题

1. 15–25 条真实风格工程规则能否收敛到少量可复用 Executor。
2. STEP/AP242 + OCP/OCCT 是否能稳定执行所选几何校核。
3. 自动标注和 Evidence 是否足以让工程师快速理解、复核结果。
4. V1→V2 回归是否能清晰识别新增问题、修复、改善、退化和不可比较。
5. 该工具是否值得工程业务方提供真实车型数据进入 Pilot。

## 3. 产品形态

- 独立 Electron Desktop App，且是唯一受支持的产品形态。
- macOS Apple Silicon 为主开发环境。
- Windows x64 为必须通过的验证环境和后续主交付环境。
- MVP 本地运行，模型默认不上传云端。
- FreeCAD、Obsidian、CATIA 均不作为宿主。
- Renderer 可以继续使用 HTML/CSS/JS/Three.js/Babylon/WebGPU 等 Web 技术，但它运行在 Electron 产品壳内。
- localhost FastAPI 只用于 App 内部通信；用户不需要理解 Python 服务、端口或 URL。

## 4. 核心用户

第一目标用户：整车总布置 / DMU 校核工程师及 Engineering Owner。

核心 JTBD：

> 当车型版本发生变化时，我希望系统自动重新执行冻结的 Check Set，告诉我新增了什么问题、修复了什么、哪里退化，并给出可直接复核的几何证据，而不是重新人工逐项测量、截图和记录。

## 5. MVP 功能范围

### 5.1 模型与项目

- 从 Electron 打开本地 `.stp/.step`。
- 读取 STEP/AP242 基础装配、单位、对象名称和几何。
- 由 STEP/XCAF 生成独立于 Viewer 的 Canonical AssemblyTree。
- 显示模型 Readiness：可预览 / 可校核 / 阻断原因。
- 支持同一车型 V1 / V2 两个版本进入回归。
- 同一模型二次打开优先命中本地缓存。

对象身份至少区分：

- `geometry_ref`：单次导入中的几何引用。
- `occurrence_id`：当前模型版本内的装配对象身份。
- `semantic_binding_id`：跨版本用于工程绑定的业务身份；MVP 可人工定义，不做自动语义绑定。

同一 `Model SHA + Import Schema Version` 重复导入时，`occurrence_id` 必须确定性复现；不得直接使用内存地址、临时数组下标或 Viewer Mesh ID。若导入 Schema 变化导致 ID 不兼容，系统必须显式标记 Replay / Regression 需要重新绑定。

Readiness 按能力分开表达：模型可以“可预览但部分 Case 不可校核”。局部无效 B-Rep 或 Binding 缺失只阻断受影响 Case，不应无差别阻断整车其他有效 Case；界面必须展示受影响对象与 Case 数量。

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
- 默认高亮目标对象并保留必要 Context；周围对象半透明弱化。
- 用户可显式触发 Isolate，但不默认直接清空上下文。
- 显示最近点、测量线、方向或角度基准。
- 显示测量值、阈值、Margin 和结果。

### 5.6 Evidence

FAIL / REVIEW_REQUIRED 的 Evidence 采用自动生成策略，工程师进入结果后直接复核，不重新人工选择对象或人工截图。

每条可执行结果产生结构化 Evidence：

- Run ID、Check Set/Case ID 与版本、模型版本、对象 ID/Path。
- Model SHA、Rule Version、Executor Version。
- Binding Snapshot。
- Measurement Method / Executor 参数。
- 计算值、阈值、单位、公差、坐标系定义、结果。
- 最近点 / 基准信息。
- Camera / Visibility / Highlight 状态。
- 截图。
- Trace / Runtime 信息。

Evidence 必须能追溯到 Case、模型版本、规则版本和当次绑定状态。

PASS 默认保留结构化结果，可按需生成局部可视 Evidence，不要求全量高成本截图常驻。

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

若原模型、Viewer Derivative 或对象身份版本不兼容，Replay 必须降级为“结构化记录 + 原 Evidence 截图”查看，并明确提示无法重建三维状态，不能静默绑定到相似对象。

### 5.8 Regression

支持冻结 Check Set 对 V1 / V2 执行并比较。

输出：

- `NEW_FAIL`
- `FIXED`
- `IMPROVED`
- `REGRESSED`
- `UNCHANGED`
- `NON_COMPARABLE`

MVP 使用**单 Viewer + V1/V2 一键切换**，不做双 Viewer 同屏。

用户可以从 Regression 结果直接进入 Evidence Replay。

V1/V2 只有在 Case/Rule/Executor/Measurement Method/单位与坐标系合同兼容，且两版 `semantic_binding_id` 均能解析时才允许比较。任一条件不成立必须输出 `NON_COMPARABLE`，不得只按 Case ID 或对象名称强行比较。

### 5.9 快速测量

快速测量是 Viewer 辅助工具，不是一级产品模式。

- Viewer/Tree 选择 A/B。
- 执行临时 Minimum Clearance 等探索测量。
- 明确标记 EXPLORATORY。
- 不自动形成正式 Verification Case。
- 关闭工具后返回原工程校核/版本回归上下文。

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

Viewer 的候选实现必须在 Electron 内完成 Gate；Standalone Browser benchmark 只能作为开发数据，不作为最终 Gate 结果。

## 7. 性能与稳定性要求

- 代表性 Golden/Coverage 模型首次 STEP 导入目标为 1–3 分钟；Scania 冷启动单独按 Scale Gate 记录，不用该目标伪装为已达标，但 Electron UI 始终不得假死。
- 第一批可视几何出现后必须允许旋转/缩放。
- 二次打开应显著快于首次导入。
- 大模型加载不能无限增加 Renderer 常驻内存。
- CAD 计算异常或 Worker 崩溃不能带崩 Electron UI。
- 长任务必须可观察、可取消、失败可恢复；取消不了的底层 OCCT 任务允许通过终止并重启 Worker 实现。
- Overview 默认关闭全车 Edge；Evidence 局部可开启高质量 Edge。

Scania 约 295MB STEP 作为当前压力测试基线，不要求 MVP 首次打开达到秒级，但要求稳定、可取消、可恢复。

## 8. 明确不做

- 独立 Web 产品或浏览器交付形态。
- AI Rule Compiler。
- 自动 Semantic Binding。
- CATIA COM / CAA 真实集成。
- BRep 几何编辑器。
- Headroom / Visibility / Dynamic DMU / CAE 等复杂 Executor。
- 企业账号、权限、审批、云部署。
- 生产级 Auto Update / Code Signing。

## 9. MVP 成功标准与四级 Gate

产品成功不是“Viewer 做得像 CATIA”，而是四级 Gate 均成立；**四级 Gate 均以 Electron 产品形态执行**。

### G1 工程真值

- 3 个 Executor 各至少 1 个 `FORMAL` Golden Case。
- Golden 的对象、方法、单位、坐标系、公差和真值来源完整。
- OCP/OCCT 结果在约定公差内与真值一致。

### G2 产品闭环

`Electron → FAIL → 自动定位/标注 → 自动 Evidence → 固化 → Replay` 可一键完成，不需要工程师重新人工选择对象复现证据。

至少由 1 名目标工程师在无开发者代操作的情况下，从 Electron App 完成该闭环；记录完成时间、阻断点和是否需要回到 CATIA 重新测量。若仍需重新测量才能信任结果，G2 不通过。

### G3 工程规模

Scania 级复杂模型在 Electron 内可以完成 Overview、Pick、Hide/Isolate 和固定 occurrence pair 的定位/Evidence 叠加；连续交互不出现应用崩溃或整场景丢失。该叠加只验证规模下的交互链路，不宣称 Scania 已形成 FORMAL 工程结论。

### G4 可交付性

同一最小 Electron 闭环在 Mac 与 Windows x64 均跑通；Electron Main 能启动、守护并关闭 Runtime，Runtime 可取消/失败处理/重启并正常退出。

浏览器模式完成同样流程不计入 G4。

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
