---
description: "停止 dloop 连续循环"
argument-hint: ""
allowed-tools: Read, Bash
effort: low
---

# /dstop — 停止 dloop

> 执行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dloop.py stop --cwd <项目根目录>` 停止当前活跃的 dloop 循环。
> 停止逻辑内置在 dloop.py 中（三件套：start/status/stop）。

## 使用时机

- 手动想停止连续任务循环时
- dloop 自然结束后无需调用（stop_decision hook 已自动清理）

## 执行步骤

1. 运行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dloop.py stop --cwd <项目根目录>`
2. 确认输出含 "已取消" 或 "无活跃"

> **注意**：stop 不负责 stale 检测（那是 status/start 的职责）。
> 完整的自动停止由 Stop hook 的 stop_decision.py 负责（continuous_mode 下每轮 drun 后检查）。
