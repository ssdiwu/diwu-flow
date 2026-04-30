---
description: 启动单任务执行器
argument-hint: "[task-id 可选]"
allowed-tools: Read, Bash
effort: low
---

# /drun — 单任务执行

调用 `drun` Skill 执行单任务主循环：Preflight → 上下文恢复 → 任务选择 → 实施 → 验证 → 记录。

> 完整方法论见 `skills/drun/SKILL.md`。

## 快速开始

- 输入 `/drun`：恢复当前 session 可继续的唯一任务。
- 若存在 `InProgress` 任务：`/drun` 只恢复 **当前 session 在 `.diwu/dtask-state.json.task_sessions` 中持有的 owner**。
- 若当前无 `InProgress`：`/drun` 选择第一个可执行的 `InSpec` 任务，并先通过 `python3 scripts/dtask_transition.py claim` 把它显式切到 `InProgress`，再开始实施。

## 运行时真相源

- `dtask.json`：任务内容与 `status` 的真相源。
- `dtask-state.json`：运行态 owner 与 dloop 元数据真相源。
- `dtask_transition.py`：唯一允许同时修改 `dtask.json.status` 与 `dtask-state.json` 的入口。

> 没有完成 `claim` 进入 `InProgress` 的任务，不允许直接开始实施。

## 与 /dloop 的关系

- `/drun`：单任务执行，做完即停。
- `/dloop`：多任务连续执行，loop 元数据写在 `.diwu/dtask-state.json.dloop`。

## 常见结果

- `继续当前任务`：当前 session 命中 owner 匹配的 `InProgress`。
- `选择下一个 InSpec`：通过 `dtask_transition.py claim` 接管新任务后开始。
- `PENDING REVIEW`：超前实施达到上限，停止并等待人工验收。
- `invalid runtime state`：`dtask-state.json` 缺失 owner、损坏或与 `dtask.json` 冲突；此时不会自动恢复 чужой 任务。
