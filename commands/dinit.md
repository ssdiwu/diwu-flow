---
name: dinit
description: 初始化项目的 Claude Code Agent 工作流结构——编排器模式。创建 CLAUDE.md、rules、agents、skills symlink、dtask.json、recording/、checks/ 等完整工作流骨架。触发场景：(1) 新项目初始化工作流结构，(2) 已有项目刷新/升级 diwu-workflow 配置，(3) 用户说"初始化"、"init"、"初始化工作流"、"dinit"。编排器模式：交互式步骤（信息收集/迁移检测/架构约束/git 初始化/验证清单）在主代理上下文执行，I/O 密集型步骤（代码库扫描/资产同步/文件创建）分发给子代理并行处理。
argument-hint: "[项目描述（可选）] [refresh]"
context: fork
agent: general-purpose
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
effort: high
---

# /dinit — 项目初始化

## 核心原则

- **Source of Truth 是文件系统**：`rules-manifest.json` 决定 rules 列表，agents 由插件默认路径 `agents/` 自动发现（不再通过 /dinit 分发）。不硬编码任何文件名。
- **刷新优先于重建**：已有项目的刷新是增量操作，不破坏用户自定义内容。
- **幂等性**：重复执行 `/dinit` 不应产生副作用（模板资产覆盖，用户跳过的文件不覆盖）。

## Step 0：模式检测

检查 `.claude/CLAUDE.md` 是否已存在：
- **已存在** → **刷新模式**：执行以下 Refresh Protocol
- **不存在** → **初始化模式**：执行 Step 1 → 7 完整流程

---

### Refresh Protocol（刷新模式）

当 `.claude/CLAUDE.md` 已存在时，按以下步骤增量更新：

#### 1. 检测并升级为 v2 格式

搜索 CLAUDE.md 中是否存在 `@rules/` 引用或旧版「工作流规则」章节（含 `@rules/` 列表）。如果存在：

**执行 v2 升级**：将整个 CLAUDE.md 替换为 v2 精简格式，包含：
- 核心原则段（5 条元规则）
- 上位心智层精简版（三唯一框架 + 不确定性门控 + P-J-A 骨架 + 证据摘要）
- Skill/文件索引表（6 个 skill + 4 个参考文件）
- 行为铁律段（recording 更新 + 时间戳 + 禁止推送目录）
- 项目上下文和项目结构（保留用户自定义内容）

> **v2 格式特征**：无任何 `@rules/` 引用、总行数 ≤ 120 行、包含 Skill 索引表。

如已是 v2 格式（无 `@rules/` 且含 Skill 索引），跳过此步。

#### 2. 检测并插入/更新 Skill 索引表

搜索是否存在 `## Skill 索引` 标题。如不存在或格式不完整，插入/更新为标准 v2 索引表。

#### 3. 更新「项目结构」章节

用 Step 1.5 的扫描结果替换 `<!-- SCAN_RESULT_PLACEHOLDER -->` 占位符或更新现有内容。

#### 4. 迁移 recording.md 到 recording/ 目录

检查 `.claude/recording.md` 是否存在。如果存在：
- 读取内容，按 `## Session YYYY-MM-DD HH:MM:SS` 分隔符识别所有 session
- 创建 `.diwu/recording/` 目录（如不存在）
- 将每个 session 写入独立文件 `recording/session-YYYY-MM-DD-HHMMSS.md`
- 迁移完成后将原 `recording.md` 重命名为 `recording.md.backup`

#### 5. 同步 Rules

详见下方 Step 3a（初始化模式和刷新模式共用同一套同步逻辑）。

#### 6. 同步 Agents

详见下方 Step 3b（初始化模式和刷新模式共用同一套同步逻辑）。

#### 7. 同步 Skills

详见下方 Step 3c（初始化模式和刷新模式共用同一套同步逻辑）。

