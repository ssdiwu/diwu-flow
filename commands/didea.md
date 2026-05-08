---
description: 想法捕获容器——挂住灵感并连接下游判断/收束/执行链
argument-hint: "[动作: create/list/show/refine/archive/push] [想法标题或描述]"
allowed-tools: Read, Bash
effort: normal
---

# /didea — 想法捕获

> 入口容器层命令。把灵感挂到 `.diwu/ideas/`，并可选择推送到下游 skill 或 GitHub Issue。

## 执行步骤

1. 解析动作参数（create/list/show/refine/archive/push）
2. create：调用 `didea_core.py create --title <标题> [--body <正文>] [--tags <标签>]` 生成本地 .md
3. list：调用 `didea_core.py list [--status 过滤]` 输出摘要表
4. show：调用 `didea_core.py show --id N` 显示完整内容
5. refine：调用 `didea_core.py refine --id N --content <补充>` 完善想法
6. archive：调用 `didea_core.py archive --id N` 归档想法
7. push：按目标调用 `didea_github.py push --id N --yes` 或输出下游建议

## 输出

JSON 结构化结果或下游衔接建议。

## 完整规范

能力边界、双入口模型、动作门控、下游接口契约详见 **`skills/didea/SKILL.md`**。
