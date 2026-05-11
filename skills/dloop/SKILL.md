---
name: dloop
version: "2.0"
description: "当用户要求批量、连续或循环执行多个任务时使用"
depends:
  - dtask
  - drun
effort: low
argument-hint: "[--max-tasks N] [--interval <min>]"
---

## 不可协商规则

- 每轮执行必须全部委托 `/drun`，禁止自行选任务或独立实施
- 禁止重复 drun 的执行协议细节，dloop 只负责循环调度
- 停止条件命中时必须立即终止并提示执行 `/dstop`
- 循环状态必须持久化到 `.diwu/dtask-state.toml.dloop`，禁止仅保存在内存中
- 收到 `decision: block` 时必须发起完整的 `/drun` 执行本轮任务，不得跳过

# dloop

Cron 定时触发 /drun 的跨 session 调度器。只做三件事：初始化循环状态、检查停止条件、配置 Cron 调度。

---

## 职责边界

- 每轮执行**全部委托 /drun**：选任务 → 实施 → 验证 → 记录 → 循环判定
- 不重复 drun 执行协议、不自行选任务、不独立实施
- **唯一模式**：Cron 模式——每次 iteration 由 Cron 定时触发独立 session 执行 /drun

---

## 生命周期（R1）

```
1. 启动：/dloop 写入 dtask-state.json.dloop（含 session_id、max_tasks 快照）
2. 执行：每轮调用 /drun 完成单任务全链路
3. 判定：Stop hook 检查停止条件，决定 block（继续）或 allow stop
4. 结束：任一停止条件触发 → 输出阶段报告 → 清理 loop 元数据
```

---

## 三段约束

### 启动约束

`/dloop --interval 3m --max_tasks N` → 写入 dloop state(mode=cron, active=true) → 创建 CronJob。启动前自动检测并清理 stale state（详见 `scripts/dloop_state.py classify()`）。

### 循环约束

每次 Cron 触发 = 全新 session 冷启动（从 dtask.toml + CLAUDE.md 重建上下文）。可用的跨 session 持久化层：`.diwu/dtask.toml`（任务定义）、`.diwu/recording/`（历史记录）、`.diwu/decisions.md`（决策记录）。

### 停止约束（OR，任一触发即停）

| # | 条件 | 结果 |
|---|------|------|
| 1 | 无可执行任务 | 阶段报告 + 清理 + 提示 /dstop |
| 2 | 达到 max_tasks 上限 | 阶段报告 + 清理 + 提示 /dstop |
| 3 | PENDING REVIEW（超前达 dloop_review_cap 上限） | 阶段报告 + 清理 + 提示 /dstop |
| 4 | 用户 /dstop | CronDelete + 清理 |

停止时 `stop_decision.py` 自动生成阶段报告并清空 dloop state。commit 前必须确认 dtask-state.toml 无 dloop 残留（断言：`s.get('dloop') is None`）。

---

## 循环状态文件（R2）

`.diwu/dtask-state.toml.dloop` 的完整字段语义：

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

| 字段 | 类型 | 写入方 | 读取方 | 说明 |
|------|------|--------|--------|------|
| `active` | bool | `dloop.py start` / `stop_decision.py` | Stop hook / dloop 判定 | 循环是否活跃 |
| `session_id` | string | `dloop.py start`（首次）/ Stop event（替换 dummy） | 全部参与者 | 启动循环的 session 身份标识 |
| `started_at` | string | `dloop.py start` | 报告 | ISO 8601 启动时间 |
| `completed_task_ids` | int[] | **仅 TaskCompleted hook** | `stop_decision.py` | 已完成的 task ID 有序列表 |
| `current_iteration` | int | 每轮 drun 开始时递增 | 报告 | 当前迭代次数（从 1 开始） |
| `max_tasks` | int | `dloop.py start`（来自 --max_tasks 参数） | Stop hook | 最大任务数限制（0=无限） |
| `stopped_at` | string\|null | `stop_decision.py` | 报告 | 停止时间（运行中为 null） |
| `stop_reason` | string\|null | `stop_decision.py` | 报告 | 停止原因（运行中为 null） |

> **关键约束**：`completed_task_ids` 只能由 TaskCompleted hook 写入。dloop SKILL 和 drun **只能读取**此字段，禁止修改。

---

## Agent 行为规范（R3）

**Block 时的唯一行为**：收到 `decision: block` 后，**发起完整的 `/drun`** 执行本轮任务，不得自行选任务或跳过。

**断点恢复是唯一例外**：当 `resolve_session_inprogress_task` 返回 owner 匹配当前 session 的 InProgress 任务时，可优先恢复该任务（format_task 注入详情），但仍需在恢复后继续走 drun 的验证与记录流程。

**禁止**：
- 不调用 `/drun` 自行实施任务
- 用 `format_task` 注入普通 InSpec 任务的实施步骤（只对断点恢复例外）
- 在 block 时修改 dtask-state.json.dloop 的 `completed_task_ids`（写入方是 TaskCompleted hook）

