---
name: drec
version: "1.1"
type: rule
description: "Session 记录写入操作手册——原子 commit、Amend 模式、标记清除语义、归档聚合策略、调用契约"
triggers:
  - "写 session 记录"
  - "Session 结束前整理"
  - "用户说 记录、recording"
keywords:
  - "recording"
  - "commit"
  - "amend"
  - "归档"
  - "decisions"
effort: normal
argument-hint: "[session内容]"
---

# drec

Session 记录写入操作手册：每次 session 结束前的必做事项。

> **格式规则（时间戳、Session 模板、踩坑四段式、Stop hook 正则、Checkpoint、CONTINUOUS_MODE_COMPLETE）的权威定义在 `rules/` 中**，本文件只保留 drec 独有的操作流程和契约。

## 前置依赖：rules/ 格式规范

写入 recording 前，以下格式规则由 hook 自动注入 system prompt（`rules/session.md` + `rules/templates.md`），Agent 必须遵守：

| 规则 | 权威来源 | 要点 |
|------|---------|------|
| 时间戳铁律 | `rules/session.md` §时间戳 | 必须运行 `date '+%Y-%m-%d %H:%M:%S'`，禁止手写 |
| Session 文件格式模板 | `rules/templates.md` §Session 文件格式 | 四段结构 + 禁止 YAML front matter |
| 踩坑四段式 + 类别标签 | `rules/session.md` §本次踩坑/经验 | 必填字段，六类标签，最低合法答案 |
| Stop hook 检测正则 | `rules/session.md` §Stop hook 检测正则 | PITFALL_PATTERN 匹配逻辑 |
| Checkpoint 格式 | `rules/templates.md` §Checkpoint / `rules/session.md` §Checkpoint | 触发条件 + 记录模板 |
| CONTINUOUS_MODE_COMPLETE | `rules/templates.md` §CONTINUOUS_MODE_COMPLETE | 循环完成输出格式 |
| 结构化错误追踪表 | `rules/session.md` §错误追踪表 | 可选增强表格 |
| 工具失败 3-Strike 协议 | `rules/session.md` §工具失败处理协议 | 分级提示策略 |

---

## 文件操作安全（R1）

**（R1）**：追加 session 记录到 `.diwu/recording/` 前 **必须先 Read 当前 session 文件尾部**（如存在），确保追加位置正确不覆盖已有内容。

---

## 设计决策记录

> 触发：Session 结束前。写入 `.diwu/decisions.md`。

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

## 原子 Commit 职责（R2）

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
   | 无标记 / null | 正常模式 |
   | 有标记 + ≤10min + HEAD 是 `[recording]` commit + **未 push** | **Amend 模式**（见 §4） |
   | 有标记 + ≤10min 但 HEAD 非 `[recording]` 或已 push | 正常模式新 commit |
   | 有标记 + >10min | 正常模式（stale 标记，closeout 后清除） |

1. 按 `rules/templates.md` §Session 文件格式模板 写入 `.diwu/recording/session-{timestamp}.md`
2. 运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳用于 commit message
3. 执行归档：`python3 scripts/drec_archive.py run --cwd <项目根目录>` → 输出归档摘要；无归档需求则输出"无待归档内容"
4. 检查 `git status --short` 是否有变更（含归档产物）
5. 有变更 → `git add -A && git commit -m "[recording] Session {timestamp} ..."`（或 amend 模式下用 `git commit --amend`；归档产物纳入同一原子 commit）
6. 无变更 → 输出跳过提示，返回成功
7. 将 commit hash 作为输出返回给调用方
8. **[收尾]** closeout 成功后清除标记：`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py clear-pending --cwd .`

---

## Amend 模式

当 Step 0b 判定进入 Amend 模式时，将新 recording 内容**追加到上一个 `[recording]` commit** 中（而非创建新 commit）。这是 drec 唯一允许改写已提交历史的场景。

### 未分享 Commit 保护

