---
name: dloop
version: "2.0"
type: rule
description: "drun 的薄壳循环包装——while(未停止){ /drun }，状态初始化、停止条件判定、驱动续跑均委托 drun 完成每轮执行"
triggers:
  - "用户要求批量执行、连续执行、循环执行多个任务"
  - "用户说 /dloop、循环、批量、全部任务"
keywords:
  - "循环"
  - "批量执行"
  - "连续任务"
  - "dloop"
depends:
  - dtask
  - drun
effort: low
argument-hint: "[--max-tasks N] [--mode {session|cron}] [--interval <min>] [--session-id <sid>]"
---

# dloop

/dloop = `while(未停止) { /drun }`

- 只做三件事：初始化循环状态、检查停止条件、驱动继续
- 每轮执行全部委托 `/drun`：选任务 → 实施 → 验证 → 记录 → 循环判定
- 不重复 drun 的执行协议，不自行选任务，不独立实施

## 生命周期

### Session 模式（默认）

```
1. 启动：/dloop 写入 dtask-state.json.dloop（含 session_id、max_tasks 快照）
2. 执行：同一 session 内循环：/drun → Stop → /drun → Stop ...
3. 判定：Stop hook 检查停止条件，决定 block（继续）或 allow stop
4. 结束：任一停止条件触发 → 输出阶段报告 → 清理 loop 元数据
```

### Cron 模式（`--mode cron`）

```
1. 启动：/dloop --mode cron --interval 3m
   → 写入 dloop state(mode=cron, active=true)
   → 创建 CronJob(prompt="/drun --max-tasks 1")，保存 job_id
2. 执行：每次 Cron 触发独立 session → /drun(读 dtask.json) → session 结束
3. 判定：每次 iteration 的 Stop hook → decide_cron_mode() → 终止或放行
4. 停止：终止条件命中 → 清理 dloop + 提示执行 /dstop
   → /dstop 自动 CronDelete(job_id) + 清理 dloop state
```

## 停止条件（OR，任一触发即停止）

| # | 条件 | 说明 |
|---|------|------|
| 1 | 无可执行任务 | dtask.json 中无未阻塞的 InSpec 且无 InProgress 任务 |
| 2 | 达到 max_tasks 上限 | completed_task_ids.length >= max_tasks |
| 3 | PENDING REVIEW | 超前实施达 review_limit 上限 |
| 4 | 用户停止 | 执行 `/dstop` |

## 循环状态文件（`.diwu/dtask-state.json.dloop`）

