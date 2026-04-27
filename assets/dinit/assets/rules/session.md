# Session 生命周期管理

> **规则约束级别说明**：本文件定义 Session 从启动到结束的完整生命周期规则。除非特别标注 `[建议]`，否则都是必须遵守的约束。

## Session 启动（必须按顺序执行）

**执行顺序约束**：Step 1-4 串行（Preflight 失败则停止）；Step 5 可选；Step 2/3 的 dtask 读取可合并。

### 1. Preflight 检查（增强版）

**基线验证**：运行 `.claude/checks/smoke.sh`（如存在），验证基线环境。

**三唯一确认**（开工检查前必须明确）：
- 唯一主线目录：本轮任务唯一允许承接主要实现和验收的目录
- 唯一运行入口：本轮要验证主链是否真的经过的实际启动/调用入口
- 唯一 canonical：当前必须以其为准的说明、接口或规则文件

**5 问开工检查**：
1. 这件事能不能直接做，还是先探索/先演示验证/先写最小规格？
2. 本次唯一主线目录、唯一运行入口、唯一 canonical 是什么？
3. 当前最可能先判断错的地方是什么？
4. 进入实施前最少要拿到哪些判别依据？
5. 完成后准备用哪类高等级证据判断结果成立？

**误判表预加载**：进入实施前先看当前现象是否落在历史高频误判中（见 `project-pitfalls.md` 或 rules/exceptions.md §现象表）。

**其他检查**：`git status` 确认工作区状态；recording/ 最新 session 中是否有未解决阻塞记录。

### 2. 上下文恢复
- **优先**读取 `.claude/continue-here.md`（如存在），读完后删除
- 否则用 `ls -t .diwu/recording/ | head -2` 读取最新 1-2 个 session 文件
- 读取 `.diwu/decisions.md`（如存在）
- 运行 `git log --oneline -20`

### 3. 归档检查（增强版）
- 统计 dtask 中 Done/Cancelled 任务数量
- 超过 `task_archive_threshold`（默认 20）时触发归档：
  - 移至 `archive/task_archive_YYYY-MM.json`
  - **聚合 project-pitfalls.md**：归档时将本次踩坑经验追加到 .diwu/project-pitfalls 文件（如存在），**每条必须标注具体 session 文件名作为来源**（如 `session-2026-04-18-213522.md`），禁止写归档文件名或占位符
- 更新 dtask 只保留活跃任务

### 4. 任务选择策略
- **优先恢复** InProgress 任务
- 否则选第一个 InSpec 任务，检查 blocked_by：
  - 为空/不存在 / 全部 Done → 可开始
  - 存在 InReview 且超前未达上限 → 可超前（标记 InReview + 立即 commit）
  - 达到超前上限 → 输出 PENDING REVIEW
- **禁止**选择 InDraft 任务

### 5. 环境初始化（可选）
- 运行 `.claude/init.sh`（如存在）
- 运行基线测试（build/lint），失败则先修复

---

## 持续运行模式（continuous_mode）

> 规则来源：settings.json `continuous_mode` 字段（默认 true）

| 模式 | 行为 |
|------|------|
| `true`（默认） | 任务 Done 后自动选择下一个可执行任务继续 |
| `false` | 每完成一个任务即停止，输出完成摘要等待人工介入 |

**关闭时仍续跑的例外**：当前任务 InProgress（断点恢复优先） / 存在未提交变更（防丢失）

**关闭时停止边界**：Done（小幅度）→ 停止+摘要；Done（大幅度）→ REVIEW；PENDING REVIEW；BLOCKED；无更多任务 → CONTINUOUS_MODE_COMPLETE

**超前实施回退方式**：`revert`（已 push）/ `reset --soft`（仅本地）/ `修改`（代码仍有效）

---

## Session 结束

在 session 结束前（含 context window 接近上限时）：

1. 确保所有代码变更已提交
2. 写入 `.diwu/recording/session-YYYY-MM-DD-HHMMSS.md`（必须运行 `date '+%Y-%m-%d %H:%M:%S'` 获取真实时间戳），记录：
   - Session 标题、处理的任务及状态、验收验证结果、下次应该做什么
   - **必填字段**：本次踩坑/经验（见下方格式规范）、遗留风险点
3. 如有重大设计决策，追加到 `.diwu/decisions.md`
4. 确保 dtask 反映最新状态

### 本次踩坑/经验（必填）

**约束级别**：必填，不可省略。每个 session 必须显式写入此字段。

**四段式格式模板**：

```markdown
### 本次踩坑/经验

- [类别] 现象描述 → 根因分析 → 错误判断 → 正确做法
```

**类别标签**（与 pitfalls.md Layer 1 六类泛化模式对齐）：
`环境漂移` / `数据缺口` / `读层现象` / `路由护栏契约` / `验证误读` / `分层未拆清` / `其他`

**示例**：

