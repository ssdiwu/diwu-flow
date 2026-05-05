---
description: Session 记录写入操作手册——原子 commit、Amend 模式、归档聚合
argument-hint: "[session内容摘要]"
allowed-tools: Read, Write, Edit, Bash
effort: normal
---

# /drec — 记录与归档

> Session 结束后的必做步骤：写入 recording → 归档 → 原子 commit。

## 执行步骤

1. 按 `rules/templates.md` §Session 文件格式 写入 `.diwu/recording/session-{timestamp}.md`
2. 踩坑经验按 `rules/session.md` §本次踩坑/经验 四段式格式记录
3. 运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳（禁止手写，见 `rules/session.md` §时间戳）
4. 执行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/drec_archive.py run --cwd <项目根目录>` → 输出归档摘要；无归档需求则输出"无待归档内容"
5. 执行 `git add -A && git commit -m "[recording] Session {timestamp} — ..."`（详见 SKILL.md §原子 Commit 职责）

## 完整规范

原子 commit、Amend 模式、标记清除语义、归档策略等详见 **`skills/drec/SKILL.md`**。格式规则（时间戳、模板、踩坑）见 **`rules/session.md`** 和 **`rules/templates.md`**。
