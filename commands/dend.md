---
description: 取消 dloop 连续循环
argument-hint: 无参数
allowed-tools: Read, Bash
effort: low
---

# /dend — 取消循环

> 执行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dend.py --cwd <项目根目录>` 取消当前活跃的 dloop 循环。

## 输出

脚本返回 JSON：`{ok, status, message, formatted_text}`。将 `formatted_text` 直接展示给用户。无活跃循环时输出 `status:'no_loop'`。