```json
{
  "active": true,
  "mode": "session",
  "session_id": "<CLAUDE_CODE_SESSION_ID>",
  "started_at": "2026-04-30T12:00:00Z",
  "completed_task_ids": [1, 2, 3],
  "current_iteration": 3,
  "max_tasks": 10,
  "stopped_at": null,
  "stop_reason": null,
  "cron_job_id": null
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `active` | bool | 循环是否活跃 |
| `mode` | string | `"session"`（默认）或 `"cron"` |
| `session_id` | string | 启动循环的 session ID（session 模式用于隔离；cron 模式记录首次 SID） |
| `started_at` | string | ISO 8601 启动时间戳 |
| `completed_task_ids` | int[] | 已完成的 task ID 列表 |
| `current_iteration` | int | 当前迭代次数（从 1 开始） |
| `max_tasks` | int | 最大任务数限制（0=无限） |
| `stopped_at` | string/null | 停止时间（运行中为 null） |
| `stop_reason` | string/null | 停止原因（运行中为 null）|
| `cron_job_id` | string/null | CronCreate 返回的 job ID（仅 cron 模式）|

## Agent 行为规范

**Block 时的唯一行为**：收到 `decision: block` 后，**发起完整的 `/drun`** 执行本轮任务，不得自行选任务或跳过 drun 协议。

**断点恢复是唯一例外**：当 `resolve_session_inprogress_task` 返回 owner 匹配当前 session 的 InProgress 任务时，可优先恢复该任务（format_task 注入详情），但仍需在恢复后继续走 drun 的验证与记录流程。

**禁止**：
- 不调用 `/drun` 自行实施任务
- 用 `format_task` 注入普通 InSpec 任务的实施步骤（只对断点恢复例外）
- 在 block 时修改 dtask-state.json.dloop 的 `completed_task_ids`（写入方是 TaskCompleted hook）

## Session ID 绑定策略

| 场景 | 模式 | 行为 |
|------|------|------|
| 正常流程 | session | start(`dloop-*`) → Stop(SID) → 绑定 SID → 后续必须匹配 SID |
| Stop 缺失 SID | session | → 退出 loop mode（不允许驱动循环） |
| 错误 SID | session | → 退出 loop mode |
| 已绑定但新 Stop 不匹配 | session | → 退出 loop mode，走 default mode |
| 任意 SID | **cron** | **跳过绑定检查**：每次 iteration 是独立合法 session，不校验 ownership |
| 无 event session_id | **cron** | **放行**：task_entry_guard 显式检查 `mode=="cron"` 后直接放行 |

**首次绑定机制**：`dloop.py start` 生成的 `dloop-<timestamp>` 为 dummy ID；第一个带真实 session_id 的 Stop event 自动将其替换并持久化。

## completed_task_ids 维护

- **写入方**：`task_completed.py` hook（TaskCompleted 事件时）
- **写入条件**：(1) `event.task.id` 存在且合法 (2) loop 活跃 (3) **session 模式**要求 loop session_id 匹配事件 session_id；**cron 模式跳过此检查** (4) 该 task_id 尚未在列表中
- **读取方**：`stop_decision.py` — 仅用于 max_tasks 判定和阶段报告，**不写入**
- **精确语义**：只认 `event.task.id` 原始信号，不使用 fallback heuristic

## Session 隔离

- **session 模式**：`dtask-state.json.dloop` 含 `session_id`，确保只有启动循环的 session 能驱动它
- 其他 session 的 Stop hook 检测到 session_id 不匹配时直接 allow stop
- 防止一个项目的循环干扰同项目其他 session
- **cron 模式**：无 session 隔离——每次 iteration 是独立合法 session，`task_entry_guard` 显式放行所有 Edit/Write

## Cron 模式详解

### 语义

Cron 模式将 `/dloop` 从"**同一 session 内循环控制器**"变为"**跨 session 调度器配置器**"。核心变化：

| 维度 | Session 模式 | Cron 模式 |
|------|-------------|-----------|
| 执行载体 | 同一 Claude Code session 持续存活 | 每次 Cron 触发全新独立 session |
| 循环驱动 | Stop hook 输出 `block` → Agent 发起 `/drun` | Cron 定时触发 → 新 session 自动执行 `/drun` |
| 上下文保持 | 累积（context window 内） | **冷启动**（每次从 dtask.json + CLAUDE.md 重建） |
| 停止方式 | stop_decision 阶段报告 + 清理 | decide_cron_mode 判定 + `/dstop` 清理 CronJob |
| session_id 作用 | ownership 隔离（必须匹配） | 仅记录，不做 ownership 校验 |

### 用法

```bash
# 启动 cron 模式循环（每 3 分钟触发一次）
/dloop --mode cron --interval 3m --max-tasks 0

# 启动带上限的 cron 循环（每 5 分钟，最多 10 个任务）
/dloop --mode cron --interval 5m --max-tasks 10

# 查看状态（显示 mode + cron_job_id）
/dloop status

