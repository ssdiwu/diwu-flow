# diwu-flow

## 核心原则

- Skills 为底，Commands 为壳：所有方法论在 Skills 中，Commands 是薄封装
- 零平台耦合：Skill frontmatter 无平台专属字段（无 context/agent/model/allowed-tools/hooks）
- 扁平结构：agents/ 和 skills/ 均为单层目录，最大化平台兼容性

## 项目结构

| 目录 | 说明 |
|------|------|
| `skills/` | 10 个 Skill（唯一真相源） |
| `agents/` | 10 个 Agent（扁平结构） |
| `commands/` | 8 个 Command（薄壳封装） |
| `hooks/` | CC 专属 Hook 脚本（6 个核心） |
| `.claude-plugin/` | CC 插件声明（plugin.json） |
| `assets/dinit/assets/` | /dinit 模板资源 |
| `rules/` | 规则参考文件 |

## Skill v1.0 Frontmatter 规范

```yaml
---
name: {skill_name}
version: "1.0"
type: rule                             # rule | product
description: "..."
triggers:
  - "触发场景1"
keywords:
  - keyword
depends:
  - {依赖 skill}
effort: low|normal|high
argument-hint: "[参数提示]"
---
```

禁止在 Skill frontmatter 中添加：context、agent、model、allowed-tools、hooks。

## Command 薄壳规范

Command = Skill 触发器 + 交互封装。不含独立方法论。
- 6 个薄壳命令：引用对应 Skill，含快速开始指引
- 2 个 CC 专属厚命令：dinit（初始化编排器）、dadr（ADR 向导）

## 行为铁律

- 修改 Skill 后必须验证 frontmatter YAML 合法性
- plugin.json 不声明 agents 字段（使用默认路径自动发现）
- CC 专属内容仅限 hooks/、.claude-plugin/、assets/