**刷新模式不做的事**：
- 不重新收集项目信息（除非用户主动要求更新）
- 不覆盖用户在 CLAUDE.md 中的自定义章节（只增补标准章节）
- 不修改 `.diwu/dtask.json` 中的任务数据
- 不重新生成 `init.sh` 或 `smoke.sh`
- 不要求用户手动清理旧版本规则文件；刷新时应自动识别并覆盖标准资产

---

## Step 1：收集项目信息

询问用户（上下文已有的跳过）：
- **项目名称**和**1-2 句描述**
- **技术栈**：语言、框架、数据库
- **常用命令**：dev、build、lint、test
- **关键目录**：项目结构概览

**示例（填写完整的项目信息）**：
- 项目名称：diwu-workflow
- 描述：Claude Code 插件仓库，提供 diwu 编码工作流套件
- 技术栈：Node.js，无框架，无数据库
- 常用命令：`npm run lint`（lint），`npm test`（test），无 dev server
- 关键目录：`commands/`（用户命令），`assets/`（模板文件），`skills/`（技能文件）

收集到的信息要达到这个粒度才能生成有效的 CLAUDE.md 和 smoke.sh。

## Step 1.5：代码库扫描（子代理并行）

> **仅初始化模式执行此步骤**。刷新模式跳过，直接用已有 CLAUDE.md 中的项目结构信息。

**前置准备**：
1. 创建临时工作目录：`mkdir -p .diwu/.dinit/`
2. 将 Step 1 收集的用户信息序列化为 `.diwu/.dinit/project-info.json`：
   ```json
   {
     "name": "用户提供的项目名称",
     "description": "用户提供的描述",
     "tech_stack_user": "用户提供的技术栈",
     "commands": {"dev": "...", "build": "...", "test": "..."},
     "key_dirs": ["用户提供的关键目录"]
   }
   ```

**启动 3 个并行子代理**（受 `subagent_concurrency` 限制，默认 3；如不足则分批）：

### 子代理 A — 目录结构扫描（Explore 类型）

- **任务**：扫描项目根目录下 1-2 层目录结构，识别主要模块和用途
- **操作**：`ls -la` + Glob `*/` + 分析目录命名约定
- **输出**：写入 `.diwu/.dinit/scan-dirs.json`
  ```json
  {"directories": [{"name": "src/", "purpose": "源码", "file_count_estimate": N}, ...]}
  ```

### 子代理 B — 技术栈检测（Explore 类型）

- **任务**：读取包管理器配置文件，提取语言、框架、构建工具、测试框架
- **操作**：Glob `package.json|requirements.txt|go.mod|Cargo.toml|pom.xml|build.gradle` → Read 提取字段
- **输出**：写入 `.diwu/.dinit/scan-tech.json`
  ```json
  {"language": "...", "framework": "...", "build_tool": "...", "test_framework": "...", "package_manager": "..."}
  ```

### 子代理 C — 关键文件识别（Explore 类型）

- **任务**：定位 README、.gitignore、CI/CD 配置、入口文件、测试目录
- **操作**：Glob 常见模式 → Read 确认内容
- **输出**：写入 `.diwu/.dinit/scan-files.json`
  ```json
  {"readme": "path", "gitignore": "path", "ci_config": "path", "entry_files": [...], "test_dir": "path"}
  ```

**等待全部完成后**：
4. 合并 3 个 JSON 为 `.diwu/.dinit/scan-result.json`：
   ```json
   {
     "directories": [...],
     "tech_stack": {...},
     "key_files": {...},
     "commands": {"dev": "...", "build": "...", "test": "..."}
   }
   ```
5. 用 `scan-result.json` 补充/覆盖 `project-info.json` 中用户未提供的信息（优先用户显式提供值）
6. 输出扫描摘要到终端（目录数、技术栈、关键文件列表）

## Step 2：旧版迁移检测（复制资产之前执行）

