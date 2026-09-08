# CAD Check — Stage-2 STEP / OCCT Capability MVP

当前分支：`mvp-v0.2-step-occt`

本阶段把 v0.1 的 Primitive Demo 推到真实 STEP/OCCT 实验链：

```text
STEP
→ STEPCAFControl_Reader / XCAF
→ Assembly / Occurrence Inventory
→ Model Readiness
→ Manual Exact-path Binding
→ VerificationCase
→ OCP/OCCT B-Rep Executor
→ V1/V2 Regression
→ Evidence + trace.jsonl
→ ocp-tessellate
→ three-cad-viewer
```

## 一键启动

要求 Python 3.11、Node.js 20+：

```bash
./scripts/bootstrap.sh
./start.sh
```

浏览器打开 `http://127.0.0.1:8000`。

`bootstrap.sh` 使用 `pip --isolated`，避免本机 `global.user=true` 等 pip 用户配置污染。

## 核心命令

```bash
python tools/generate_step_fixture.py   # 生成 V1/V2 XCAF STEP
python tools/readiness.py               # STEP / BRep / Binding / pair readiness
python tools/run_step_demo.py           # 真实 OCP 回归
python tools/register_model.py model.step --model-id public_vehicle --version V1
pytest -q tests/test_stage2_step.py
```

## 当前已经进入代码的能力

- `STEPCAFControl_Reader` + XCAF Assembly/Occurrence tree；
- STEP schema / source unit / BRep validity / empty shape / duplicate bbox / coordinate contract Readiness；
- 人工 exact occurrence-path Binding；
- `BRepExtrema_DistShapeShape` Minimum Clearance + 最近点；
- Directional Distance（当前明确标记为 `bbox_axis_extrema` 近似）；
- XCAF occurrence transform 的 Angle / Orientation；
- 18 条现有 VerificationCase 对真实重新导入 STEP 执行；
- V1/V2 Regression；
- `result.json`、`trace.jsonl`、Evidence PNG 落盘；
- `ocp-tessellate` → `three-cad-viewer` WebGL Viewer；
- CI 中安装 OCP、生成 STEP、重新导入、执行测试和构建 Web。

## Controlled Fixture 的意义

Controlled Fixture 不是绕过 STEP：几何先由 OCP/XCAF 写出 STEP，然后应用再次通过 STEPCAF/XCAF Reader 导入，所有 Check 都对重新导入的 TopoDS Shape 执行。因此它可以验证 STEP Boundary、OCP Geometry、Binding、Regression、Evidence 的代码闭环。

## 仍然不宣称

- CATIA → AP242 企业保真度已验证；
- 真实车型 Binding Reuse Rate 已验证；
- Directional Distance 当前近似等于企业正式测量方法；
- Headroom / Visibility / Dynamic DMU 已支持；
- 当前结果可用于量产工程签核。

这些仍然属于真实企业数据 Pilot 要回答的问题。
