# Branching & Release Policy

本仓库当前只保留两条长期远端分支：

- `main`：稳定基线 / 可发布代码。
- `dev`：唯一日常开发分支。

## 协作规则

1. GPT、Codex 和本地人工开发统一从 `dev` 开始工作。
2. 临时本地分支可以创建，但原则上不长期推送到远端；确需远端协作时，任务完成后立即合回 `dev` 并删除。
3. 日常功能、数据准备、修复和文档都先进入 `dev`，不再建立长期 `feat/*`、`gpt/*`、`mvp-*` 分支。
4. `dev` 保持可运行；关键提交应通过 Python CI 和 CAD Integration CI。
5. 一个阶段验证完成后，通过 PR 将 `dev` 合入 `main`。
6. `main` 不承载未验证开发。

## 发布规则

- 软件版本通过 Git Tag 标记，例如 `v0.1.0`、`v0.2.0`。
- 如确需发布冻结，可临时创建 `release/x.y.z`，发布后删除。
- Spec 文档版本与软件版本分离。

## 当前基线

- `main`：P0 稳定基线。
- `dev`：包含 P1 real-CAD fixtures/data readiness 工作，作为后续唯一开发入口。

## Agent 约束

后续给 GPT / Codex 的默认指令统一为：

```text
从 origin/dev 拉取最新代码；
完成任务后提交到 dev；
除非明确要求，不创建新的长期远端分支；
不要直接修改 main。
```
