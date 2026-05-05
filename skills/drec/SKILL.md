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

## 设计决策记录

> 触发：Session 结束前（drun §Session 结束 Step 2）。写入 `.diwu/decisions.md`。

### 三档标准

| 档位 | 条件 | 示例 |
|------|------|------|
| **必须写** | 多方案选一 **或** 影响范围 >= 2 模块 | 统一 dtask-state.json vs 分散状态文件；脚本化 Command 转 Python |
| **建议写** | 对后续有约束作用的技术选型（单模块内） | 选 scripts/ 作共享库位置；max_tasks 取快照而非固定值 |
| **不写** | 记录本次 session 做了什么、下一步计划 | 常规实施日志、bug 修复过程 → 写入 session 文件即可 |

### 追加格式

```markdown
### YYYY-MM-DD HH:MM:SS 决策标题

- **备选方案**: A) ... B) ...
- **选定方案**: B
- **影响范围**: [模块列表]
- **理由**: [正向论证]
```

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

> **执行入口**：`/drec` 自动调用 `scripts/drec_archive.py run`；fallback 手动步骤在脚本不可用时使用。

### 双轨总览

| 轨道 | 归档对象 | 触发条件 | 产物 | 操作方式 |
|------|---------|---------|------|---------|
| **Task 轨道** | Done / Cancelled 任务 | 数量 ≥ `task_archive_threshold`（默认 20） | `archive/task_archive_YYYY-MM.json` | 序列化追加 + 从 dtask.json 移除 |
| **Recording 轨道** | Session 记录文件 | 文件数 ≥ `recording_archive_threshold`（默认 30）或超龄 | `archive/recording/YYYY-MM/session-*.md` | **移动**源文件到按 session 月份分片的子目录 |

### 触发参数

| 参数 | 默认值 | 配置来源 |
|------|--------|---------|
| `task_archive_threshold` | 20 | `.diwu/dsettings.json` |
| `recording_archive_threshold` | 50 | `.diwu/dsettings.json` |
| `recording_retention_days` | 30 | `.diwu/dsettings.json` |

### 选文件规则

① 移动所有超龄文件（mtime > retention_days 天）；② 若 `.diwu/recording/` 剩余数 ≥ threshold，按 mtime 从旧到新继续移动，直到活跃目录文件数严格 < threshold。目标子目录月份取 **session 文件名自身月份**。

### 踩坑聚合协议（9 步）

> 在 `run()` 的双轨归档完成后自动执行。扫描被移动的 recording 文件中的踩坑经验。

1. **扫描**：遍历本次移动的 `archive/recording/YYYY-MM/session-*.md` 中所有 `### 本次踩坑/经验` 段落
2. **来源追踪**：来源 = 文件名（如 `session-2026-05-04-021452.md`），无需额外 Source metadata
3. **按类别聚类**：按六类标签分组（环境漂移/数据缺口/读层现象/路由护栏契约/验证误读/分层未拆清/其他）
4. **同 session 同类别合并**：同一文件 + 同类别标签的多条踩坑合并为一条
5. **禁止跨 session 去重**：不同文件遇到同一问题是复发信号，各自保留独立条目
6. **禁止过期清理**：保留所有历史条目
7. **追加写入**：追加到 `.diwu/project-pitfalls.md`
8. **来源列规范**：来源列写文件名（如 `session-2026-05-04-021452.md`）
9. **无数据跳过**：如无踩坑数据则跳过

### Fallback 手动步骤（脚本不可用时）

[保留原 5 步手动流程作为降级路径，标注"优先使用脚本"]

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

