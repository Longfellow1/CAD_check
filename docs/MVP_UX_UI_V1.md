# CAD Check MVP UX & UI V1.1

> V1.1 为 V1.0 增量加固：主工作台与核心流程不变，只补齐 Canonical Tree、Job 状态、Case 成熟度和错误恢复。

## 1. UX 目标

界面围绕工程校核闭环设计，不复制 CATIA/NX 的建模工作台。

核心路径：

`打开模型 → 运行 Check → 看异常 → 自动定位 → 复核 Evidence → 保存/回放 → 对比版本`

第一原则：用户只需要知道“哪里有问题、为什么、怎么复核、版本间发生了什么变化”。

## 2. 信息架构

主界面采用单窗口三栏工作台：

```text
┌─────────────────────────────────────────────────────────────┐
│ 项目 / 模型 / 版本       运行校核      Job状态      设置/更多 │
├──────────────┬──────────────────────────────┬───────────────┤
│ 模型/结果树   │                              │ 当前问题详情   │
│              │          3D Viewer           │               │
│ Model Tree   │                              │ Rule          │
│ Check List   │                              │ Value         │
│ Regression   │                              │ Evidence      │
│              │                              │ Trace         │
├──────────────┴──────────────────────────────┴───────────────┤
│ 状态：Model / Runtime / Worker / Check / Cache / Error      │
└─────────────────────────────────────────────────────────────┘
```

3D 与检测结果始终处于视觉中心，低频技术信息收进“更多”。

## 3. 一级导航

只保留 3 个工作模式：

1. **工程校核**：执行 Check Set。
2. **版本回归**：V1 vs V2。
3. **快速测量**：辅助临时测量，不等同正式 Check。

## 4. 打开模型流程

### 4.1 空状态

只显示：打开 STEP、最近模型、最近项目。

### 4.2 导入与 Job 状态

选择 STEP 后：

- 顶部显示模型名、Job 状态、当前阶段。
- 阶段型 Progress：`READING / INVENTORY / TESSELLATING / FINALIZING`。
- 无可靠细粒度进度时使用不定进度，不伪造百分比。
- 始终提供 Cancel。
- UI 必须保持响应。

用户不需要看到 Heartbeat 数值，但系统检测 Runtime/Worker 异常后必须明确显示：

- `运行中`
- `已完成`
- `已取消`
- `失败`
- `超时`
- `CAD Worker 已停止 · 重新启动`

### 4.3 可浏览状态

第一批 Overview 可用后立即进入 Viewer，不等待全部 Detail。

Assembly Tree 必须来自 Python/XCAF Canonical AssemblyTree，不能从当前已加载 Mesh 反推，因此即使局部几何尚未加载，树层级仍应完整可浏览。

Readiness 分开显示“可预览”和“可校核”。局部无效 B-Rep/Binding 缺失时，用户仍可浏览模型并运行不受影响的 Case；受影响 Case 单独 BLOCKED，并可查看对象与原因。

## 5. 工程校核流程

### 5.1 运行

用户选择 Check Set，点击唯一主操作：`运行校核`。

运行中：

- 结果增量出现。
- 顶部显示已执行 / 总 Case 或当前阶段。
- 提供 Cancel。
- Viewer 不需要等待整车 Detail 完成才开始 Check。

### 5.2 Case 成熟度

Case 详情显示轻量成熟度标记：

- `FORMAL`：正式规则，可输出正式 PASS/FAIL。
- `PROVISIONAL`：待确认规则，只输出 REVIEW_REQUIRED/BLOCKED。
- `EXPLORATORY`：探索/临时测量，不进入正式 Regression。

主结果列表不堆技术字段，但必须避免把非 FORMAL 结果视觉上伪装成正式结论。

### 5.3 结果列表

默认优先级：FAIL → REVIEW_REQUIRED → BLOCKED → PASS。

每条展示：状态、Case 标题、测量值/阈值、对象短名、必要时成熟度标记。

### 5.4 点击结果

点击 FAIL 后自动：

1. 用 occurrence ID 定位 Target / Counterpart。
2. 无关对象隐藏或半透明。
3. 两个对象高亮。
4. 显示最近点 / 测量线 / 方向 / 角度标记。
5. Frame Camera 到证据区域。
6. 右栏显示 Rule、Value、Threshold、Margin、Result。

这是 MVP 最重要的体验。

## 6. Evidence 详情

右栏顺序：

```text
状态 / Rule Maturity
测量值 / 阈值 / Margin / 公差
检测对象 A / B
规则来源
Evidence 说明
Trace（折叠）
```

