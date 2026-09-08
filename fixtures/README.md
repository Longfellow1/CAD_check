# CAD_check MVP 测试数据

这里保存真实 CAD MVP 的本地输入、来源证据、哈希和 golden contract。它不是应用代码，也不承担自动下载或运行时安装依赖。

## 三套数据的职责

| 数据集 | 当前本地状态 | 主要证明什么 | 不应据此证明什么 |
| --- | --- | --- | --- |
| NIST AP242 | 已准备：选定 STEP、官方 README；原压缩包为本机缓存 | STEP/AP242/XCAF 导入链、schema、assembly、PMI/validation-property 外部对照 | 汽车产品尺度、企业语义 binding、版本回归 |
| TABBY EVO | 官方来源和许可已核验；STEP 下载待人工补齐 | 真实车辆尺度、Vehicle Assembly、viewer 观感和基础几何性能 | AP242 conformance、OEM 语义绑定、V1/V2 golden truth |
| Controlled Automotive Fixture | 数据合同已准备；STEP 等待 GPT 生成器 | PASS/FAIL、V1/V2 回归、binding drift、Missing、Evidence、Trace | 企业真实 CAD 的格式保真或工程规范真值 |

推荐测试顺序是 Controlled Fixture → NIST AP242 → TABBY EVO：先证明产品的可重复验证闭环，再证明标准输入链，最后证明车辆尺度下的演示价值。三套数据合起来形成“标准上可信、车辆上看得懂、变化上可验证”的产品证据。

## 文件入口

- `manifest.yaml`：所有数据集的状态、来源、哈希和验收字段。
- `nist-ap242/README.md`：NIST 选集和外部 STEP File Analyzer 使用边界。
- `tabby-evo/README.md`：官方来源、许可和人工下载步骤。
- `controlled/README.md`：受控数据的 golden contract。
- `controlled/controlled-fixture-spec.yaml`：交给 GPT 生成器实现的几何与版本合同。

## 数据纪律

1. 任何 STEP 放入仓库前先计算 SHA-256，并在 `manifest.yaml` 登记。
2. 公共数据只保留原始来源和归属，不把第三方镜像当作官方数据。
3. NIST SFA 是外部预检工具，不是 CAD_check 的运行时依赖；它的 Windows/Excel 前置条件应在人工验收记录中体现。
4. Controlled Fixture 的预期值来自本地合同，不来自测量后反推。若生成器输出不满足合同，应修生成器或 fixture，不应改 golden 值迁就结果。
5. 本目录不包含密钥、账号、私有 OEM 数模或应用代码。

NIST 原始压缩包保存在 `nist-ap242/source/` 仅用于本地复核，已由该目录的 `.gitignore` 排除；协作时以 `nist-ap242/selected/` 和 `manifest.yaml` 为准。
