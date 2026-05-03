---
description: Session 记录写入与归档——文件格式、踩坑记录、原子 commit、归档聚合
argument-hint: "[session内容摘要]"
allowed-tools: Read, Write, Edit, Bash
effort: normal
---

# /drec — 记录与归档

> Session 结束后的必做步骤：写入 recording + 原子 commit + 可选归档。

## 执行步骤

1. 按 `skills/drec/SKILL.md` §Session 文件格式模板 写入 `.diwu/recording/session-{timestamp}.md`
2. 踩坑经验按四段式格式记录（`skills/drec/SKILL.md` §本次踩坑/经验）
3. 运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳（禁止手写）
4. 执行 `git add -A && git commit -m "[recording] Session {timestamp} — ..."`（详见 SKILL.md §原子 Commit 职责）
5. 如需归档，按 `skills/drec/SKILL.md` §归档聚合指引 执行

## 完整规范

格式模板、时间戳规则、Amend 模式、标记清除语义等详见 **`skills/drec/SKILL.md`**。
