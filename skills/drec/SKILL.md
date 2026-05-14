---
name: drec
version: "2.0"
description: "当 Session 结束需要写入记录、整理归档或 amend 上一个 recording 时使用"
effort: normal
argument-hint: "[session内容]"
---

## 不可协商规则

- 必须运行 `date '+%Y-%m-%d %H:%M:%S'` 获取真实时间戳，禁止手写日期
- 追加 session 记录前必须先 Read 当前 session 文件尾部，确认追加位置正确不覆盖已有内容
- drec 是项目状态存档的唯一入口，写完 recording 后必须执行原子 commit，禁止调用方自行 commit 包含 recording 或 .diwu/ 状态文件
- closeout 成功后才可清除 pending_recording 标记，closeout 失败时必须保留标记
- 本次踩坑/经验字段为必填，不得省略

# drec

Session 记录写入操作手册：每次 session 结束前的必做事项。

> **格式规则（时间戳、Session 模板、踩坑四段式等）的权威定义在 `rules/session.md` + `rules/templates.md`**，本文件只保留 drec 独有的操作流程和契约。

---

## 文件操作安全（R1）

**追加前必须 Read 当前 session 文件尾部**（如存在），确认追加位置正确不覆盖已有内容。

---

## 设计决策记录

触发：Session 结束前有重大设计决策时写入 `.diwu/decisions.md`。三档标准见 `rules/session.md` §何时写 decisions.md。

追加格式：

```markdown
### YYYY-MM-DD HH:MM:SS 决策标题

- **备选方案**: A) ... B) ...
- **选定方案**: B
- **影响范围**: [模块列表]
- **理由**: [正向论证]
```

---

## 原子 Commit 职责（R2）

> drec 是项目状态存档的**唯一入口**。写完 recording 后执行原子 commit。

### Commit 行为

| 条件 | 动作 |
|------|------|
| 工作区有变更 | `git add -A` 全量 → `git commit` 一次性提交 |
| 工作区无变更 | 跳过，返回「无变更需提交」 |

### Commit 前缀（Task#96 约定，AI 职责）

**前缀不由脚本硬编码或推断。** AI 在写入 recording 时必须根据实际变更内容判断并标注 `Category` 行：

```markdown
**Category**: refactor
```

脚本（`drec_write.py`）从该行读取前缀用于 commit message。映射表：

| Category | 前缀 | 典型场景 |
|----------|------|---------|
| functional | `[功能]` | 新功能实现 |
| ui | `[界面]` | UI 变更 |
| bugfix | `[修复]` | Bug 修复 |
| refactor | `[重构]` | 重构/规则改写 |
| infra | `[基建]` | 基础设施/工具链 |
| release | `[发版]` | 版本发布 |
| （无/纯记录） | `[记录]` | 纯 .diwu/ 状态文件变更 |

**判断原则**：看本次 session 实际改了什么——以代码变更为主还是以文档/状态为主。不确定时用 `[重构]` 或 `[记录]`。

Git add 范围为全量 `git add -A`（代码 + .diwu/ 全部状态文件）。

---

## Session 文件格式模板（R3）

写入 recording 时必须包含以下结构（详细格式见 `rules/templates.md` §Session 文件格式）：

```markdown
## Session YYYY-MM-DD HH:MM:SS
### Task#N: [标题] → [状态]
**实施内容**: - [工作项]
**验收验证**: - [x] [acceptance] ([方法])
**提交**: commit [hash]
### 下一步: [计划]
### 本次踩坑/经验
- [类别] 现象 → 根因 → 误判 → 正确做法
```

**禁止 YAML front matter**。Session 文件以 `## Session` 开头。

---

## 本次踩坑/经验（R4）

必填字段，采用四段式格式：

```markdown
### 本次踩坑/经验

- [环境漂移] 本地测试通过但 CI 超时 → CI 缺少代理配置导致网络超时 → 误判为代码性能问题 → 应先检查 CI 环境变量和网络配置
- [验证误读] 单元测试全部 PASS 但功能不工作 → 测试 mock 关键依赖导致假阳性 → 误判为已完成 → 应补充集成测试或端到端验证
```

**六类合法标签**：`环境漂移` / `数据缺口` / `读层现象` / `路由护栏契约` / `验证误读` / `分层未拆清` / `其他`

**最低合法答案**（确实无踩坑时使用）：

```markdown
### 本次踩坑/经验

本轮无显著误判，实施路径符合预期。
```

仅用于确实无踩坑的 session。存在任何判断偏差、意外阻塞、返工或环境问题时，必须按四段式记录。

---

## 归档聚合（R5）

