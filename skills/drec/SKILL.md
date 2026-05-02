---
name: drec
version: "1.0"
type: rule
description: "Session 记录写入方法论——文件格式模板、踩坑经验四段式记录、时间戳获取规则、最低合法答案、归档聚合指引、Stop hook 检测正则"
triggers:
  - "写 session 记录"
  - "记录踩坑经验"
  - "Session 结束前整理"
  - "用户说 记录、recording、踩坑"
keywords:
  - "session记录"
  - "踩坑"
  - "时间戳"
  - "归档聚合"
  - "四段式"
  - "checkpoint"
effort: normal
argument-hint: "[session内容]"
---

# drec

Session 记录写入规范：每次 session 结束前的必做事项。

### 文件操作安全（R1）

**（R1）**：追加 session 记录到 `.diwu/recording/` 前 **必须先 Read 当前 session 文件尾部**（如存在），确保追加位置正确不覆盖已有内容。

---

## 时间戳规则（铁律）

写入 Session 标题前**必须先运行命令获取真实时间戳**：

```bash
date '+%Y-%m-%d %H:%M:%S'
```

- 禁止手写日期或写"（续）"等占位符
- 正确：先运行 date → 得到 `2026-04-18 16:49:42` → 写 `## Session 2026-04-18 16:49:42`
- 错误：`## Session 2026-02-26 （续）`

---

## Session 文件格式模板

```markdown
## Session YYYY-MM-DD HH:MM:SS
### Task#N: [标题] → [状态]
**实施内容**: - [工作项]
**验收验证**: - [x] [acceptance] ([方法])
**提交**: commit [hash]
### 下一步: [计划]
### 本次踩坑/经验
- [类别] 现象 → 根因 → 误判 → 正确做法
### 错误追踪表（可选）
| 时间戳 | 工具 | 错误摘要 | 尝试 | 解决方式 | 类别 |
```

**禁止 YAML front matter**：Session 文件禁止以 `---` 开头。`---` 在 Markdown 中是 front matter 语法，渲染器会将包裹内容当作元数据隐藏。

- 正例：文件第一行就是 `## Session 2026-04-14 18:44:09`
- 反例：开头写 `---` 再跟 `## Session ...`

---

## 本次踩坑/经验（必填）

**约束级别**：必填，不可省略。每个 session 必须显式写入此字段。

### 四段式格式模板

```markdown
### 本次踩坑/经验

- [类别] 现象描述 → 根因分析 → 错误判断 → 正确做法
```

**类别标签**（六类泛化模式对齐）：
`环境漂移` / `数据缺口` / `读层现象` / `路由护栏契约` / `验证误读` / `分层未拆清` / `其他`

#### 示例

```markdown
### 本次踩坑/经验

- [环境漂移] 本地测试通过但 CI 超时 → CI 环境缺少代理配置导致网络超时 → 误判为代码性能问题 → 应先检查 CI 环境变量和网络配置再定位代码
- [验证误读] 单元测试全部 PASS 但功能不工作 → 测试 mock 了关键依赖导致假阳性 → 误判为已完成 → 应补充集成测试或端到端验证
```

#### 最低合法答案（无显著误判时使用）

```markdown
### 本次踩坑/经验

本轮无显著误判，实施路径符合预期。
```

> 注意：最低合法答案仅用于确实无踩坑的 session。任何判断偏差、意外阻塞、返工或环境问题都必须按四段式记录。

### Stop hook 检测正则

Stop hook 用以下正则检测必填字段是否存在：

```python
# 匹配本次踩坑/经验字段是否存在
PITFALL_PATTERN = re.compile(
    r'^###\s*本次踩坑[\/]?经验\s*\n'
    r'(.*\n)*'
    r'.+',   # 至少有一行内容
    re.MULTILINE
)

# 最低合法答案专用匹配
PITFALL_MINIMAL_PATTERN = re.compile(
    r'###\s*本次踩坑[\/]?.*经验.*无显著误判.*符合预期',
    re.DOTALL
)
```

**匹配语义**：
- 正常踩坑记录：标题存在 + 后续有四段式内容 → **PASS**
- 最低合法答案：包含"无显著误判"且包含"符合预期" → **PASS**
- 缺失：文件中不存在标题 → **FAIL**（触发 Stop hook 告警）

---

## 归档聚合指引

归档时（recording/ 文件数超阈值），扫描所有即将归档的 session 文件中的 `### 本次踩坑/经验` 段落，按类别聚类后追加到 project-pitfalls.md。**每条必须标注具体 session 文件名作为来源**（如 `session-2026-04-18-213522.md`），禁止写归档文件名或占位符；归档文件内按 `## Source:` 分隔符追踪所属 session。