---

## Session ID 绑定策略（R4）

| 场景 | 行为 | 结果 |
|------|------|------|
| 正常流程 | start(`dloop-*`) → Stop(SID) → 绑定 SID | 后续必须匹配 SID |
| Stop 缺失 SID | → 退出 loop mode（不允许驱动循环） | 安全退出 |
| 错误 SID | → 退出 loop mode | 安全退出 |
| 已绑定但新 Stop 不匹配 | → 退出 loop mode，走 default mode | 安全退出 |

**首次绑定机制**：`dloop.py start` 生成的 `dloop-<timestamp>` 为 dummy ID；第一个带真实 session_id 的 Stop event 自动将其替换并持久化。

> **为什么需要这个机制**：Cron 触发的第一个 iteration 可能没有真实 session_id（Cron 自身作为调度器启动），用 dummy ID 占位后由第一个实际执行的 drun session 提供真实 ID 替换。这是一个架构 trade-off——避免了"无 SID 则无法启动"的死锁。

---

## completed_task_ids 维护协议（R5）

- **写入方**：`task_completed.py` hook（TaskCompleted 事件时）
- **写入条件**：(1) `event.task.id` 存在且合法 (2) loop 活跃 (3) loop session_id 匹配事件 session_id (4) 该 task_id 尚未在列表中
- **读取方**：`stop_decision.py` — 仅用于 max_tasks 判定和阶段报告，**不写入**
- **精确语义**：只认 `event.task.id` 原始信号，不使用 fallback heuristic

> **为什么严格限制写入方**：防止并发场景下多 session 同时追加导致 ID 重复或丢失。hook 是 TaskCompleted 事件的唯一确定性执行点。

---

## Session 隔离（R6）

- `dtask-state.json.dloop` 含 `session_id`，确保只有启动循环的 session 能驱动它
- 其他 session 的 Stop hook 检测到 session_id 不匹配时直接 allow stop
- 防止一个项目的循环干扰同项目其他 session

---

## 循环结束：自动阶段报告（R7）

当任何停止条件触发时，`stop_decision.py` 自动：

1. **生成阶段报告**（输出到 stderr），包含：
   - 停止原因、启动/结束时间、总迭代次数
   - 已完成任务列表（Task#N 标题）
   - 剩余任务列表（InSpec / InProgress / InReview）
2. **清空 `dtask-state.json.dloop`**
3. 允许 session 正常结束

---

## 结束检查清单（R8）——必做

停止前 / commit 前必须确认：

- [ ] `s.get('dloop') is None` —— dloop 元数据已清理
- [ ] 无 `active: true` 残留 —— 确认不再有活跃循环标记
- [ ] `dtask-state.toml` 可正常加载解析

> **遗漏后果**：残留的 `dloop.active=true` 被提交后，后续 session 的 Stop hook 可能误判为"循环仍在运行"，导致行为异常。

---

## 已知限制：dummy SID 窗口（R9）

| 现象 | 存在原因 | trade-off |
|------|---------|-----------|
| `start()` 生成 dummy SID (`dloop-*`) | Cron 首次迭代可能无真实 session | 用 dummy 占位换取"无需等待真实 SID 即可启动"的灵活性 |
| 首个 Stop event 替换为真实 SID | 第一个 drun session 提供 | 窗口期内（首次 Stop 前）SID 为 dummy 是已知限制 |

**不影响安全性**：dummy SID 期间循环仍受 max_tasks 和其他停止条件约束。

---

## Stale-State 自动清理（R10）

`dloop.py start` 启动时自动检测并清理 stale state：

| 检测条件 | 清理动作 |
|----------|---------|
| `dloop.active=true` 但对应 session 已不存在 | 设 active=false，保留其余字段供诊断 |
| `dloop` 含 `started_at` 但超过 24h | 标记为 stale，启动时覆盖 |
| `dloop` 缺少必要字段（active/session_id/started_at） | 视为无效，重新初始化 |

> **不自动删除** invalid_state 字段，仅标记和覆盖。避免误删诊断信息。

---

## 安全限制

- `--max_tasks N`（0=无限）：防止失控
- `/dstop` 可随时手动停止
- 被 blocked_by 阻塞的任务立即停止不重试

---

## 适用场景判断锚点

| 场景 | 用 dloop | 用 /drun 逐个 |
|------|---------|-------------|
| 批量小任务（bugfix 集合/refactor 系列） | 是 | 否 |
| 完整 dtask 规划，信任自主执行 | 是 | 否 |
| 需逐步审查每个任务产出 | 否 | 是 |
| 无人值守批量交付 | 是 | 否 |

> 状态文件 schema 和字段定义见 `scripts/dloop_state.py`；Cron 用法和冷启动细节见 `.doc/`。
