---
name: drun
description: 触发自动任务执行——读取 task.json 并按 diwu 方法论逐个完成
argument-hint: "[task.json路径] [--mode auto|step]"
---

# /drun — 自动执行

调用 `drun` Skill 执行自动任务运行。

> 完整方法论见 `skills/drun/SKILL.md`

## 快速开始

输入 `/drun` 启动自动执行引擎。引擎会依次执行：Preflight 检查 → 上下文恢复 → 归档检查 → 选择任务 → 实施 → 验证 → 循环。

- `auto`（默认）：自动完成单任务全部步骤（Preflight → 实施 → 验证 → Session 结束），**做完即停**
- `step`：每步完成后暂停等待确认

> 连续执行多个任务请用 `/dloop

需提前准备好 task.json（可用 `/dtask` 创建）。