检测项目是否使用旧版 diwu-workflow（v0.x）或旧运行时目录结构：

1. **检测旧版标志**：
   - 检查 `.claude/rules/states.md` 是否存在
   - 检查 `.claude/rules/task.md` 是否**不存在**
   - 两个条件同时满足 → 检测到旧版

2. **检测旧运行时目录迁移需求**：
   - 检查 `.diwu/dtask.json`、`.claude/recording/`、`.claude/decisions.md`、`.claude/dsettings.json`、`.claude/project-pitfalls.md`、`.claude/archive/`、`.claude/continue-here.md`、`.claude/checks/` 是否存在任一旧运行时文件
   - 检查 `.diwu/` 是否**不存在**
   - 两个条件同时满足 → 输出迁移指引或执行自动迁移：将上述旧运行时文件迁移到 `.diwu/`，保留 `.claude/CLAUDE.md`、`rules/`、`agents/`、`skills/` 等 Claude 原生机制目录不动

3. **如检测到旧版，执行迁移**：
   a. **更新 CLAUDE.md 引用**：搜索所有 `@rules/states.md` → 替换为 `@rules/task.md`
   b. **合并 dsettings 新字段**：读取 `dsettings.json.template`，合并到用户项目的 `.diwu/dsettings.json`（不覆盖已有值，只追加缺失字段）
   c. **备份旧 states.md**：重命名为 `states.md.backup`
   d. 输出迁移报告（引用更新数、合并字段数、备份状态）

4. **如未检测到旧版和旧运行时结构**：跳过此步骤，直接进入 Step 3

## Step 3：同步可分发资产（子代理并行）

> **初始化模式和刷新模式共用此步骤**。

**前置准备**：
1. 确定插件根目录 `PLUGIN_ROOT` = `${CLAUDE_PLUGIN_ROOT}` 或通过 `which` 定位
2. 确保 `.diwu/.dinit/` 目录存在（Step 1.5 已创建；刷新模式需手动创建）

按以下类别从模板目录同步到项目目录：

| 资产类型 | 源目录 | 目标目录 | 清单来源 | 冲突策略 |
|---------|--------|---------|---------|---------|
| rules | `${PLUGIN_ROOT}/assets/dinit/assets/rules/` | `.claude/rules/` | `rules-manifest.json` 的 `rules` 数组 | 按需写入/覆盖 |
| skills | `${PLUGIN_ROOT}/skills/` | `.agents/skills/` | 动态扫描 `*/SKILL.md` | 按需写入/覆盖 |

**并行启动 2 个子代理**（受 `subagent_concurrency` 限制）：

### 子代理 D — Rules 同步（general-purpose 类型）

- **输入**：`PLUGIN_ROOT` 路径（从环境变量或上下文获取）
- **任务**：
  1. 清理孤立文件：删除 `.claude/rules/` 下不在 `rules-manifest.json` `rules` 数组中的文件（如旧的 `states.md`）
  2. 读取 `${PLUGIN_ROOT}/assets/dinit/assets/rules-manifest.json`
  3. 按 `rules` 数组逐一比较源文件与目标文件内容：
     - 目标不存在 → 写入，标记 `NEW`
     - 目标存在且内容一致 → 跳过，标记 `SAME`
     - 目标存在且内容不同 → 用源文件覆盖，标记 `UPDATED`
- **输出**：写入 `.diwu/.dinit/sync-rules-report.json`
  ```json
  {"files": [{"name": "task.md", "status": "NEW|SAME|UPDATED"}], "summary": {"total": N, "new": N, "same": N, "updated": N}}
  ```

### 子代理 E — Skills Symlink（general-purpose 类型）

