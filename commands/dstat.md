---
description: 项目状态只读聚合——一键展示任务进度、最近 Session、近期决策、Git 状态
argument-hint: "[--deep（可选）]"
allowed-tools: Read, Bash, Glob
effort: low
---

# /dstat — 项目状态快照

> 项目状态只读聚合。触发 `skills/dstat/SKILL.md`。

## 用法

```bash
/dstat          # 标准模式：任务概览 + 最近 Session + 决策 + Git
/dstat --deep   # 深度模式：追加活跃任务详情 + git diff
```

## 输出

按 `skills/dstat/SKILL.md` §输出规格 格式化输出。
