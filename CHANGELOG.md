# Changelog

All notable changes to diwu-flow will be documented in this file.

## [0.0.1] - 2026-04-28

### 新增（从 diwu-workflow v0.10.x 迁移重构）

- **多平台支持**：Skills 为底 Commands 为壳架构，支持 Claude Code / Codex CLI / OpenCode
- **10 个 Skill**：drun, dtask, dvfy, djug, dcorr, dprd, drec, darc, ddoc, ddemo
- **10 个 Agent**：explorer, implementer, verifier + 7 个领域专家
- **8 个 Command**：/drun, /dtask, /dinit, /dprd, /dadr, /ddoc, /ddemo, /dcorr
- **6 个核心 Hook**：TaskCompleted, TaskCreated, PreToolExecution, Stop, PreCompaction, SessionStart
- **install.sh**：全平台安装脚本（claude-code / codex / opencode / all）
- **drelease.sh**：发布脚本
- **dsess → drun 重命名**：合并 Session 管理与自动执行引擎为统一 Skill

### 变更

- **Rules 精简重构**（13 → 12 文件）：
  - 删除 `correction.md`（内容 100% 被 dcorr Skill 覆盖）
  - 重写 session.md / workflow.md / pitfalls.md / judgments.md / mindset.md（消除内容重叠）
  - 精简 templates.md（迁移 Checkpoint 格式模板）
  - 增强 constraints.md（版本号升级判定表）+ task.md（Commit 语言规范 + 分支命名规范）
  - 所有 rules 文件控制在 200 行以内
- **drun SKILL.md 增强**：执行验证循环改为显式四问框架 + 状态文件映射表
- **Rules 目录提升**：从 `assets/dinit/assets/rules/` 模板提升为顶层 `rules/` 目录
- **plugin.json agents 字段移除**：使用默认路径自动发现，修复安装验证错误
- **Hooks 精简**：22 → 6 个核心 hook（PostToolUse/Stop 系列/Subagent 系列有意精简）

### 移除

- `rules/correction.md`（→ dcorr Skill 完全覆盖）
- 16 个非核心 Hook 脚本（有意精简，不影响核心工作流）

### 修复

- `stop_decision.py` 第 98 行 f-string 语法错误（多余右括号）
- `test_doc_consistency.py` RULES_DIR 路径修正（`.claude/rules` → `rules`）
- `test_doc_consistency.py` hooks.json 数组格式兼容（新旧 CC hooks 格式）