---

## 工具失败处理协议（3-Strike）

当同一工具连续失败时，Hook 自动追踪并注入分级提示：

| 尝试 | 策略 | 注入内容 |
|------|------|---------|
| 1/3 | 诊断并修复根因 | 温和提醒：诊断根因，如有踩坑考虑记录 |
| 2/3 | 更换根本不同的方法 | 强烈建议：换工具/换文件/换策略 |
| 3+/3 | 广泛重新思考或升级用户 | 阻止继续：质疑假设，考虑升级 |

**状态持久化**：`/tmp/diwu_ctx_<pid>_errtrack` JSON 文件，冷却窗口默认 60 秒。

---

## 结构化错误追踪表（可选）

复杂 session（多次工具失败、多轮纠偏）中，建议在踩坑记录后追加表格：

```markdown
### 错误追踪表（可选）

| 时间戳 | 工具 | 错误摘要 | 尝试 | 解决方式 | 类别 |
|--------|------|---------|------|---------|------|
| 01:30:05 | Bash | npm install E403 | 2 | 使用镜像源 | 环境漂移 |
```

---

## Checkpoint 记录机制

大任务实施过程中记录中间进度：

```
### Checkpoint @ 步骤3/8
进度: 完成 auth 模块重构，payment 模块进行中
已修改: src/auth.ts(+120/-80), src/models/user.ts(+15/-5)
下一步: 步骤4 payment 模块重构 → 步骤5 集成测试
回滚方式: git checkout -- src/auth.ts src/models/user.ts
         或 git reset --soft HEAD~1（如已提交）
```

---

## CONTINUOUS_MODE_COMPLETE 格式

```
CONTINUOUS MODE COMPLETE - 所有可执行任务已完成
已完成: Task#A, Task#B  |  剩余: Task#X(InDraft), Task#Y(BLOCKED)
本轮连续完成 N 个任务
```

---

## 原子 Commit 职责

> **（R2）**：drec 是项目状态存档的**唯一入口**。写完 recording 后必须执行原子 commit，不得由调用方（drun 等）自行 commit。

### Commit 行为规范

| 条件 | 动作 |
|------|------|
| 工作区有变更（代码 + .diwu/ 状态文件） | `git add -A` 全量添加 → `git commit` 一次性提交 |
| 工作区无变更 | 跳过 commit，不报错，返回提示「无变更需提交」 |

### Commit Message 格式

单任务：
```
[recording] Session YYYY-MM-DD HH:MM:SS — Task#N {title} ({status})
```

多任务（同一 session 完成多个）：
```
[recording] Session YYYY-MM-DD HH:MM:SS — Task#A (Done), Task#B (InReview)
```

纯记录（无具体任务关联，如中间 checkpoint）：
```
[recording] Session YYYY-MM-DD HH:MM:SS — {简述}
```

### Git Add 范围

**全量 `git add -A`**：包含所有工作区变更——代码文件、`.diwu/recording/`、`.diwu/dtask.json`、`.diwu/dtask-state.json` 等全部状态文件。一个 commit = 一次完整快照。

> **为什么全量而非仅 .diwu/**：recording 记录的是"发生了什么"，代码变更是"改了什么"，两者属于同一次 session 的产出，应原子提交避免历史分裂。

### 执行步骤

1. 按 Session 文件格式模板写入 `.diwu/recording/session-{timestamp}.md`
2. 运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳用于 commit message
3. 检查 `git status --short` 是否有变更
4. 有变更 → `git add -A && git commit -m "[recording] Session {timestamp} ..."`
5. 无变更 → 输出跳过提示，返回成功
6. 将 commit hash 作为输出返回给调用方

---

## 调用契约

### 输入

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session 内容摘要 | 字符串 | 是 | 本次 session 的核心内容：处理了哪些任务、做了什么改动、验收结果、下一步计划 |
| 关联任务列表 | 数组 | 否 | 本 session 涉及的任务 ID 和状态，用于生成 commit message |

### 输出

| 返回值 | 说明 |
|--------|------|
| recording 文件路径 | `.diwu/recording/session-{timestamp}.md` 的绝对路径 |
| commit hash | git commit 的 SHA（无变更时为空字符串） |

### 调用方职责（drun / dloop / 手动）

- **准备阶段**：整理 session 内容摘要（任务状态、实施内容、验收证据）
- **调用阶段**：将摘要传入 `/drec`，由 drec 负责：写入文件 → 格式校验 → 原子 commit
- **调用后**：读取返回的 commit hash，确认存档成功
- **禁止**：调用方自行执行 `git commit` 包含 recording 或 .diwu/ 状态文件
