---
description: 启动连续任务循环
argument-hint: "[--max-tasks N]"
allowed-tools: Read, Bash
effort: low
---

# /dloop — 启动连续任务循环

> 执行 `python3 scripts/dloop.py start [--max-tasks N] --cwd <项目根目录>` 启动循环。

## 用法

```bash
/dloop                # 启动（自动取活跃任务数为 max_tasks）
/dloop --max-tasks 5  # 启动（最多执行 5 个任务）
/dloop --max-tasks 0   # 启动（无限模式，直到无可执行任务）
```

## 参数语义

| 参数 | 行为 |
|------|------|
| 省略 | 自动取启动时 InSpec(未阻塞)+InProgress 任务数作为上限 |
| `--max-tasks N` (N>0) | 手动限制最多执行 N 个任务 |
| `--max-tasks 0` | 无限模式：直到无可执行任务才停止 |

> 启动后新增任务不自动纳入本轮（max_tasks 快照在启动时固定）。

## 子命令

| 命令 | 说明 |
|------|------|
| `start [--max-tasks N]` | 启动 dloop 循环。冲突/无任务时返回错误 JSON |
| `status` | 查询当前 dloop 状态（轮次/完成数/max_tasks） |

## 取消

使用 `/dend` 取消运行中的循环（T3: cancel 归 dend.py 唯一入口）。

## Stale-State 自动清理

`start` 和 `status` 执行时，若发现 `dloop-state.json` 为 `active=true` 但实际循环已终止（terminal_stale），会自动清理残留文件：

- **terminal_stale 判定**：`completed_task_ids.length >= max_tasks` 或无可执行任务
- **start 命中**：清理旧 state → 继续正常启动本轮循环（message 中含清理提示）
- **status 命中**：清理旧 state → 返回 `{ok: true, status: 'stale_cleaned'}`
- **invalid_state**（JSON 损坏）：返回 `{ok: false, status: 'invalid_state_file'}`，不自动删除

> `/dend` 仍是活跃循环的手动取消入口。`/drun` 不承担 dloop-state 生命周期管理。

## 循环驱动

启动后每轮由 `stop_decision.py` hook 驱动：读取状态 → 判断停止条件 → block 或 allow stop。

> **文件操作安全（R1）**：本命令 start 子句写入 `.diwu/dloop-state.json`，写入前确认状态文件当前状态。
