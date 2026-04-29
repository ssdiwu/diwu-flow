---
name: dloop
version: "1.0"
type: rule
description: "连续任务循环——基于 dtask.json 自动执行多个任务直到停止条件满足，每轮包含 drec 记录写入"
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
  - dvfy
  - djug
  - dcorr
  - drec
effort: high
argument-hint: "[--max-tasks N]"
---

# diwu-loop

连续任务循环：基于 dtask.json 自动执行多个任务直到停止条件满足。

> **与 /drun 的关系**：/drun = 单任务执行器（做一件事做完就停）。/dloop = 连续循环调度器（做多件事自动续跑）。dloop 内部复用 drun 的单轮执行协议，并在其基础上追加 **drec（每轮记录）** + 循环驱动。

---

## 生命周期

```
1. 启动：/dloop 创建 .diwu/dloop-state.json
2. 执行：每轮循环
3. 判定：Stop hook 读取 dloop-state.json 决定继续/停止
4. 结束：任一停止条件触发 → 最终 recording → 清理状态文件
```

## 每轮完整流程（纯自动，无暂停）

```
选任务(InSpec) → dtask(实施) → dvfy(验证) → djug(判定)
       ↓ 通过              ↓ 失败
  dcorr(纠偏) ←──────────┘
       ↓
  drec(写 recording) ← 每轮必做，记录本轮任务结果
       ↓
  更新 dloop-state.json (iteration++, completed_task_ids++)
       ↓
  Stop hook 判定: 继续下一轮 or 停止
```

> **需要单步执行？用 `/drun`。** /dloop 不提供 step 模式——职责分离，避免模式切换复杂度。

## 停止条件（OR，任一触发即停止）

| # | 条件 | 说明 |
|---|------|------|
| 1 | 无可执行任务 | dtask.json 中无未阻塞的 InSpec 任务，且无 InProgress 任务（InReview/InDraft/Done/Cancelled 不算可执行） |
| 2 | 达到 max_tasks 上限 | completed_task_ids.length >= max_tasks |
| 3 | PENDING REVIEW | 超前实施达 review_limit 上限 |
| 4 | 用户取消 | 执行 `/dend` |

## 循环状态文件（`.diwu/dloop-state.json`）

```json
{
  "active": true,
  "session_id": "<CLAUDE_CODE_SESSION_ID>",
  "started_at": "2026-04-30T12:00:00Z",
  "completed_task_ids": [1, 2, 3],
  "current_iteration": 3,
  "max_tasks": 10,
  "stopped_at": null,
  "stop_reason": null
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `active` | bool | 循环是否活跃 |
| `session_id` | string | 启动循环的 session ID（用于隔离） |
| `started_at` | string | ISO 8601 启动时间戳 |
| `completed_task_ids` | int[] | 已完成的 task ID 列表 |
| `current_iteration` | int | 当前迭代次数（从 1 开始） |
| `max_tasks` | int | 最大任务数限制（0=无限） |
| `stopped_at` | string/null | 停止时间（运行中为 null） |
| `stop_reason` | string/null | 停止原因（运行中为 null）|

## Session 隔离

- 状态文件含 `session_id`，确保只有启动循环的 session 能驱动它
- 其他 session 的 Stop hook 检测到 session_id 不匹配时直接 allow stop
- 防止一个项目的循环干扰同项目其他 session

## 与 stop_decision.py 的集成

`/dloop` 改变了 `stop_decision.py` 的行为模式：

**默认模式**（无 dloop-state.json）：
- InProgress 任务 → block（断点恢复，防丢失）
- 其他情况 → allow stop（不驱动续跑）

**循环模式**（dloop-state.json 存在且 active）：
- 读取状态文件，检查停止条件
- 未命中停止条件 → block + 注入下一任务信息（含 🔄 iteration N/M）
- 命中停止条件 → **输出阶段报告** → 清理状态文件 → allow stop

## 循环结束：自动阶段报告

当任何停止条件触发时，`stop_decision.py` 自动：

1. **生成阶段报告**（输出到 stderr），包含：
   - 停止原因、启动/结束时间、总迭代次数
   - 已完成任务列表（✅ Task#N 标题）
   - 剩余任务列表（📋 InSpec / 🔄 InProgress / 👀 InReview）
2. **删除 `.diwu/dloop-state.json`**
3. 允许 session 正常结束

报告格式示例：
```
==================================================
🏁 DLOOP 阶段报告
==================================================
停止原因 : 达到任务上限 (max_tasks=5)
启动时间   : 2026-04-30T12:00:00Z
结束时间   : 2026-04-30T14:23:45Z
总迭代次数 : 5
任务上限   : 5

--- 已完成任务 ---
  ✅ Task#1 修复 dstat SKILL.md 缺陷
  ✅ Task#3 task_entry_guard 软提醒改造

--- 剩余任务 ---
  📋 Task#5 设计 dloop 拆分方案 [InSpec]
==================================================
```

## 安全限制

- `--max-tasks N`（默认 10，0=无限）：防止无限循环失控
- `/dend` 可随时手动取消
- session_id 隔离防止跨 session 干扰
- 被 blocked_by 阻塞的 InSpec 任务立即停止（不重试）

## 适用场景

- 批量处理多个小任务（bugfix 集合、refactor 系列）
- 已有完整 dtask 规划，信任 Agent 自主执行
- 不需要每步确认的批量交付场景

> 想逐步审查每个任务的产出？用 `/drun` 逐个执行。
