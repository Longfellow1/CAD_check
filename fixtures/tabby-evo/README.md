# Open Motors TABBY EVO

## 目的

TABBY EVO 是公开的 EV platform 数据，适合验证汽车尺度下的 viewer、加载性能、基础 clearance/ground distance/angle 和产品演示叙事。它不承担 AP242 conformance，也不承担 Controlled Fixture 的 golden truth。

## 来源状态

官方页面仍标明 2-seat 和 4-seat 的 STEP 3D source files、发布日期和 MD5，并声明 TABBY by Open Motors（formerly OSVehicle）采用 CC BY-SA 4.0。历史页面中的 Google Drive 文件 ID 已记录在 [../manifest.yaml](../manifest.yaml)，但 2026-09-08 从本机访问这些历史链接返回 HTTP 404，因此当前没有把未验证镜像放入仓库。

正式数据准备完成的判据：

1. 从官方 [Open Motors download page](https://www.openmotors.co/download/) 当前可用入口下载 2-seat 或 4-seat STEP archive；优先选择一个完整 assembly，不要只拿截图或单个零件。
2. 将原始 archive 保存在 `source/`，解压后的 STEP 保存在 `source/extracted/` 或由 GPT 约定的固定路径；不要改原文件名。
3. 保存下载页面/许可证据，并记录文件大小、SHA-256；官方页面的 MD5 只作为交叉核对，不替代本地 SHA-256。
4. 在 `manifest.yaml` 的 `source_records` 补上实际文件名、大小、SHA-256 和下载日期。
5. 在 viewer 首次加载前完成单位、车辆前进方向、地面基准和 root assembly 的人工确认。

## 许可与归属

分发或演示 TABBY 数据时保留 Open Motors 归属和 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 链接。衍生材料要评估 ShareAlike 要求。不得把 TABBY 或 Open Motors 的数据说成 OEM 量产车型或 NIST conformance ground truth。

## MVP 用例

- 首次加载、fit-to-view、隐藏/隔离、对象高亮和截图。
- 记录导入耗时、三角面/shape 数量、浏览器首屏时间和内存峰值。
- 选择可解释的底盘/电池/车轮/结构对象，展示一个基础空间测量或离地测量。
- 将 viewer 结果与对象 ID、模型版本和 trace 关联；不要把渲染 mesh 的近似值当作后端精确测量值。

若官方入口长期不可恢复，TABBY 只能作为“待补齐的车辆演示数据”，不能阻塞 Controlled Fixture 和 NIST 两条 MVP 验收主线。
