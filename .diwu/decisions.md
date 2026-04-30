# 设计决策记录

> 每条决策记录一次影响范围 ≥2 模块或多方案选一的设计决定。
> 格式：时间戳 + 决策标题 + 备选方案 + 选定方案 + 影响范围 + 理由。
> 详见 rules/judgments.md §何时写 decisions.md / skills/drec/SKILL.md §设计决策记录

---

### 2026-04-30 22:38:08 统一 runtime state 真相源：引入 dtask-state.json

- **备选方案**:
  - A) 维持分散状态：`dtask.json` 存 status，`dloop-state.json` 存 loop 元数据，owner 信息隐含在 InProgress 唯一性假设中
  - B) 统一 runtime state：新增 `dtask-state.json` 作为 owner/dloop 元数据唯一真相源，`dtask.json` 专注任务定义与 status
- **选定方案**: B
- **影响范围**: Task#26-31 全线（scripts/dtask_state.py / dtask_transition.py / dloop.py / dloop_state.py / stop_decision.py / context_monitor.py / pre_compact.py / task_completed.py / session_start.py / commands / skills / rules 三副本 / assets 模板）
- **理由**:
  - 分散状态下 `dloop-state.json` 与 task owner 无关联，普通 InProgress 断点恢复只能盲取 `ip[0]`，多 session 并发时可能误恢复 чужой 任务
  - 统一后 `dtask-state.json.task_sessions` 提供 session-scoped owner 语义，stop_decision / context_monitor / checkpoint 写入均有明确的 owner 匹配校验
  - `dtask_transition.py` 作为唯一允许同时修改 `dtask.json.status` 与 `dtask-state.json` 的入口，避免半完成状态
  - legacy `dloop-state.json` 迁移路径保留向后兼容