自动调用 `scripts/drec_archive.py run` 执行双轨归档（Task 轨道 + Recording 轨道）。阈值配置来自 `.diwu/dsettings.toml`。归档完成后自动执行踩坑聚合（扫描本次移动文件中的 `### 本次踩坑/经验` 段落，按六类聚类追加到 project-pitfalls.md）。

> 双轨归档详细规则和触发参数见 `scripts/drec_archive.py` 和 `rules/file-layout.md` §归档触发条件。

---

## 工具失败处理协议 — 3-Strike（R6）

drec 执行过程中遇到工具失败时，按以下分级策略处理：

| 尝试 | 策略 | 注入内容 |
|------|------|---------|
| 1/3 | 诊断并修复根因 | 温和提醒：诊断根因，如有踩坑考虑记录 |
| 2/3 | 更换根本不同的方法 | 强烈建议：换工具/换文件/换策略 |
| 3+/3 | 广泛重新思考或升级用户 | 阻止继续：质疑假设，考虑升级 |

- **状态持久化**：临时文件（需确保可清理）
- **冷却窗口**：默认 60 秒
- **开关**：`dsettings.toml → error_tracking_enabled`（默认 true）

---

## 结构化错误追踪表（R7）

同一 session 出现 2 次以上工具失败时，在 `### 本次踩坑/经验` 之后追加：

```markdown
### 错误追踪表（可选）

| 时间戳 | 工具 | 错误摘要 | 尝试 | 解决方式 | 类别 |
|--------|------|---------|------|---------|------|
| 01:30:05 | Bash | npm install E403 | 2 | 使用镜像源 | 环境漂移 |
```

表格是四段式的机器可读版本；两者互为补充。

---

## Checkpoint 记录机制（R8）

当上下文监控达到临界阈值时自动写入 checkpoint：

```markdown
### Checkpoint @ 步骤3/8
进度: 完成 auth 模块重构，payment 模块进行中
已修改: src/auth.ts(+120/-80), src/models/user.ts(+15/-5)
下一步: 步骤4 payment 模块重构 → 步骤5 集成测试
回滚方式: git checkout -- src/auth.ts src/models/user.ts
         或 git reset --soft HEAD~1（如已提交）
```

---

## CONTINUOUS_MODE_COMPLETE（R9）

dloop 结束后常用输出格式：

```
CONTINUOUS MODE COMPLETE - 所有可执行任务已完成
已完成: Task#A, Task#B  |  剩余: Task#X(InDraft), Task#Y(BLOCKED)
本轮连续完成 N 个任务
```

---

## Amend 模式（R10）

当 pending_recording 存在且在时间窗内（≤600s）时，将新 recording 内容**追加到上一个 recording commit** 中（而非创建新 commit）。这是 drec 唯一允许改写已提交历史的场景。

### 判定逻辑（去 git 化）

```
pending_recording 存在 && released_at ≤ 600s → 尝试 amend
amend 成功 → closeout 完成
amend 失败（任何原因）→ fallback 到新建 recording + 普通 commit
```

不再依赖 `git log -1` 做 HEAD 前缀匹配或 `git rev-parse` 做 upstream reachability 检查。amend 失败由 git 自身报错，脚本自动 fallback 到普通 commit。

### 回退策略

| 失败场景 | 处理方式 |
|----------|---------|
| `--amend` 权限/锁冲突 | 放弃 amend，回退到正常 `git commit` 新建 commit |
| `git commit` 本身失败 | 输出错误信息，保留 recording 和 pending_recording，返回 recovery_hint |

### 禁止双写

amend 模式下若 worktree 不一致且可能重复追加内容时，直接退出并要求人工介入。

---

## 标记清除语义（R11）

> **（R11）**：drec **closeout 成功后**才清除 `pending_recording` 标记。

**closeout 成功 = 以下任一**：
- recording 文件已成功写入磁盘
- `git commit` 成功（exit 0 + 返回 hash）
- 工作区干净，判定"无变更需提交"

**必须保留标记（不清除）**：
- recording 写入失败（IO 错误/权限不足）
- `git add` 或 `git commit` 返回非零退出码

---

## Gap 检测（R13）

> **v2.0 新增**：closeout 时自动执行 G1/G2/G3 三档信号级检查。**不阻塞 closeout**。

### 三档判定

| 判定 | 含义 | drec 行为 |
|------|------|-----------|
| **SYNCED** | 代码变更与 `.doc/` 一致，或本次无 doc-sync 要求 | 记录 `gap: none`，正常 closeout |
| **GAP_DETECTED** | 代码改了但对应 `.doc/` 段落未更新 | 记录 `gap: detected` + 具体位置，**不阻塞 closeout** |
| **DOC_AHEAD** | `.doc/` 更新了但代码尚未跟进（规划先行场景） | 记录 `gap: doc-ahead`，正常 closeout |

