# CAD Check MVP UX & UI V1.0

## 1. UX 目标

界面围绕工程校核闭环设计，不复制 CATIA/NX 的建模工作台。

核心路径必须最短：

`打开模型 → 运行 Check → 看异常 → 自动定位 → 复核 Evidence → 保存/回放 → 对比版本`

第一原则：用户不需要先理解系统架构，只需要知道“哪里有问题、为什么、怎么复核、版本间发生了什么变化”。

## 2. 信息架构

主界面采用单窗口三栏工作台：

```text
┌─────────────────────────────────────────────────────────────┐
│ 项目 / 模型 / 版本       运行校核      进度       设置/更多 │
├──────────────┬──────────────────────────────┬───────────────┤
│ 模型/结果树   │                              │ 当前问题详情   │
│              │          3D Viewer           │               │
│ Model Tree   │                              │ Rule          │
│ Check List   │                              │ Value         │
│ Regression   │                              │ Evidence      │
│              │                              │ Trace         │
├──────────────┴──────────────────────────────┴───────────────┤
│ 状态：模型 / Runtime / Check / Cache / 错误                  │
└─────────────────────────────────────────────────────────────┘
```

默认把 3D 与检测结果放在视觉中心，不让低频设置占用主工作区。

## 3. 一级导航

只保留 3 个工作模式：

1. **工程校核**：对当前模型执行 Check Set。
2. **版本回归**：V1 vs V2 比较。
3. **快速测量**：工程师临时选择两个对象做辅助测量。

“模型与数据 / Trace / 缓存 / 调试”收进二级“更多”。

## 4. 打开模型流程

### 4.1 空状态

首页只显示：

- 打开 STEP。
- 最近模型。
- 最近项目。

不自动加载任何重型模型。

### 4.2 导入状态

用户选择 STEP 后：

- 顶部显示模型名和导入阶段。
- STEP/XCAF 内部无法给细进度时使用不定进度，不伪造百分比。
- 可取消。
- UI 必须保持响应。

### 4.3 可浏览状态

第一批 Overview 几何可用后立即进入 Viewer，不等待所有 Detail。

展示：

- Assembly Tree 可展开。
- 当前加载状态。
- 模型 Readiness。
- Cache 状态可放在“更多”。

## 5. 工程校核流程

### 5.1 运行

用户选择 Check Set，点击唯一主操作：`运行校核`。

运行中：

- 结果列表增量出现。
- 顶部显示已执行 / 总 Case 数。
- 不要求 Viewer 等待整车完整 Detail 才开始 Check。

### 5.2 结果列表

左栏结果优先按：

1. FAIL
2. REVIEW_REQUIRED
3. BLOCKED
4. PASS

每条只展示：

- 状态。
- Case 标题。
- 测量值 / 阈值。
- 对象短名。

不在列表堆 Trace、Executor、Binding Path 等开发信息。

### 5.3 点击结果

点击 FAIL 后系统自动执行：

1. 3D 定位 Target / Counterpart。
2. 无关对象隐藏或半透明。
3. 两个对象高亮。
4. 显示最近点 / 测量线 / 方向 / 角度标记。
5. 相机自动 Frame 到证据区域。
6. 右栏显示 Rule、Value、Threshold、Margin、Result。

这是 MVP 最重要的体验。

## 6. Evidence 详情

右栏按固定顺序：

```text
状态
测量值 / 阈值 / Margin
检测对象 A / B
规则来源
Evidence 说明
Trace（折叠）
```

主操作：

- 保存 Evidence。
- 复制截图。
- 回放。

Viewer 中 Evidence 采用局部高质量几何，允许 Edge ON；整车 Overview 默认 Edge OFF。

## 7. Regression UX

版本回归页只做一件事：告诉用户版本变化造成了什么工程影响。

顶部：

`Baseline V1 → Candidate V2`

左侧过滤：

