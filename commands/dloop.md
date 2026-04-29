---
description: "启动连续任务循环"
argument-hint: "[--max-tasks N]"
---

# /dloop — 启动连续任务循环

基于 dtask.json 自动连续执行多个任务，直到停止条件满足。

## 前置检查

1. **状态文件冲突**：检查 `.diwu/dloop-state.json` 是否已存在
   - 存在 → 报错：`⚠️ dloop 已在运行（iteration N）。请先执行 /dend 取消当前循环。`
   - 不存在 → 继续

2. **任务可用性**：读取 `.diwu/dtask.json`，确认存在 InSpec 或 InProgress 任务
   - 无可执行任务 → 报错：`❌ 无可执行任务。dtask.json 中没有 InSpec/InProgress 状态的任务。请先 /dtask 规划任务。`

## 启动流程

1. 解析参数：
   - `--max-tasks N`：最大任务数（默认 10，0=无限）
2. 创建 `.diwu/dloop-state.json`：
   ```json
   {
     "active": true,
     "session_id": "<当前 CLAUDE_CODE_SESSION_ID>",
     "started_at": "<date -u +%Y-%m-%dT%H:%M:%SZ>",
     "completed_task_ids": [],
     "current_iteration": 0,
     "max_tasks": <N>,
     "stopped_at": null,
     "stop_reason": null
   }
   ```
3. 输出启动确认：
   ```
   🔄 dloop 已启动 (max_tasks: <N>)
   首轮开始：Task#<id> <title>
   ```
4. 开始第一轮执行（按 drun 协议选任务并执行）

## 后续循环

首轮及后续循环由 `stop_decision.py` 驱动：
- 每次 Stop 事件时读取 `dloop-state.json`
- 未命中停止条件 → block + 注入下一任务
- 命中停止条件 → 清理状态文件 + allow stop

## 纯自动模式

每轮完成后**自动进入下一轮**，无暂停机制。

需要单步执行？用 `/drun`。职责分离，不搞模式切换。
