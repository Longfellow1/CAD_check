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

详细设计见：`docs/LARGE_MODEL_WEB_LOADING.md`。
