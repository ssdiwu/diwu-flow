---
name: dtask
description: 任务规划与管理——创建任务、分解需求、编写验收条件
argument-hint: "[功能描述] [category] [blocked_by]"
---

# /dtask — 任务管理

调用 `dtask` Skill 进行任务规划和管理。

> 完整方法论见 `skills/dtask/SKILL.md`

## 快速开始

输入 `/dtask 你的需求描述` 创建新任务。Skill 会引导你完成：需求提炼 → GWT 验收条件定义 → 任务分解 → 写入 task.json。

支持 category：functional / ui / bugfix / refactor / infra
