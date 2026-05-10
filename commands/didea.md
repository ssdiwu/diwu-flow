---
description: 想法捕获容器——挂住灵感并连接下游判断/收束/执行链
argument-hint: "[动作: create/list/show/refine/archive] [想法标题或描述]"
allowed-tools: Read, Bash
effort: normal
---

# /didea — 想法捕获

> 入口容器层命令。把灵感挂到 `.diwu/ideas/`。

## 执行步骤

1. 解析动作参数（create/list/show/refine/archive）
2. create：调用 `didea_core.py create --title <标题> [--body <正文>] [--tags <标签>]` 生成本地 .md
3. list：调用 `didea_core.py list` 输出摘要表
4. show：调用 `didea_core.py show --id N` 显示完整内容
5. refine：调用 `didea_core.py refine --id N --content <补充>` 完善想法
6. archive：调用 `didea_core.py archive --id N` 归档想法

## 输出

JSON 结构化结果。

## 完整规范

能力边界、双入口模型、动作门控详见 **`skills/didea/SKILL.md`**。
