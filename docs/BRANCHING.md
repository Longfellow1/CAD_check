# Branching & Release Policy

本仓库采用两条长期分支：

- `main`：稳定基线；
- `dev`：唯一开发分支。

GPT / Codex / 本地开发均从 `dev` 接续。临时分支允许存在于本地，但任务完成后合入 `dev`，不作为远端长期主线。

阶段验证完成后通过 PR 将 `dev` 合入 `main`；发布版本使用 Git tag 固定，不再用 `mvp-*`、`gpt/*`、`codex/*` 等长期分支表达版本或开发者身份。

当前大模型 Web Viewer 优化、真实 STEP 数据接入、Verification Case 扩展均在 `dev` 上迭代。