```markdown
### 本次踩坑/经验

- [环境漂移] 本地测试通过但 CI 超时 → CI 环境缺少代理配置导致网络超时 → 误判为代码性能问题 → 应先检查 CI 环境变量和网络配置再定位代码
- [验证误读] 单元测试全部 PASS 但功能不工作 → 测试 mock 了关键依赖导致假阳性 → 误判为已完成 → 应补充集成测试或端到端验证
```

**最低合法答案**（当本轮无显著误判时使用）：

```markdown
### 本次踩坑/经验

本轮无显著误判，实施路径符合预期。
```

> **注意**：最低合法答案仅用于确实无踩坑的 session。如果存在任何判断偏差、意外阻塞、返工或环境问题，必须按四段式格式记录。

**归档聚合指引**：归档时（recording/ 文件数超阈值），扫描所有即将归档的 session 文件中的 `### 本次踩坑/经验` 段落，按类别聚类后追加到 `.diwu/project-pitfalls.md`。**来源列必须写具体 session 文件名**（如 `session-2026-04-18-213522.md`）；归档文件内按 `## Source:` 分隔符追踪所属 session；更新记录中不写伪文件来源（下面已有具体 session 来源时，更新记录只写批次信息）。详见 pitfalls.md §Layer 2。

**Stop hook 检测正则**（供 Task#130 完整性检查使用）：

```python
import re

# 匹配本次踩坑/经验字段是否存在（兼容正常记录和最低合法答案）
PITFALL_PATTERN = re.compile(
    r'^###\s*本次踩坑[\/]?经验\s*\n'   # 标题行
    r'(.*\n)*'                            # 内容（允许空或多行）
    r'.+',                                # 至少有一行内容
    re.MULTILINE
)

# 最低合法答案专用匹配
PITFALL_MINIMAL_PATTERN = re.compile(
    r'###\s*本次踩坑[\/]?.*经验.*无显著误判.*符合预期',
    re.DOTALL
)
```

**匹配语义**：
- 正常踩坑记录：标题 `### 本次踩坑/经验` 存在 + 后续有四段式内容 → **PASS**
- 最低合法答案：包含"无显著误判"且包含"符合预期" → **PASS**
- 缺失：文件中不存在 `### 本次踩坑` 或 `### 本次经验` 标题 → **FAIL**（触发 Stop hook 告警）

### 工具失败处理协议（3-Strike）

**约束级别**：`[建议]`。由 `post_tool_use_failure.py` 自动执行，AI 无需手动计数。

当同一工具连续失败时，Hook 自动追踪并注入分级提示：

| 尝试 | 策略 | 注入内容 |
|------|------|---------|
| 1/3 | 诊断并修复根因 | 温和提醒：诊断根因，如有踩坑考虑记录 |
| 2/3 | 更换根本不同的方法 | 强烈建议：换工具/换文件/换策略 |
| 3+/3 | 广泛重新思考或升级用户 | 阻止继续：质疑假设，考虑升级 |

**状态持久化**：`/tmp/diwu_ctx_<pid>_errtrack` JSON 文件，冷却窗口默认 60 秒。
**开关**：`dsettings.json → error_tracking.enabled`（默认 true）。

### 结构化错误追踪表（可选增强）

**约束级别**：`[建议]`。推荐在复杂 session（多次工具失败、多轮纠偏）中使用。

当同一 session 中出现 2 次以上工具失败或纠偏时，建议在 `### 本次踩坑/经验` 之后追加结构化表格：

```markdown
### 错误追踪表（可选）

| 时间戳 | 工具 | 错误摘要 | 尝试 | 解决方式 | 类别 |
|--------|------|---------|------|---------|------|
| 01:30:05 | Bash | npm install E403 | 2 | 使用镜像源 | 环境漂移 |
```

**与四段式格式的关系**：表格是四段式的机器可读版本；两者记录同一信息，互为补充。表格方便跨 session 聚合查询，四段式适合人类阅读和 Stop hook 验证。

**PreToolUse 注入**：`inject_errors_decisions.py` 会自动扫描近期 session 的 `### 本次踩坑/经验` 段落并注入 context，无需手动回顾历史文件。

### Checkpoint 记录机制

当 context_monitor 达到 CRITICAL+DELAY 阈值时（见 templates.md 可调参数），自动写入 checkpoint：
- 将当前进度压缩写入 recording/ 最新 session 文件末尾
- 记录：当前任务状态、已完成步骤、下一步动作、关键上下文锚点
- 目的：context window 压缩后可快速恢复断点

### Context Window 管理
- context window 接近上限时会自动压缩，允许无限期继续工作
- 不要因 token 预算担忧而提前停止任务
- 始终保持最大程度的自主性

### continuous_mode=false 时的 Session 结束变体

**正常停止**（Done 且无 InProgress）：执行标准步骤 1-4，不自动选下一任务，输出摘要。
**开启后恢复**（false→true）：下次 Stop hook 触发时恢复自动续跑，无需重启 session。
