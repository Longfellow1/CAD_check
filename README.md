# CAD Check

Automotive Engineering Verification MVP for STEP / AP242 + OCCT.

## Product Form Lock

CAD Check MVP is an **Electron Desktop Application**.

- 唯一用户入口：Electron App。
- `web/` 目录仅作为 Electron Renderer 的前端源码与构建产物，不代表独立 Web 产品。
- FastAPI / localhost 仅作为 Electron 内部 Python/OCP sidecar 通信层。
- Standalone browser、`./scripts/start-web-dev.sh` 只允许开发调试，不计入功能完成、Demo、用户测试或 MVP Gate。
- 任何功能只有在 Electron 内跑通才算 Done。

## 当前分支

- `main`：稳定基线。
- `dev`：V1.1 文档/开发合同基线。
- `dev-2`：当前 Electron MVP 实现分支。

## macOS 本地启动

```bash
./scripts/bootstrap.sh
./start.sh
```

`./start.sh` 会直接启动 Electron；Electron Main 再拉起并守护 Python/OCP Runtime。正常产品测试不需要、也不应手动打开浏览器。

## Windows x64 本地启动

PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
.\start.cmd
```

## 开发调试：Standalone Web

仅在需要单独调试 Renderer/API 时使用：

```bash
./scripts/start-web-dev.sh
```

浏览器调试模式不是产品形态，也不能作为 Electron MVP 的验收证据。

## 架构

```text
Electron Desktop
├─ Electron Main
│  └─ spawn / health / restart Python Runtime
├─ Electron Renderer
│  └─ web/ frontend bundle + Viewer + UX
└─ Python Runtime
   └─ FastAPI + OCP/OCCT Verification Core
```

核心设计见：

- `docs/MVP_PRODUCT_REQUIREMENTS_V1.md`
- `docs/MVP_TECH_ARCHITECTURE_V1.md`
- `docs/MVP_UX_UI_V1.md`
- `docs/MVP_PROJECT_PLAN_V1.md`
