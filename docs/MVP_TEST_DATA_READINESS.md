# P1 真实 CAD 测试数据就绪度

## 产品出口

工程师拿到 STEP 后，能确认模型是否读对、规则是否满足、V1 到 V2 的变化是否可信，并能复核三维证据。

## 当前状态

P0 已在 `main@11b5173` 合入。当前 P1 数据分支提供输入和验收合同，不改变应用代码。

| 数据集 | 状态 | 价值 |
| --- | --- | --- |
| NIST AP242 | 7 个 STEP、README、哈希已准备 | 验证 AP242/XCAF 导入和 assembly 报告 |
| Controlled Fixture | contract 已准备，STEP 等待生成器 | 验证 PASS/FAIL、版本回归和 binding drift |
| TABBY EVO | 官方来源和许可已核验，STEP 待补 | 验证车辆尺度、viewer 和基础测量 |

## 当前差距

1. Controlled STEP 尚未生成，12/8 mm golden 尚未跑通。
2. TABBY 官方 STEP 的历史下载入口当前不可用，不能用未核验镜像替代。
3. NIST 仍需批量导入报告；STEP File Analyzer 只作外部预检。
4. P1 代码需把失败、绑定漂移和 viewer 证据接入真实验收。

## 通过标准

- Controlled：12 mm PASS、8 mm FAIL、`NEW_FAIL`，五类变体有明确结果。
- NIST：7 个文件可批量读取，CTC 02/04 的 assembly 关系可审计。
- TABBY：可加载、定位、隔离、高亮、测量并保留截图和性能数据。

推荐顺序：Controlled → NIST → TABBY。先证明可重复验证，再扩大标准覆盖和车辆尺度演示。

资料入口：

- [数据总清单](../fixtures/manifest.yaml)
- [Controlled Fixture 合同](../fixtures/controlled/controlled-fixture-spec.yaml)
- [P1 实现待办](GPT_IMPLEMENTATION_REQUEST.md)
- [GitHub 协作规则](GITHUB_GPT_COLLABORATION.md)
