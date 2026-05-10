# Hooks 导航

> diwu-flow 的 11 个 hook 脚本，按事件触发时机组织。
> 回答：**什么事件 → 触发哪个 hook → 它访问什么数据**。
> 完整注册以 `hooks/hooks.json` 为真值来源。设计原则见 `.doc/架构规范.md` Part C。

## 事件 → Hook 映射

| 触发事件 | Hook 脚本 | 核心职责 | 数据访问层 |
|---------|----------|---------|-----------|
| SessionStart | session_start.py | 初始化 session_id、sync runtime、注入 pitfalls | L2(write) |
| TaskCreated | task_created_validate.py | 新建任务字段校验 | L1(read) |
| PreToolUse(Edit\|Write) | task_entry_guard.py | 实施入口门控：dtask 状态检查 | L1+L2(read) |
| PreToolUse | context_monitor.py | 上下文量监控 + checkpoint 触发 | L0(目标) |
| PreToolUse | drift_detect_pre.py | 上下文漂移检测 | L0(目标) |
| ExitPlanMode | plan_exit_hint.py | Plan→Dtask 强提示 + marker 写入 | L0 |
| PreCompact | pre_compact.py | 压缩前 checkpoint 写入 | L0(目标) |
| Stop | stop_decision.py | 录用提醒 + decisions 提醒 + dirty 检测 | L0(目标) |
| Stop | stop_archive.py | 归档阈值检测（task + recording） | L1(read) |
| TaskCompleted | task_completed.py | clear_owner + loop 追踪 + reminder | L2(write) |

> `run_hook.py` 是 wrapper（JSON 前缀+日志），不直接响应事件。`_shared.py` 是公共工具模块。

## 按数据访问层分组

### L0 — 纯事件数据

只从 event payload 取数，无跨窗口风险。

| Hook | 职责要点 |
|------|---------|
| stop_decision.py | session 级提醒（recording / decisions / dirty） |
| plan_exit_hint.py | Plan 退出强提示 |
| drift_detect_pre.py | 上下文漂移检测 |
| context_monitor.py | 上下文量监控 |
| pre_compact.py | 压缩前 checkpoint |

### L1 — 项目只读

读取项目文件做判断，不修改运行态状态。

| Hook | 读什么 | 判断目的 |
|------|--------|---------|
| task_entry_guard.py | dtask.json + dtask-state.json | 是否有活跃任务可执行编辑 |
| stop_archive.py | dtask.json + recording/ | 是否达归档阈值 |
| task_created_validate.py | dtask.json | 新建任务字段合法性 |

### L2 — 运行态读写

读写 runtime state 文件。

| Hook | 写什么 | 写入时机 |
|------|--------|---------|
| session_start.py | session_id 到 runtime state | Session 启动时 |
| task_completed.py | 清除 owner + loop 计数 | 任务 Done 时 |

## 命名约定

统一采用 `{event}_{action}.py` 模式：

- **event** = Claude Code hook 事件名（SessionStart / Stop / TaskCompleted / PreToolUse / ExitPlanMode / PreCompact）
- **action** = 该 hook 在此事件中的核心动作

例外：
- `_shared.py` — 公共工具模块（下划线前缀标记非 hook）
- `run_hook.py` — 基础设施 wrapper
