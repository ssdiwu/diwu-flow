---
name: dloop
version: "3.0"
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
- 循环状态必须持久化到 `.diwu/dtask-state.json.dloop`，禁止仅保存在内存中
- 收到 `decision: block` 时必须发起完整的 `/drun` 执行本轮任务，不得跳过

# dloop

Cron 定时触发 /drun 的跨 session 调度器。只做三件事：初始化循环状态、检查停止条件、配置 Cron 调度。

---

## 职责边界

- 每轮执行**全部委托 /drun**：选任务 → 实施 → 验证 → 记录 → 循环判定
- 不重复 drun 执行协议、不自行选任务、不独立实施
- **唯一模式**：Cron 模式——每次 iteration 由 Cron 定时触发独立 session 执行 /drun

---

## 三段约束

### 启动约束

`/dloop --interval 3m --max_tasks N` → 写入 dloop state(mode=cron, active=true) → 创建 CronJob。启动前自动检测并清理 stale state（详见 `scripts/dloop_state.py classify()`）。

### 循环约束

每次 Cron 触发 = 全新 session 冷启动（从 dtask.json + CLAUDE.md 重建上下文）。可用的跨 session 持久化层：`.diwu/dtask.json`（任务定义）、`.diwu/recording/`（历史记录）、`.diwu/decisions.md`（决策记录）。

### 停止约束（OR，任一触发即停）

| # | 条件 | 结果 |
|---|------|------|
| 1 | 无可执行任务 | 阶段报告 + 清理 + 提示 /dstop |
| 2 | 达到 max_tasks 上限 | 阶段报告 + 清理 + 提示 /dstop |
| 3 | PENDING REVIEW（超前达 review_limit 上限） | 阶段报告 + 清理 + 提示 /dstop |
| 4 | 用户 /dstop | CronDelete + 清理 |

停止时 `stop_decision.py` 自动生成阶段报告并清空 dloop state。commit 前必须确认 dtask-state.json 无 dloop 残留（断言：`s.get('dloop') is None`）。

---

## Agent 行为规范

**Block 时的唯一行为**：收到 `decision: block` 后发起完整 `/drun`，不得跳过或自行选任务。

**禁止**：
- 不调用 /drun 自行实施
- 用 format_task 注入 InSpec 任务实施步骤
- 在 block 时修改 completed_task_ids（写入方是 TaskCompleted hook）

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
