# P1 真实 CAD 数据协作

## 当前主线

- `main`：稳定集成主线，当前 P0 已合入。
- `feat/p1-real-cad`：下一阶段唯一官方开发分支。
- `feat/p1-real-cad-fixtures`：本分支，负责 P1 测试数据和验收资料；PR 合入后关闭。
- 分支规则以 [BRANCHING.md](BRANCHING.md) 为准，不使用 Agent 名称建立长期产品分支。

## 本分支范围

本分支只交付 `fixtures/` 和数据验收文档：

- NIST AP242 选集、来源、哈希和导入验收边界。
- Controlled Fixture 的几何、版本和 golden contract。
- TABBY EVO 官方来源与许可记录，等待人工补齐 STEP。
- P1 实现待办和验收标准。

数据侧不修改 `server/`、`web/`、`tests/`、依赖或启动脚本。实现侧不得改写原始 STEP、golden 值和 SHA-256。

## 合并验收

1. NIST 7 个 STEP 可批量读取，并输出 schema、单位、assembly、shape 和异常信息。
2. Controlled V1/V2 达到 12 mm PASS、8 mm FAIL、`NEW_FAIL`；缺件和 binding drift 必须阻塞。
3. TABBY 官方 STEP 补齐后，完成车辆尺度加载、定位、测量和 viewer 证据。
4. CI、数据哈希和本地验收记录完整。

实现侧可从 `feat/p1-real-cad` 建立短期 feature/fix 分支，PR 目标先指向 `feat/p1-real-cad`，通过后再进入 `main`。
