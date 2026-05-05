---
description: 启动连续任务循环
argument-hint: "[--max-tasks N]"
allowed-tools: Read, Bash
effort: low
---

# /dloop — 连续任务循环

> 执行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dloop.py start [--max-tasks N] --cwd <项目根目录>` 启动循环。

## 用法

```bash
/dloop                             # 自动取启动时全部 InSpec + InProgress 任务数作为快照
/dloop --max-tasks 5               # 最多执行 5 个任务
/dloop --max-tasks 0               # 无限模式，直到无可执行任务
/dloop --session-id <sid>          # 传入真实 session ID（可选，首次 Stop 事件自动绑定）
```

## 运行时真相源

- loop 元数据保存在 `.diwu/dtask-state.json.dloop`
- 不再把 `.diwu/dloop-state.json` 当作长期真相源；它只作为 legacy 输入，在 `start/status/stop_decision` 中一次性迁移
- 普通 `InProgress` owner 保存在 `.diwu/dtask-state.json.task_sessions`

## 状态与停止

- `start`：启动新 loop；若已存在活跃 loop owner，返回 `already_running`
- `status`：显示当前 iteration / completed / max_tasks
- `stale_cleaned`：检测到 terminal stale 后自动清理残留 loop 元数据
- `/dstop`：停止 dloop 循环（清除 `.diwu/dtask-state.json.dloop`），不负责 stale 检测

## Stale-State 规则

- `completed_task_ids.length >= max_tasks`
- 无可执行任务（无未阻塞 `InSpec` 且无 `InProgress`）
- 命中 `PENDING REVIEW`

## 与 stop_decision.py 的关系

- 默认模式：只恢复 owner 匹配当前 session 的 `InProgress`
- loop 模式：`stop_decision.py` 读取 `.diwu/dtask-state.json.dloop`，决定继续下一轮还是输出阶段报告并清理 loop
- 未命中停止条件时：Stop hook 输出 `block` + `请继续执行 /drun 完成下一轮任务`，Agent 收到后发起完整 `/drun`
- `session_id` / `sessionId` 两种事件字段都必须兼容

### Session ID 绑定策略

`/dloop start` 生成 `dloop-<timestamp>` 格式 dummy ID；首次带真实 `session_id` 的 Stop 事件自动将其替换并持久化。此后只有匹配该 session_id 的 Stop 事件才能驱动循环。

> `/drun` 不负责 dloop 生命周期管理；`/dloop` 也不绕过 `dtask_transition.py` 对任务状态的显式接管。