主操作：保存 Evidence、复制截图、回放。

Evidence 背后必须绑定 Model SHA、Rule Version、Executor Version、Binding Snapshot、坐标系和单位；这些默认折叠，不增加主界面认知负担。

## 7. Regression UX

顶部：`Baseline V1 → Candidate V2`

默认优先 NEW_FAIL / REGRESSED，并支持 FIXED / IMPROVED / UNCHANGED / NON_COMPARABLE。

只有 FORMAL Case 进入正式 Regression；非正式 Case 单独标记，不混入正式版本结论。

点击任一项：进入 V2 Evidence，可切换 V1，显示两版数值和 Delta。

## 8. Record / Replay UX

用户看到的是“工程复核记录”，不是录像播放器。

记录卡片包含：Case、模型版本、Result、保存时间、Evidence 缩略图。

点击回放后恢复：

- 模型版本。
- occurrence 对象选择。
- Visibility / Isolate。
- Camera。
- Highlight。
- Measurement / Annotation。

Replay 后仍可继续旋转、选择和复核。

若 Model SHA、Import Schema 或 Viewer Derivative 不兼容，回放页保留结构化记录和原截图，并显示“当前无法重建三维状态”；禁止自动选择名称相近对象制造伪回放。

## 9. Canonical Assembly Tree

Tree 只承担定位、层级导航和显隐，但数据源必须独立于 Viewer。

要求：

- 保留原始父子层级和名称。
- Tree Node 绑定 occurrence ID。
- Tree 点击 → Viewer Select。
- Viewer Pick → Tree Reveal。
- Hide / Isolate / Show All。
- 搜索对象名。
- 不因 Detail 未加载而丢节点。
- 不默认展开完整 subshape/face。

Scania 回归时，不允许再次出现“源装配有父子结构、Viewer Tree 退化为全部 root”的情况。

## 10. 快速测量

定位为辅助工具，不是正式 Check。

`选择 A → 选择 B → 最小距离 → 显示结果`

要求：

- A/B 同对象阻断。
- Tree 或 Viewer 均可选对象。
- 使用当前模型单位。
- 明确标记“临时测量 / EXPLORATORY”。
- 保存后只能成为 Evidence Note，不自动成为 Verification Case。

## 11. 大模型交互原则

- 不自动全量加载 Detail。
- Loading 时仍可旋转/缩放。
- Overview 与 Evidence 分离。
- 批量显隐不能造成整场景空白/消失。
- 全车 Edge 默认关闭。
- isolate 后优先加载目标区域 Detail。
- 内存超预算优先卸载不可见 Detail。

## 12. 错误与恢复

用户可见错误必须说明“发生什么 + 能做什么”。

典型状态：

- 模型可浏览但不可正式校核：显示 Readiness BLOCKED 原因。
- 某 Case 无 Binding：只阻断该 Case。
- Runtime Controller 异常：提示重启 Runtime。
- CAD Worker 超时/崩溃：提示任务失败并提供 Worker Restart。
- 用户 Cancel：明确进入已取消状态，不继续后台假运行。
- Viewer Detail 加载失败：保留 Overview、Tree 和 Check Result。
- 无效 B-Rep：明确受影响对象和 Case。

## 13. 视觉原则

- 白底、工程工具风格。
- 信息密度适中。
- 大字号用于关键结果。
- 状态不能只依赖颜色。
- PASS 弱化，FAIL / NEW_FAIL / REGRESSED 强调。
- 3D Viewer 始终拥有最大面积。

## 14. MVP 页面清单

只做：

1. 空状态 / 最近项目。
2. 主工程工作台。
3. Regression 工作台。
4. Evidence Replay 状态。
5. 更多：模型信息 / Readiness / Trace / Runtime/Worker Log。

## 15. UX 验收任务

新用户无需培训，应完成：

1. 打开 STEP，并能取消一次长任务。
2. 在完整 Canonical Tree 中定位对象。
3. 运行 Check Set。
4. 找到一个 FORMAL FAIL。
5. 看懂对象、测量值、阈值和 Evidence。
6. 保存并 Replay。
7. 切换 V1/V2 查看 Regression。
8. Worker 异常后能够恢复而不重启整个 App。

验收至少邀请 1 名目标工程师，在开发者不代操作的情况下完成上述主闭环，并记录完成时间、求助点、误操作和是否回到 CATIA 重新测量。若无法独立完成，或必须回到 CATIA 才能信任 Evidence，则本轮 UX Gate 不通过。

目标：技术复杂性由系统承担，不让 Viewer/Runtime 细节打断工程复核任务。
