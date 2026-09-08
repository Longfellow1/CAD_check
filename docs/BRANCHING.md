# Branching & Release Policy

本仓库采用轻量 Trunk-Based Development。

## 分支角色

- `main`：唯一稳定集成主线。只接受通过 CI 的 PR。
- `feat/*`：短期功能开发分支，例如 `feat/p1-real-cad`、`feat/headroom-shadow`。
- `fix/*`：缺陷修复分支。
- `chore/*`：工程治理、CI、依赖或文档维护。
- `release/*`：仅在准备正式交付时建立；不用于日常开发。

## 本地 Codex / GPT 协作规则

1. 所有 Agent 从最新 `main` 创建短期分支，不直接向 `main` 开发。
2. 不使用开发者身份命名长期分支，例如 `gpt/*`、`codex/*` 不作为产品分支语义。
3. 如果本地 Codex 已经在临时分支工作，允许先 push；随后按实际任务将其 PR 到对应 `feat/*` 或直接 PR 到 `main`，合入后关闭临时分支。
4. 一个分支只承载一个可评审目标；不要把数据准备、Geometry Runtime、UI 和其他无关功能混在同一个临时分支。
5. 合入 `main` 前至少要求：Python CI 通过、CAD Integration CI 通过；涉及 Viewer 的变更还应完成本地视觉 smoke review。

## 版本与发布

产品版本不通过长期分支表达。

- `main` 表示当前最佳可运行状态；
- `release/x.y.z` 仅用于发布冻结；
- 发布后使用 Git tag `vX.Y.Z` 固定交付代码；
- Spec 文档版本与软件版本分离，不创建 `mvp-v0.x` 长期开发分支。

## 历史探索分支

以下分支只保留用于短期追溯，不再继续开发：

- `mvp-v0.1`
- `mvp-v0.2-step-occt`
- `gpt/mvp-real-cad-p0`

当前 P0 能力已通过 PR 合入 `main`。后续开发统一从 `main` 分叉。

## 当前下一阶段

官方 P1 工作分支：

`feat/p1-real-cad`

用于接入公开/真实 STEP 数据、验证 Import/Binding/Geometry 边界；任何本地 Codex 临时分支都应与该分支或 `main` 做显式 compare/PR，不以 Agent 身份分支作为发布主线。
