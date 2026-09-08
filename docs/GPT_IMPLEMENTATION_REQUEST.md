# P1 真实 CAD 实现待办

## 目标

在 P0 已合入 `main` 的基础上，接入可复现的真实 CAD 测试数据，形成“导入—规则—回归—三维证据”的 P1 验收闭环。

## 实现任务

1. 读取 `fixtures/manifest.yaml`，保留原始文件哈希，不在运行时改写数据。
2. 接入 Controlled Fixture 生成与批跑：V1 间隙 12 mm 为 PASS，V2 间隙 8 mm 为 FAIL，版本结果为 `NEW_FAIL`；覆盖缺件、路径漂移、稳定 ID 漂移和换件。
3. 接入 NIST 7 个 AP242 文件，输出 schema、单位、assembly、shape 数量和异常报告；CTC 02/04 的树结构要可审计。
4. TABBY 官方 STEP 补齐后，完成车辆尺度加载、定位、隔离、高亮、测量和截图。
5. 规则结果补充 `engineering_domain`、`verification_method`、`executor`，不把验证方法简化成“自动/手动”。
6. 保持失败阻塞：binding、测量或证据失败不能返回成功结论。

## PR 验收

- `pytest -q`、Controlled 批跑、NIST 批跑和 `npm run build` 结果可复现。
- 提供 V1/V2 实测值、状态、回归状态和一份 viewer/evidence 证据。
- 说明依赖、接口、manifest 和原始数据哈希是否变化。

## 暂不做

AI 规则编译、自动语义绑定、企业权限、数据库/消息队列和真实温度场仿真不进入本轮。