- 新增不满足 NEW_FAIL。
- 已修复 FIXED。
- 退化 REGRESSED。
- 改善 IMPROVED。
- 无变化 UNCHANGED。
- 不可比较 NON_COMPARABLE。

默认优先显示 NEW_FAIL / REGRESSED。

点击任一项：

- 进入 V2 Evidence。
- 可切换查看 V1 Evidence。
- 显示两版数值和 Delta。

示例：

```text
Battery ↔ Bracket
V1 12.0 mm  PASS
V2  8.0 mm  FAIL
Δ  -4.0 mm
NEW_FAIL
```

## 8. Record / Replay UX

用户看到的是“工程复核记录”，不是录像播放器。

记录卡片包含：

- Case。
- 模型版本。
- Result。
- 保存时间。
- Evidence 缩略图。

点击 `回放`：

- 自动恢复模型版本。
- 自动恢复对象显隐。
- 自动恢复 Camera。
- 自动恢复 Highlight。
- 自动恢复测量标记和 Annotation。

Replay 完成后用户可继续旋转、选择和复核，不锁死画面。

## 9. Assembly Tree

Tree 只承担定位和显隐：

- 保留父子层级。
- 显示原始对象名。
- 点击 Tree 节点 → Viewer Select。
- Viewer Pick → Tree Reveal。
- 右键：Hide / Isolate / Show All。
- 搜索对象名。

不要把完整 subshape / face 列表默认展开。

## 10. 快速测量

定位为辅助工具，不是正式 Check。

流程：

`选择 A → 选择 B → 最小距离 → 显示结果`

要求：

- A/B 同对象必须阻断。
- 支持从 Tree 或 Viewer Pick 对象。
- 默认使用当前模型单位。
- 结果明确标记“临时测量”。
- 若保存，则转成 Evidence Note，不自动成为 Verification Case。

## 11. 大模型交互原则

- 不自动全量加载 Detail。
- Loading 时仍可旋转/缩放。
- Overview 与 Evidence 分离。
- 用户选择/显隐必须批处理，不因模型越加载越明显变慢。
- 全车 Edge 默认关闭。
- isolate 后优先加载目标区域高质量 Detail。
- 内存超预算时优先卸载不可见 Detail，而不是崩溃。

## 12. 错误与状态

用户可见错误必须说明“发生什么 + 能做什么”。

典型状态：

- 模型可浏览，但不可正式校核：显示 Readiness BLOCKED 原因。
- 某 Case 无 Binding：该 Case BLOCKED，不把整个 App 置灰。
- Runtime 崩溃：提示 `CAD Runtime 已停止 · 重新启动`。
- Viewer Detail 加载失败：保留 Overview 和 Check Result，不清空整个场景。
- 无效 B-Rep：明确标注受影响对象和 Case。

## 13. 视觉原则

- 白底、工程工具风格。
- 信息密度适中，不做大面积营销卡片。
- 大字号用于结果值和状态，不用于装饰。
- 颜色只表达状态，不依赖颜色作为唯一信息。
- PASS 弱化，FAIL / NEW_FAIL / REGRESSED 强调。
- 3D Viewer 始终拥有最大面积。

## 14. MVP 页面清单

只做：

1. 空状态 / 最近项目。
2. 主工程工作台。
3. Regression 工作台（复用主布局）。
4. Evidence Replay 状态。
5. 更多：模型信息 / Readiness / Trace / Runtime Log。

不单独建设复杂设置中心、规则编辑器、账户中心、报告中心。

## 15. UX 验收任务

新用户无需培训，能够完成：

1. 打开 STEP。
2. 运行 Check Set。
3. 找到一个 FAIL。
4. 看懂两个检测对象、距离和阈值。
5. 保存 Evidence。
6. 从记录中 Replay。
7. 切换 V1/V2 查看 Regression。

目标：主闭环每一步都只有一个明确主操作，不因 Viewer/Runtime 技术细节打断工程任务。