- **输入**：`PLUGIN_ROOT` 路径
- **任务**：
  1. 创建 `.agents/skills/` **普通目录**（如不存在）
  2. 扫描 `${PLUGIN_ROOT}/skills/` 下所有含 `SKILL.md` 的子目录
  3. 为每个 skill 创建**独立目录级 symlink**：`ln -s ../../skills/{name} .agents/skills/{name}`
     - 目标已存在且指向正确 → 跳过（幂等）
     - 不是 symlink 或目标错误 → 删除后重新创建
  4. 冲突策略：用户自定义 skill 目录（非 symlink）不被覆盖
- **输出**：写入 `.diwu/.dinit/sync-skills-report.json`
  ```json
  {"symlinks": [{"name": "dtask", "target": "../../skills/dtask", "status": "CREATED|SKIPPED|FIXED"}], "summary": {...}}
  ```

**等待全部完成后**：
- 汇总两个 report 输出到终端（表格形式：资产类型 | 文件数 | NEW | SAME | UPDATED）

> **设计说明**：Rules 用 manifest 而非动态扫描——有严格排序语义和版本字段；Skills 用目录级 symlink——用户可自由添加自定义 skill 不污染插件目录。Agents 由插件 `plugin.json` 声明自动发现，无需 /dinit 分发。

## Step 4：创建项目配置文件（子代理）

> **前置条件**：Step 3 三个同步子代理均已完成（可读取 `.diwu/.dinit/sync-*-report.json` 确认）。
> **仅初始化模式执行完整流程**；刷新模式跳过已存在且无需更新的文件。

**启动 1 个子代理**：

### 子代理 G — 模板填充与文件创建（general-purpose 类型）

- **输入文件**：
  - `.diwu/.dinit/project-info.json` — 用户提供的项目信息
  - `.diwu/.dinit/scan-result.json` — 代码库扫描结果
  - `PLUGIN_ROOT` 路径 — 模板来源目录

