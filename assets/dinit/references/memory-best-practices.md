# CLAUDE.md 最佳实践

摘录自 Claude Code 官方文档。

## 编写指南

- **具体明确**: "使用 2 空格缩进" 优于 "正确格式化代码"
- **使用结构**: 在描述性 markdown 标题下组织相关指令
- **包含常用命令**: 构建、测试、lint 命令避免重复搜索
- **记录代码风格**: 命名约定、import 顺序、错误处理模式
- **添加架构模式**: 项目特定的重要模式

## @import 语法

引用其他文件而不复制内容:
```markdown
项目概览参见 @README,可用命令参见 @package.json。
架构指南 @docs/architecture.md
```

- 支持相对和绝对路径
- 代码块内的 import 不会被求值
- 最大递归深度: 5 跳

## 模块化规则 (.claude/rules/)

对于大型项目,将指令组织到多个文件:

```
.claude/rules/
├── code-style.md       # Code style guidelines
├── testing.md          # Testing conventions
└── constraints.md      # Architecture constraints
```

### 路径作用域规则

规则可以使用 YAML frontmatter 指定目标文件:

```markdown
---
paths: src/api/**/*.ts
---
# 仅应用于 API 文件的 API 规则
```

## 层级关系

优先级顺序(从高到低):
1. 企业策略 (`/Library/Application Support/ClaudeCode/CLAUDE.md`)
2. 用户记忆 (`~/.claude/CLAUDE.md` + `~/.claude/rules/`)
3. 项目记忆 (`./CLAUDE.md` + `./.claude/rules/`)
4. 本地覆盖 (`./CLAUDE.local.md`)

## 核心原则

> CLAUDE.md 不仅仅是给人看的文档——它是 AI 伙伴的系统指令。约束越精确,AI 的错误率越低。
