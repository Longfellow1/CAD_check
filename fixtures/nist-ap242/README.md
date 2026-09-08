# NIST AP242 选集

## 目的

NIST 这套数据只承担 STEP/AP242/XCAF 导入链的可信度验证：文件头、schema、实体/属性、PMI、validation properties、assembly 和基础格式健康。它不是汽车产品数据，也不是本项目的 V1/V2 版本真值。

NIST 官方页面说明 STC（Simplified Test Cases）是 2023 年从 FTC 简化而来，移除了部分复杂 PMI；官方测试数据、CAD 模型和 STEP 文件可以无使用限制使用，但应在材料中致谢，且不能把 NIST logo 用于宣传。`selected/` 中的 7 个 STEP 是仓库交付物；`source/` 下的原压缩包仅作为本机下载缓存，不进入普通 Git 历史，manifest 保留其来源、大小和 SHA-256。

可复现下载入口也登记在 manifest：

- [NIST PMI STEP files](https://www.nist.gov/document/nist-pmi-step-files)
- [NIST STC PMI v4](https://www.nist.gov/document/nist-stc-pmi-v4)
- [NIST MTC assembly CAD models](https://www.nist.gov/document/nist-cad-models-mtc-assembly)

## 本地选集

| 子集 | 文件 | 用途 |
| --- | --- | --- |
| STC | `selected/stc/nist_stc_06...` 至 `nist_stc_10...` | AP242 schema/PMI/实体导入的连续样本；文件名已标出 edition |
| CTC | `selected/assembly/nist_ctc_02...`、`nist_ctc_04...` | assembly 候选对；NIST 页面说明 CTC 02 和 04 可组合，需由导入器报告实际树和变换 |
| reference | `selected/reference/*.txt` | NIST 自带版本说明和 STEP 文件说明 |
| source | 三个本机 `.zip` | 原始下载缓存；不作为仓库交付物；`NIST-MTC-Assembly.zip` 是参考 CAD assembly，不作为当前 STEP 运行输入 |

每个文件的 SHA-256、大小和 AP242 edition 在 [../manifest.yaml](../manifest.yaml) 登记。不要用文件名推断业务语义；PMI 预期应以 NIST STEP File Analyzer 对照报告为准。

## 验收动作

1. 对 `selected/` 的 7 个 `.stp` 做 SHA-256 校验。
2. 读取每个文件的 `ISO-10303-21` 头，并确认 `FILE_SCHEMA` 为 AP242；导入器还要输出单位、根节点、shape 数量和异常。
3. 用 OCP/OCCT 读取并遍历 XCAF assembly；至少记录 label、实例路径、变换、shape/solid 数量和坏 shape。
4. 在 Windows + Excel 环境中（如果要做外部预检）运行 NIST STEP File Analyzer，保存生成的报告；它不是 CAD_check 的运行时依赖。
5. 对 CTC 02/04 分别导入并记录是否能识别为可组合 assembly，不把“能打开文件”当作 assembly 通过。

## 证据边界

- NIST 文件适合证明“我们的 STEP reader 和 AP242 对照链能处理公开标准案例”。
- NIST 文件不适合证明“我们的系统理解了汽车零件语义”或“V1 到 V2 的 binding 没有漂移”。
- NIST README 明确提示这些文件可能包含语法错误；发现错误时要保留原始报告，不能静默修复后再宣称通过。

来源：

- [NIST MBE PMI Validation and Conformance Testing](https://www.nist.gov/ctl/smart-connected-systems-division/smart-connected-manufacturing-systems-group/mbe-pmi-0)
- [NIST STEP File Analyzer and Viewer](https://www.nist.gov/services-resources/software/step-file-analyzer-and-viewer)