- **任务列表**（按序执行）：

  **4.1 .claude/CLAUDE.md**
  - 读取 `${PLUGIN_ROOT}/assets/dinit/assets/claude-md-portable.template`
  - 填充占位符：
    - 项目名称 / 描述 → 来自 `project-info.json`
    - 技术栈 → 合并 `project-info.tech_stack_user` 和 `scan-result.tech_stack`
    - 常用命令 → 来自 `project-info.commands` 或 `scan-result.commands`
    - 关键目录 → 来自 `project-info.key_dirs` 或 `scan-result.directories`
    - `<!-- SCAN_RESULT_PLACEHOLDER -->` → 替换为 `scan-result` 的结构化描述
    - `<!-- RULES_PLACEHOLDER -->` ~ `<!-- END_RULES_PLACEHOLDER -->` → 根据 `rules-manifest.json` 动态生成规则索引
  - 写入 `.claude/CLAUDE.md`
  - **约束**：不得创建 `.claude/assets/rules/` 或其他子目录；总行数 ≤ 120 行

  **4.2 .diwu/dtask.json**
  - 读取 `${PLUGIN_ROOT}/assets/dinit/assets/task.json.template`
  - 若用户在 Step 1 提供了初始需求 → 填充任务（status: InDraft）；否则 tasks 数组为空
  - 写入 `.diwu/dtask.json`

  **4.3 init.sh（项目根目录）**
  - 读取 `${PLUGIN_ROOT}/assets/dinit/assets/init.sh.template`
  - 根据技术栈定制安装命令和 dev server 命令
  - 执行 `chmod +x init.sh`

  **4.4 .diwu/recording/**
  - 创建目录：`mkdir -p .diwu/recording/`

  **4.5 .diwu/archive/**
  - 创建目录：`mkdir -p .diwu/archive/`

  **4.6 .diwu/continue-here.md**
  - 创建空文件（会话续接文件，默认不预填内容）

  **4.7 .diwu/dsettings.json**
  - 读取 `${PLUGIN_ROOT}/assets/dinit/assets/dsettings.json.template`
  - 若已存在 → 跳过（不覆盖用户配置）；若不存在 → 写入

  **4.8 .diwu/project-pitfalls.md**
  - 读取 `${PLUGIN_ROOT}/assets/dinit/assets/project-pitfalls.md.template`
  - 若已存在 → 跳过（不覆盖用户内容）；若不存在 → 写入

  **4.9 .diwu/checks/smoke.sh**
  - 读取 `${PLUGIN_ROOT}/assets/dinit/assets/smoke.sh.template`
  - 根据技术栈定制
  - 执行 `chmod +x .diwu/checks/smoke.sh`

  **4.10 .diwu/decisions.md（可选）**
  - 仅当 `project-info.json` 中包含 `"decisions": true` 或用户在 Step 1 明确要求时
  - 读取 `${PLUGIN_ROOT}/assets/dinit/assets/decisions.md.template` → 写入

- **输出**：写入 `.diwu/.dinit/create-files-report.json`
  ```json
  {
    "files": [
      {"path": ".claude/CLAUDE.md", "status": "CREATED|SKIPPED|UPDATED|ERROR"},
      ...
    ],
    "summary": {"total": N, "created": N, "skipped": N, "error": N}
  }
  ```

**等待子代理完成后**：
- 读取 `create-files-report.json` 输出摘要到终端
- 如有 ERROR 状态文件，记录到验证清单待 Step 7 检查

## Step 5：可选 — 架构约束

询问用户是否需要 `.claude/rules/constraints.md`（架构复杂的项目推荐）。
如需要，读取 `${PLUGIN}/assets/dinit/references/constraint-template.md`，引导用户用五维框架定义约束。

## Step 6：Git 初始化（如需要）

若当前目录不是 git 仓库，初始化 git 仓库并创建初始提交。

## Step 7：验证清单

确认以下文件均已创建（数量来自运行时扫描，非硬编码）：

**基础文件（v2 格式验证）**：
- [ ] `.claude/CLAUDE.md` 已填充项目信息，包含核心原则 + Skill 索引表
- [ ] `.claude/CLAUDE.md` **不包含任何 `@rules/` 引用**（grep 零匹配）
- [ ] `.claude/CLAUDE.md` 总行数 ≤ 120 行
- [ ] `.claude/CLAUDE.md` 包含 `## Skill 索引` 或等效 skill 列表
- [ ] `.claude/CLAUDE.md` 的「项目结构」章节包含扫描结果（非默认占位符）
- [ ] `.diwu/dtask.json` 是有效 JSON
- [ ] `init.sh` 可执行
- [ ] `.diwu/recording/` 目录存在
- [ ] `.claude/recording.md` 不存在（已迁移为 recording/ 目录）或已重命名为 `.recording.md.backup`

**Rules（N = rules-manifest.json.rules.length）**：
- [ ] `.claude/rules/` 下有 N 个 rules 文件
- [ ] `.claude/rules/` 下不存在 `states.md`（已替换为新版规则集）
- [ ] `.claude/rules/states.md.backup` 仅在检测到旧版时存在
- [ ] 刷新时能识别并覆盖内容变化的标准 rules 文件（例如 `templates.md`）

**Skills（K = skills/ 下含 SKILL.md 的子目录数）**：
- [ ] `.agents/skills/` 目录存在且包含 K 个目录级 symlink（名称 `{name}`）
- [ ] 每个 symlink 目标为 `../../skills/{name}` 且目标内含 `SKILL.md`
- [ ] 刷新时能识别并更新指向错误的 symlink

**可选文件**：
- [ ] `.diwu/dsettings.json` 存在且 JSON 合法
- [ ] `.diwu/project-pitfalls.md` 存在
- [ ] `.diwu/checks/smoke.sh` 可执行
- [ ] `.diwu/archive/` 目录存在（归档产物存放位置）
- [ ] `.diwu/archive/` 目录存在
- [ ] （可选）`.diwu/continue-here.md`
- [ ] （可选）`.diwu/decisions.md`