# 停止（自动清理 CronJob + dloop state）
/dstop
```

### 冷启动链路

每次 Cron 触发的 iteration 是**全新的 Claude Code session**，无累积上下文。可用的跨 session 持久化层：

| 注入层 | 来源 | 可用性 |
|--------|------|--------|
| `.claude/CLAUDE.md` | git 仓库内文件 | 自动加载 |
| `.claude/rules/*` | UserPromptSubmit hook 注入 | 自动加载 |
| `.diwu/dtask.json` | 任务定义真相源 | `/drun` 读取 |
| `.diwu/recording/*.md` | 历史 session 记录 | 文件系统可读 |
| `.diwu/decisions.md` | 设计决策记录 | 文件系统可读 |

> **不足**：细粒度的"为什么选这个方案而不选那个"推理过程可能丢失。由 `recording/` 和 `decisions.md` 部分弥补。

### 停止条件差异

| 条件 | Session 模式 | Cron 模式 |
|------|-------------|-----------|
| 无可执行任务 | → 阶段报告 + 清理 | → 阶段报告 + 清理 + 提示 `/dstop` |
| 达到 max_tasks | → 阶段报告 + 清理 | → 阶段报告 + 清理 + 提示 `/dstop` |
| PENDING REVIEW | → 阶段报告 + 清理 | → 阶段报告 + 清理 + 提示 `/dstop` |
| 用户 `/dstop` | → 立即清理 | → CronDelete(job_id) + 清理 |
| 未命中终止条件 | → block + 继续 `/drun` | → **允许 session 自然结束**（等下次 Cron 触发） |

### 选择指南

| 场景 | 推荐模式 | 理由 |
|------|---------|------|
| 少量任务（<5），快速批量 | session | 无冷启动开销，上下文连续 |
| 大量任务（>5），预计运行时间长 | cron | 不受 context compression 影响 |
| 需要 agent 积累经验（前轮决策影响后轮） | session | 上下文保留 |
| 任务间独立性高（每个任务自包含） | cron | 冷启动代价低 |
| 无人值守批量执行 | cron | 自动持续运行，无需人工续跑 |

## 循环结束：自动阶段报告

当任何停止条件触发时，`stop_decision.py` 自动：

1. **生成阶段报告**（输出到 stderr），包含：
   - 停止原因、启动/结束时间、总迭代次数
   - 已完成任务列表（Task#N 标题）
   - 剩余任务列表（InSpec / InProgress / InReview）
2. **清空 `dtask-state.json.dloop`**
3. 允许 session 正常结束

## 结束检查清单（必做）

循环结束后（无论自然停止、`/dstop` 手动停止、或 `stop_decision` 阶段报告清理）**commit 前**必须确认：

| # | 检查项 | 方法 |
|---|--------|------|
| 1 | `dtask-state.json.dloop` 为 `None` 或 key 不存在 | `python3 -c "import json; s=json.load(open('.diwu/dtask-state.json')); assert s.get('dloop') is None"` |
| 2 | 无残留 `active: true` 的 loop 状态 | `grep 'active.*true' .diwu/dtask-state.json` 应无输出 |
| 3 | **最终文件为干净状态** | `Read .diwu/dtask-state.json`，确认内容为 `{version, task_sessions}`（不含 `dloop`/`pending_recording` 冗余 key） |

> **为什么重要**：`dtask-state.json` 是 tracked 文件。若 `dloop.active=true` 被 commit，任何 clone 该仓库的人执行 `/dloop status` 会看到虚假的"运行中"循环，`/dloop start` 会被 `already_running` 拦截。

> **正确格式**：commit 时 `dtask-state.json` 应为干净状态 `{version: N, task_sessions: {}}`——不含 `dloop`、`pending_recording` 等 key。`stop_decision.py` 清理时先写 `dloop: null`（中间态），后续 `sync_runtime_state()` / `dtask_transition.py release` 覆写时会自然消除这些冗余 key，这是**预期行为**。**只需确认最终不含 `active: true` 即可安全 commit**。

## 安全限制

- `--max-tasks N`（0=无限）：防止无限循环失控
- `/dstop` 可随时手动停止
- session_id 隔离防止跨 session 干扰
- 被 blocked_by 阻塞的 InSpec 任务立即停止（不重试）

## 已知限制：dummy SID 窗口

`/dloop start` 写入 `dloop-<timestamp>` 格式的 **dummy session_id**，真实 SID 要到第一次 `Stop` 事件才由 `stop_decision.py` 绑定。在此窗口内：

- `task_entry_guard.py` 的 dloop fail-fast guard **无法区分 owner 与 foreign session**（dummy SID 不匹配任何真实 SID）
- 当前设计选择**放行**所有 Edit/Write（避免误拦启动 loop 的 agent 自身）
- **residual risk**：foreign session 在此极短窗口内可写入项目文件

> 这是可用性优先的安全权衡。若需消除此窗口，需修改 `dloop.py start` 使其在启动时即接受/推导真实 session ID（独立架构改动，不在当前范围内）。测试锁定了此行为：`TestDloopGuard::test_3_dummy_sid_with_foreign_also_allows`。

## Stale-State 自动清理

`/dloop start` 和 `status` 执行时自动检测 terminal stale state 并清理：

- **terminal_stale 条件**：`completed_task_ids.length >= max_tasks` 或无可执行任务
- **start 命中**：清理旧 state → 继续正常启动（message 含清理提示）
- **status 命中**：清理旧 state → 返回 `stale_cleaned`
- **invalid_state**（JSON 损坏/字段矛盾）：返回 `invalid_state_file`，不自动删除
- **legacy 兼容**：若只存在旧 `.diwu/dloop-state.json`，`start/status/stop_decision` 会先迁移到 `dtask-state.json.dloop`
- **/dstop** 仍是活跃循环的手动停止入口，不负责 stale 检测
- **/drun** 不承担 dloop-state 生命周期管理职责

## 适用场景

- 批量处理多个小任务（bugfix 集合、refactor 系列）
- 已有完整 dtask 规划，信任 Agent 自主执行
- 不需要每步确认的批量交付场景

> 想逐步审查每个任务的产出？用 `/drun` 逐个执行。
