---
description: 启动连续任务循环
argument-hint: "[--max-tasks N] [--mode {session|cron}] [--interval <min>]"
allowed-tools: Read, Bash
effort: low
---

# /dloop — 连续任务循环

> 执行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dloop.py start [--max-tasks N] --cwd <项目根目录>` 启动循环。

## 用法

```bash
# Session 模式（默认）
/dloop                             # 自动取启动时全部 InSpec + InProgress 任务数作为快照
/dloop --max-tasks 5               # 最多执行 5 个任务
/dloop --max-tasks 0               # 无限模式，直到无可执行任务
/dloop --session-id <sid>          # 传入真实 session ID（可选，首次 Stop 事件自动绑定）

# Cron 模式（跨 session 调度）
/dloop --mode cron --interval 3m   # 每 3 分钟触发一次新 session 执行 /drun
/dloop --mode cron --interval 5m --max-tasks 10  # 每 5 分钟，最多 10 个任务
```

## 运行时真相源

- loop 元数据保存在 `.diwu/dtask-state.json.dloop`
- 不再把 `.diwu/dloop-state.json` 当作长期真相源；它只作为 legacy 输入，在 `start/status/stop_decision` 中一次性迁移
- 普通 `InProgress` owner 保存在 `.diwu/dtask-state.json.task_sessions`
- dloop state 新增字段：`mode`（"session"|"cron"）、`cron_job_id`（CronCreate 返回的 job ID）

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

## Cron 模式

`--mode cron` 将循环执行从"同一 session 内循环"变为"Cron 定时触发独立 session"。每次 iteration 冷启动读取 `dtask.json` 执行 `/drun`，session 结束后等下次 Cron 触发。

- **启动**：`/dloop --mode cron --interval <min> [--max-tasks N]`
- **状态**：`/dloop status` 显示 `mode: cron` + `cron_job_id: <job-id>`
- **停止**：`/dstop` 自动清理 CronJob + dloop state
- **降级**：若 CronCreate 不可用，回退到 session 模式并输出 warning

详见 `skills/dloop/SKILL.md` "Cron 模式详解" 章节。
