---
name: dinit
description: 初始化项目的 Claude Code Agent 工作流结构——编排器模式
argument-hint: "[项目描述（可选）] [refresh]"
context: fork
agent: general-purpose
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
effort: high
---

# /dinit — 项目初始化

> 脚本：`python3 scripts/dinit.py <子命令> --cwd <项目根目录>`

## 核心原则

- **Source of Truth 是文件系统**：`rules-manifest.json` 决定 rules 列表，agents 由默认路径自动发现
- **刷新优先于重建**：增量更新不破坏用户自定义内容
- **幂等性**：重复执行不产生副作用

## 子命令

| 命令 | 说明 |
|------|------|
| `scan-repo` | 扫描目录结构/技术栈/关键文件 → 输出 JSON |
| `sync-rules` | 按 manifest 同步 rules 到 `.claude/rules/` |
| `sync-skills` | 创建 `.agents/skills/` 下 symlink 指向 skills/ |
| `create-config [--project-info-file X] [--scan-result-file Y]` | 创建 CLAUDE.md/dtask.json/runtime dirs |
| `migrate-legacy` | 检测旧版 v0.x 并迁移运行时文件 |
| `validate` | 运行验证清单 → PASS/FAIL 报告 |

## AI 保留步骤（脚本不覆盖）

### Step 0：模式检测

检查 `.claude/CLAUDE.md` 是否已存在：
- **已存在** → 刷新模式：依次执行 `sync-rules` → `sync-skills` → `validate`
- **不存在** → 初始化模式：执行 Step 1 → 7

### Step 1：信息收集

询问用户项目名称、描述、技术栈、常用命令、关键目录。

> **文件操作安全（R1）**：修改已有文件前先 Read 当前内容；整文件重写先 Read 完整文件；新建确认不存在后再 Write。
> **JSON 格式（R2）**：写入 .json 必须 indent=2, ensure_ascii=False

### Step 1.5：代码库扫描

执行 `scan-repo`，结果存入 `.diwu/.dinit/scan-result.json`，供 create-config 使用。

### Step 2：旧版迁移检测

执行 `migrate-legacy`，自动检测 states.md 旧标志和旧运行时文件位置。

### Step 3：资产同步（子代理并行）

- Rules 同步：执行 `sync-rules`
- Skills Symlink：执行 `sync-skills`

### Step 4：配置文件创建

执行 `create-config --project-info-file <info> --scan-result-file <scan>`。

### Step 5-7：架构约束 / Git / 验证

- Step 5：询问是否需要 constraints.md（可选）
- Step 6：非 git 目录则初始化仓库
- Step 7：执行 `validate` 验证全部产出

## 刷新模式快捷流程

```
/dinit refresh
→ migrate-legacy → sync-rules → sync-skills → validate
```
