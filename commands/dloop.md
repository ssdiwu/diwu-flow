---
description: 启动连续任务循环
argument-hint: "[--max-tasks N] [--interval <min>]"
allowed-tools: Read, Bash
effort: low
---

# /dloop — 连续任务循环（Cron 驱动）

> 执行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dloop.py start --interval <min> [--max-tasks N] --cwd <项目根目录>` 启动循环。

## 用法

```bash
# 启动 cron 模式循环（每 3 分钟触发一次）
/dloop --interval 3m
/dloop --interval 3m --max-tasks 5         # 最多执行 5 个任务
/dloop --interval 5m --max-tasks 0         # 无限模式，直到无可执行任务
```

## 运行时真相源

- loop 元数据保存在 `.diwu/dtask-state.toml.dloop`
- 不再把 `.diwu/dloop-state.json` 当作长期真相源；它只作为 legacy 输入，在 `start/status/stop_decision` 中一次性迁移
- 普通 `InProgress` owner 保存在 `.diwu/dtask-state.toml.task_sessions`
- dloop state 字段：`mode`（固定 `"cron"`）、`cron_job_id`（CronCreate 返回的 job ID）

## 状态与停止

- `start`：启动新 loop；若已存在活跃 loop owner，返回 `already_running`
- `status`：显示当前 iteration / completed / max_tasks
- `stale_cleaned`：检测到 terminal stale 后自动清理残留 loop 元数据
- `/dstop`：停止 dloop 循环（清除 `.diwu/dtask-state.toml.dloop`），不负责 stale 检测

## Stale-State 规则

- `completed_task_ids.length >= max_tasks`
- 无可执行任务（无未阻塞 `InSpec` 且无 `InProgress`）
- 命中 `PENDING REVIEW`

## 与 stop_decision.py 的关系

- **仅 cron 模式**：`stop_decision.py` 读取 `.diwu/dtask-state.toml.dloop`，调用 `decide_cron_mode()` 判断终止或放行
- 未命中停止条件时：Stop hook 允许 session 自然结束（等下次 Cron 触发）
- 终止条件命中：生成阶段报告 + 清理 dloop + 提示执行 `/dstop`

详见 `skills/dloop/SKILL.md` "Cron 模式详解" 章节。
