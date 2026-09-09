# 真实头部空间 Fixture

## 用途

用于验证真实 STEP 的导入、Viewer、最小间隙计算和 Evidence/Trace 流程。它不是已确认的工程规则真值。

原始文件暂保留在仓库根目录：

- `1.1.CATPart`：CATIA V5 原生文件
- `9.9.stp`：CATIA V5 导出的 STEP

## 已确认

- CATPart 可识别为 CATIA V5 Part134；当前本机没有 CATPart 读取器。
- STEP 可由 OCCT 读取，单位为 mm，schema 为 `CONFIG_CONTROL_DESIGN`（AP203）。
- STEP 为一个 `/Part134` 节点，含 14 个开放壳、17 个面，无 solid。
- Viewer 可生成三角网格并显示整个 STEP。
- 临时取第 14 个壳为 `head_envelope`、第 2 个壳为 `roof_surface`，最小曲面间隙为 64.474 mm。

## 使用边界

壳序号只用于本轮流程验证，不是稳定绑定。正式案例还需要从 CATIA 或中性格式导出稳定的头部包络、顶棚/边界对象和坐标契约，并补正式 Check Card 阈值。

详细字段见 [`real-headspace-fixture.yaml`](real-headspace-fixture.yaml)。