0. **[前置检查]** 读取 `pending_recording` 标记：
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py show-pending --cwd .
   ```
   - 输出 `no_pending_recording` → 正常模式（跳到 Step 1）
   - 输出 `has_pending_recording` + task 详情 → 进入 Step 0b 判定

   **Step 0b — Amend 模式判定**：
   | 条件 | 动作 |
   |------|------|
   | 无标记 / null | 正常模式（原流程不变） |
   | 有标记 + ≤10min + HEAD 是 `[recording]` commit + **未 push** | **Amend 模式**（见下方 Amend 章节） |
   | 有标记 + ≤10min 但 HEAD 非 `[recording]` 或已 push | 正常模式新 commit |
   | 有标记 + >10min | 正常模式（stale 标记，closeout 后清除） |

1. 按 Session 文件格式模板写入 `.diwu/recording/session-{timestamp}.md`
2. 运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳用于 commit message
3. 执行归档：`python3 scripts/drec_archive.py run --cwd <项目根目录>` → 输出归档摘要；无归档需求则输出"无待归档内容"
4. 检查 `git status --short` 是否有变更（含归档产物）
5. 有变更 → `git add -A && git commit -m "[recording] Session {timestamp} ..."`（或 amend 模式下用 `git commit --amend -m "..."`; 归档产物纳入同一原子 commit）
6. 无变更 → 输出跳过提示，返回成功
7. 将 commit hash 作为输出返回给调用方
8. **[收尾]** closeout 成功后清除标记：`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py clear-pending --cwd .`

---

## Amend 模式

当 Step 0b 判定进入 Amend 模式时，将新 recording 内容**追加到上一个 `[recording]` commit** 中（而非创建新 commit）。

### 未分享 Commit 保护

```bash
# 检查 1: HEAD commit message 是否以 [recording] 开头
HEAD_SUBJECT=$(git log -1 --pretty=%s)
echo "$HEAD_SUBJECT" | grep -q '^\[recording\]' || { AMEND_ELIGIBLE=false; echo "HEAD 非 recording commit"; }

# 检查 2: HEAD 是否已 push（即 HEAD 是否 reachable from upstream）
if $AMEND_ELIGIBLE; then
    if git rev-parse @{u} >/dev/null 2>&1; then
        UNPUSHED_COUNT=$(git rev-list @{u}..HEAD --count 2>/dev/null || echo "0")
        if [ "$UNPUSHED_COUNT" -eq 0 ]; then
            AMEND_ELIGIBLE=false  # HEAD 已被上游包含，amend 会改写已分享历史
        fi
    fi
    # 无 upstream → 视为未 push，允许 amend
fi
```

### Amend 执行流程

```
1. 正常写入 recording 文件（Step 1，追加或新建）
2. git add -A（全量变更）
3. git commit --amend -m "[recording] Session {timestamp} — {updated_msg}"
4. 返回 amend 后的 commit hash
```

### Amend 回退策略

> 注意：Step 0b 前置判定已在执行 amend **之前**排除已 push / 非 recording commit 的场景，直接降级到正常模式。下表仅覆盖判定通过后仍发生的异常。

| 失败场景 | 处理方式 |
|----------|---------|
| 前置判定未拦截但 `--amend` 仍失败（如权限/锁冲突） | 放弃 amend，回退到正常 `git commit` 新建 commit |
| `git commit` 本身失败（merge conflict 等） | 输出错误信息，Agent 手动解决后重试 |

---

## 标记清除语义（R3）

> **（R3）**：drec **closeout 成功后**才清除 `pending_recording` 标记。以下情况视为 closeout 成功，可清除：
> - recording 文件已成功写入磁盘
> - `git commit` 成功（exit 0 + 返回 hash）
> - 工作区干净，判定"无变更需提交"（drec 原有 no-op 分支）
>
> **以下情况必须保留标记不清除**：
> - recording 写入失败（IO 错误/权限不足）
> - `git add` 或 `git commit` 返回非零退出码
> - 前置判定降级到正常 commit 后 `git commit` 仍失败

清除方式（仅 closeout 成功后调用）：
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py clear-pending --cwd .
```

### 完整失败处理表

| 失败场景 | 处理方式 | 标记状态 |
|----------|---------|---------|
| 前置判定发现 HEAD 已 push 或非 recording commit | 降级到正常 `git commit` 新建 commit（不执行 amend） | commit 成功后清除 |
| `git commit` 本身失败 | 输出错误，Agent 手动解决后重试 | **保留**（未 closeout 成功） |
| recording 写入失败 | 输出错误，不执行 commit | **保留** |
| 工作区干净（已被其他方式提交） | 跳过 commit，仅清除标记 | 清除（no-op 也是 success） |
| 标记 task_id 与 dtask.json status 不匹配 | 正常模式执行，closeout 成功后清除 + 输出警告 | 清除 |

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
