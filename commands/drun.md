---
description: 启动单任务执行器
argument-hint: "[task-id 可选]"
allowed-tools: Read, Bash
effort: low
---

# /drun — 单任务执行

调用 `drun` Skill 执行单任务主循环：Preflight → 上下文恢复 → 任务选择 → 实施 → 验证 → 记录。

> 完整方法论见 `skills/drun/SKILL.md`。

## 快速开始

- 输入 `/drun`：恢复当前 session 可继续的唯一任务。
- 若存在 `InProgress` 任务：`/drun` 只恢复 **当前 session 在 `.diwu/dtask-state.json.task_sessions` 中持有的 owner**。
- 若当前无 `InProgress`：`/drun` 选择第一个可执行的 `InSpec` 任务，并先通过 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py claim --task-id N --cwd <proj>` 把它显式切到 `InProgress`，再开始实施（`--session-id` 默认 `auto`，自动解析真实 session ID）。
- 当本轮实施与验证结束：必须通过 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py release --task-id N --to done|inreview --cwd <proj>` 显式收尾，不能手改 `status`（`--session-id` 同样默认 `auto`）。`release` 会自动在 `dtask-state.json` 写入 `pending_recording` 标记；若忘记后续调 `/drec`，Stop Hook 会检测到此标记并强制拦截，要求先执行 `/drec` 清除标记后才允许继续。

## 运行时真相源

- `dtask.json`：任务内容与 `status` 的真相源。
- `dtask-state.json`：运行态 owner 与 dloop 元数据真相源。
- `dtask_transition.py`：唯一允许同时修改 `dtask.json.status` 与 `dtask-state.json` 的入口。

> 没有完成 `claim` 进入 `InProgress` 的任务，不允许直接开始实施。

> 完成后的最终状态也必须通过 `release` 脚本回写：自审通过切 `Done`，证据不足或需人工确认则切 `InReview`。

## 与 /dloop 的关系

- `/drun`：单任务执行，做完即停。
- `/dloop`：多任务连续执行，loop 元数据写在 `.diwu/dtask-state.json.dloop`。

## 常见结果

- `继续当前任务`：当前 session 命中 owner 匹配的 `InProgress`。
- `选择下一个 InSpec`：通过 `dtask_transition.py claim` 接管新任务后开始。
- `完成并收尾`：通过 `dtask_transition.py release` 将当前 `InProgress` 显式切到 `Done` 或 `InReview`。
- `PENDING REVIEW`：超前实施达到上限，停止并等待人工验收。
- `invalid runtime state`：`dtask-state.json` 缺失 owner、损坏或与 `dtask.json` 冲突；此时不会自动恢复 чужой 任务。

## 细粒度子代理委托

> 完整决策矩阵和流水线协议见 `skills/drun/SKILL.md` §细粒度子代理委托。

**核心原则**：按每个步骤独立判断是否拆分，默认 S1（直做），仅命中 B/C 维度时升级。

| 策略 | 触发条件简述 | Agent 组合 |
|------|------------|-----------|
| S1 直做 | <200 行 + 高把握 + 自审够 | 主代理直接执行 |
| S2 探索+实施 | 不确定代码结构/首次接触 | explorer → implementer |
| S3 实施+验证 | API 变更 / >2000行 / 需独立验收 | implementer → verifier |
| S4 完整流水线 | 重量级 + 高不确定 + 强验证需求 | explorer → implementer → verifier |

**退化安全**：任何 agent 失败退化回主代理闭环，不阻塞任务推进。
