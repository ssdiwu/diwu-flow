---
description: "结束活跃的 dloop 循环"
---

# /dend — 结束连续任务循环

结束当前活跃的 dloop 循环，清理状态文件。

## 执行流程

1. **检查状态文件**：`.diwu/dloop-state.json` 是否存在
   - **不存在** → 输出：`✅ 无活跃的 dloop 循环。`
   - **存在** → 继续

2. **读取状态**：
   - 读取 `current_iteration` 和 `completed_task_ids`
   - 输出取消摘要：
     ```
     🛑 dloop 已取消
     已完成: <completed_task_ids.length> 个任务 (iteration <N>)
     已完成任务: #<id1>, #<id2>, ...
     ```

3. **删除状态文件**：
   - `rm .diwu/dloop-state.json`

4. **后续行为**：
   - 下次 Stop 事件时，stop_decision.py 检测不到状态文件 → 默认模式 → allow stop
   - Agent 在完成当前任务后正常停止
