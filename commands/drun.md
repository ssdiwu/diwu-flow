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

- `auto`（默认）：全自动循环，完成一个任务后自动选下一个
- `step`：每步完成后暂停等待确认

需提前准备好 task.json（可用 `/dtask` 创建）。
