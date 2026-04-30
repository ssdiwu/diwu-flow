---
description: 项目状态只读聚合——一键展示任务进度、最近 Session、近期决策、Git 状态
argument-hint: "[--deep（可选）]"
allowed-tools: Read, Bash
effort: low
---

# /dstat — 项目状态快照

> 纯读取聚合命令。执行 `python3 scripts/dstat.py [--deep] --cwd <项目根目录>` 获取结构化 JSON 输出。

## 用法

```bash
/dstat          # 标准模式：任务概览 + 最近 Session + 决策 + Git
/dstat --deep   # 深度模式：追加活跃任务详情 + git diff --stat
```

## 输出

脚本返回 JSON 含 `summary`（各维度计数）+ `formatted_text`（ASCII 表格，完全复刻 SKILL.md §输出规格）。将 `formatted_text` 直接展示给用户。

## AI 判断点

- **阻塞提醒**：Done 任务占比低 + InProgress 长时间未变 → 提醒检查是否阻塞
- **未 commit 提示**：git dirty 且有 Done 任务 → 提醒先提交再继续
- **归档提醒**：recording 文件数接近阈值 → 建议执行 /darc 归档

> **文件操作安全（R1）**：本命令为纯读取，不写入任何文件。
