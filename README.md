# CAD Check

Automotive Engineering Verification MVP for STEP / AP242 + OCCT.

## 当前开发分支

- `main`：稳定基线
- `dev`：唯一开发分支

## 本地启动

```bash
./scripts/bootstrap.sh
./start.sh
```

`start.sh` 当前使用 `server.app_v2:app`，在既有工程校验 API 上叠加大型模型 Web Streaming / View Derivative 能力。

浏览器打开：

```text
http://127.0.0.1:8000
```

## 当前 MVP 能力

- STEP / AP242 → STEPCAF / XCAF
- Assembly / Occurrence Inventory
- 人工 exact-path Binding
- OCCT 三类基础执行器
- V1 / V2 Regression
- Evidence / Trace
- three-cad-viewer WebGL
- 大模型 View Derivative：Manifest + Chunk + LOD Preview + Disk Cache
- 前端真实 Part/Chunk 加载进度
- 低频能力折叠到“更多”

## 大模型 Web 加载

Scania 等大模型不再走整车单体 Viewer JSON。当前 Web 默认链路：

```text
STEP/XCAF/BRep
  ├─ Engineering Truth → Geometry Check
  └─ View Derivative → Manifest → Chunk Cache → Progressive Web Viewer
```

详细设计见：`docs/LARGE_MODEL_WEB_LOADING.md`。

## 测试

```bash
python -m pytest -q
cd web && npm run build
```

当前阶段重点验证：

1. STEP/XCAF 真实读取；
2. OCCT 几何执行；
3. Regression；
4. 大模型不再构造 1.56GB 单体 Viewer JSON；
5. Chunk 渐进加载、缓存和真实进度；
6. Evidence / Trace 可复核。
