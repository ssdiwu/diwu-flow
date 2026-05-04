---
description: Session 记录写入与归档——文件格式、踩坑经验、原子 commit、归档聚合
argument-hint: "[session内容摘要]"
allowed-tools: Read, Write, Edit, Bash
effort: normal
---

# /drec — 记录与归档

> Session 结束后的必做步骤：写入 recording → 归档 → 原子 commit。

## 执行步骤

1. 按 `skills/drec/SKILL.md` §Session 文件格式模板 写入 `.diwu/recording/session-{timestamp}.md`
2. 踩坑经验按四段式格式记录（`skills/drec/SKILL.md` §本次踩坑/经验）
3. 运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳（禁止手写）
4. 执行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/drec_archive.py run --cwd <项目根目录>` → 输出归档摘要；无归档需求则输出"无待归档内容"
5. 执行 `git add -A && git commit -m "[recording] Session {timestamp} — ..."`（详见 SKILL.md §原子 Commit 职责）

## 完整规范

格式模板、时间戳规则、归档聚合等详见 **`skills/drec/SKILL.md`**。
