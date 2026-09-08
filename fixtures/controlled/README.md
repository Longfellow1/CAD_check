# Controlled Automotive Fixture

## 定位

这是软件验证的 golden fixture，不是企业车型真值。它用汽车尺度的简化前舱/底盘部件构造出可解释、可重复的版本变化：V1 电池包到支架的最小间隙为 12 mm，V2 将电池沿 Z 轴下移 4 mm 后为 8 mm；规则阈值为 10 mm，因此 V1 必须 PASS、V2 必须 FAIL，版本比较必须得到 `NEW_FAIL`。

精确的几何、对象路径、变体和预期值见 [`controlled-fixture-spec.yaml`](controlled-fixture-spec.yaml)。当前仓库已有的 Python primitive demo 不能替代这里的 STEP fixture；它的数值和对象保存在代码中，且不是 OCP/OCCT/XCAF 输入。

## 需要 GPT 生成的本地文件

生成器完成后，建议把结果放在 `source/`：

- `controlled_vehicle_v1.stp`
- `controlled_vehicle_v2.stp`
- `controlled_vehicle_mutants/` 下的 label-only rename/path/stable-ID/missing/replaced 变体
- `controlled-fixture-manifest.yaml`：对象 ID、assembly path、单位、坐标系、hash
- `golden-results.yaml`：每个 case 的精确值、状态、回归状态和允许误差

STEP 文件生成后才算 `contract_ready_step_pending` 变为 `ready_local`。生成器不得把规则预期值写入模型文件，也不得在运行时按“最接近的名字”自动修复 binding。

## 变体的验收语义

- **几何变化**：V1/V2 都能稳定绑定时，检查状态按测量值计算；本例是 PASS → FAIL / `NEW_FAIL`。
- **只改显示名**：如果稳定对象 ID 和 assembly path 保持不变，绑定必须继续成功，结果应为 PASS/`UNCHANGED`；这证明系统没有把 label 当成唯一身份。
- **改 assembly path 或稳定对象 ID**：严格模式下应暴露 binding drift，当前 Check Status 用 `BLOCKED`，回归用 `NON_COMPARABLE`；只有人工更新 alias/binding manifest 后才允许继续比较。
- **删除对象**：不能被当作 PASS 或自动替换；应为 `BLOCKED` / `NON_COMPARABLE`，trace 要指出缺失的稳定 ID/path。
- **替换对象**：即使新对象形状相似，也必须视为新的对象，不能静默继承旧 binding。

这套语义把“当前版本是否满足”与“跨版本是否可比较”分开，避免绑定漂移被误报成工程回归或误报成通过。
