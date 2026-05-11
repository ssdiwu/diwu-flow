---
name: dinit
description: 初始化项目的 Claude Code Agent 工作流结构
argument-hint: "[项目描述（可选）]"
context: fork
agent: general-purpose
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
effort: high
---

# /dinit

用户输入 `/dinit` 即可。AI 调用 **skills/dinit** 获取执行指引。

脚本入口: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dinit.py run --cwd <项目根目录>`

## 行为契约

- AI 自动检测模式（刷新/新建），不询问用户选择
- 全自动迁移旧版格式，不报告细节除非出错
- 幂等安全，重复执行无副作用
- 首次初始化时需收集项目信息（名称/描述/技术栈）