### G1/G2/G3 信号级检查

| 检查 | 检查项 | 判定逻辑 | 自动化程度 |
|------|--------|---------|-----------|
| **G1** | rules/skills/agents 变更 vs `.doc/` | 本次 commit 有 rules/skills/agents 文件变更 → 检查 `.doc/` 中是否有对应更新 | 可自动判定 |
| **G2** | dfeat.doc_sync 要求 vs 实际 | dfeat 的 `[remote].doc_scope` 声明了目标文件但未被本次 commit 修改 | 可自动判定 |
| **G3** | 版本号 vs CHANGELOG | plugin.json 版本号已变但 CHANGELOG 无可辨识追加 | 可自动判定 |

### 不阻塞 closeout 的理由

1. drec 的定位是记录者 + 检查者，不是 gate（那是 dgate 的职责）
2. 阻塞等于让记录工具变成执行拦截器，破坏职责分离
3. gap 信息写入 session 文件后，SessionStart hook 可注入提醒，形成延迟纠偏链路

### 输出格式

closeout 脚本输出 JSON 新增 `gap_detection` 字段：

```json
{
  "gap_conclusion": "GAP_DETECTED",
  "checks": [
    {"check": "G1", "status": "GAP_DETECTED", "detail": "..."},
    {"check": "G2", "status": "SYNCED", "detail": "..."},
    {"check": "G3", "status": "SYNCED", "detail": "..."}
  ],
  "message": "GAP_DETECTED (1/3)"
}
```

### Session 文件标注格式

当 gap_conclusion 为 GAP_DETECTED 时，AI 应在 session 文件的 `### 本次踩坑/经验` 之后追加：

```markdown
### Gap 检测

| Check | 状态 | 详情 |
|-------|------|------|
| G1 (rules/skills vs .doc/) | GAP_DETECTED | skills/drun/SKILL.md 已更新但 .doc/ 未同步 |
| G2 (dfeat.doc_sync) | SYNCED | 无未满足的 doc_sync 要求 |
| G3 (version vs CHANGELOG) | SYNCED | CHANGELOG 已同步 |

结论: GAP_DETECTED — 标记但不阻塞 closeout。建议下次 Session 启动时调用 `/ddoc --incremental`。
```

> **与 doc-sync 检查点的关系**：drun 在 release 前做 doc-sync（要不要同步），drec 在 closeout 时做 gap 检测（同步了没有）。两者互补不重叠。

---

> **v2.0 变更**：从 AI 手工执行链切换到 `drec_write.py run` 脚本驱动。

### AI 侧职责（调用前）

1. 整理 session 内容摘要（纯 markdown 正文）
2. 执行 `date '+%Y-%m-%d %H:%M:%S'` 获取真实时间戳（禁止手写）
3. 直接写入 `.diwu/recording/session-{timestamp}.md`（包含 `## Session YYYY-MM-DD HH:MM:SS` 标题行）
4. 调用脚本：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/drec_write.py run --cwd <项目根目录>
```

### 脚本侧职责（`drec_write.py`）

| 步骤 | 动作 | 失败处理 |
|------|------|---------|
| 检测 recording | 扫描 `recording/` 取 mtime 最新的 session 文件 | 不存在 → 返回 failed + hint |
| 归档 | 调用 `drec_archive.py run` | 失败不阻止 commit，记录到 archive_summary |
| Git commit | `add -A` + `commit` / `--amend` | 失败 → 保留所有状态，返回 recovery_hint |
| 清理 | clear-pending | 仅 closeout 成功后执行 |

### 输出

脚本 stdout 返回 JSON：

```json
{
  "ok": true,
  "status": "committed|amended|no_changes|partial_success|failed",
  "recording_path": ".diwu/recording/session-2026-05-12-143022.md",
  "commit_hash": "abc1234",
  "archive_summary": "无待归档内容",
  "gap_detection": {
    "gap_conclusion": "SYNCED|GAP_DETECTED",
    "checks": [...],
    "message": "..."
  }
}
```

### dloop 兼容

- `drec_write.py` **不区分 drun / dloop 调用方**；只依赖 `pending_recording` 标记
- `CONTINUOUS_MODE_COMPLETE` 格式由 AI 写入 recording 正文，脚本不负责生成该段
- `stop_decision.py` 的阶段报告仍由其自身负责；`drec_write.py` 只做 closeout

---

## 调用链

调用方（drun/dloop/手动）整理 session 摘要后传入 `/drec`。AI 负责：获取时间戳 → 直接写 recording 文件 → 调用 `drec_write.py run` → 解析结果 JSON。调用方禁止自行 commit 包含 recording 或 .diwu/ 状态文件。