前置判定已在 Step 0b 排除已 push / 非 recording commit 的场景。安全检查由 `dtask_transition.py` 内部实现（HEAD subject 前缀匹配 + upstream reachability 检测），详见 `scripts/dtask_transition.py`。

### Amend 执行流程

```
1. 正常写入 recording 文件（Step 1，追加或新建）
2. git add -A（全量变更）
3. git commit --amend -m "[recording] Session {timestamp} — {updated_msg}"
4. 返回 amend 后的 commit hash
```

### Amend 回退策略

| 失败场景 | 处理方式 |
|----------|---------|
| 前置判定未拦截但 `--amend` 仍失败（权限/锁冲突等） | 放弃 amend，回退到正常 `git commit` 新建 commit |
| `git commit` 本身失败（merge conflict 等） | 输出错误信息，Agent 手动解决后重试 |

### 标记清除语义（R3）

> **（R3）**：drec **closeout 成功后**才清除 `pending_recording` 标记。

**closeout 成功 = 以下任一**：
- recording 文件已成功写入磁盘
- `git commit` 成功（exit 0 + 返回 hash）
- 工作区干净，判定"无变更需提交"

**必须保留标记（不清除）**：
- recording 写入失败（IO 错误/权限不足）
- `git add` 或 `git commit` 返回非零退出码
- 前置判定降级到正常 commit 后 `git commit` 仍失败

清除方式（仅 closeout 成功后调用）：
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py clear-pending --cwd .
```

---

## 归档聚合

> **执行入口**：`/drec` 自动调用 `scripts/drec_archive.py run`；fallback 手动步骤在脚本不可用时使用。

### 双轨总览

| 轨道 | 归档对象 | 触发条件 | 产物 | 操作方式 |
|------|---------|---------|------|---------|
| **Task 轨道** | Done / Cancelled 任务 | 数量 ≥ `task_archive_threshold`（默认 20） | `archive/task_archive_YYYY-MM.json` | 序列化追加 + 从 dtask.json 移除 |
| **Recording 轨道** | Session 记录文件 | 文件数 ≥ `recording_archive_threshold`（默认 30）或超龄 | `archive/recording/YYYY-MM/session-*.md` | **移动**源文件到按月份分片的子目录 |

### 触发参数

| 参数 | 默认值 | 配置来源 |
|------|--------|---------|
| `task_archive_threshold` | 20 | `.diwu/dsettings.json` |
| `recording_archive_threshold` | 30 | `.diwu/dsettings.json` |
| `recording_retention_days` | 30 | `.diwu/dsettings.json` |

### 踩坑聚合

双轨归档完成后自动执行：扫描被移动 recording 文件中的 `### 本次踩坑/经验` 段落，按六类聚类后追加到 `.diwu/project-pitfalls.md`。来源列写具体 session 文件名，禁止跨 session 去重。完整实现见 `scripts/drec_archive.py aggregate_pitfalls()`。

---

## 调用契约

### 输入

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session 内容摘要 | 字符串 | 是 | 本次 session 的核心内容：处理了哪些任务、做了什么改动、验收结果、下一步计划 |
| 关联任务列表 | 数组 | 否 | 本 session 涉及的任务 ID 和状态，用于生成 commit message |

### 输出

| 返回值 | 说明 |
|--------|--------|
| recording 文件路径 | `.diwu/recording/session-{timestamp}.md` 的绝对路径 |
| commit hash | git commit 的 SHA（无变更时为空字符串） |

### 调用方职责（drun / dloop / 手动）

- **准备阶段**：整理 session 内容摘要（任务状态、实施内容、验收证据）
- **调用阶段**：将摘要传入 `/drec`，由 drec 负责：写入文件 → 格式校验 → 原子 commit
- **调用后**：读取返回的 commit hash，确认存档成功
- **禁止**：调用方自行执行 `git commit` 包含 recording 或 .diwu/ 状态文件
