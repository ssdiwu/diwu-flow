---
name: drec
version: "1.1"
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

Commit message 格式和 category 前缀映射详见 `rules/task.md` §提交规范。Git add 范围为全量 `git add -A`（代码 + .diwu/ 全部状态文件）。

---

## 执行步骤

1. 读取 `pending_recording` 标记（通过 dtask_transition.py show-pending）
   - 无标记 → 正常模式
   - 有标记 + ≤10min + HEAD 是 `[recording]` commit + 未 push → Amend 模式（追加到上一 commit）
   - 其他 → 正常模式新 commit
2. 按 `rules/templates.md` §Session 文件格式 写入 `.diwu/recording/session-{timestamp}.md`
3. 运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳
4. 执行归档：`python3 scripts/drec_archive.py run --cwd <项目根目录>`
5. 有变更 → `git add -A && git commit -m "..."`（amend 模式用 `--amend`）；无变更 → 跳过
6. 返回 commit hash 给调用方
7. closeout 成功后清除 pending_recording 标记

---

## 标记清除语义（R3）

**closeout 成功 = 以下任一**：recording 写入成功 / git commit exit 0 / 工作区干净无变更。

**不清除标记**：recording 写入失败 / git 操作返回非零退出码。

> Amend 模式的安全检查（HEAD 前缀匹配 + upstream reachability）由 dtask_transition.py 内部实现。amend 失败时回退到正常 git commit。

---

## 归档聚合

自动调用 `scripts/drec_archive.py run` 执行双轨归档（Task 轨道 + Recording 轨道）。阈值配置来自 `.diwu/dsettings.toml`。归档完成后自动执行踩坑聚合（扫描本次移动文件中的 `### 本次踩坑/经验` 段落，按六类聚类追加到 project-pitfalls.md）。

> 双轨归档详细规则和触发参数见 `scripts/drec_archive.py` 和 `rules/file-layout.md` §归档触发条件。

---

## 调用链

调用方（drun/dloop/手动）整理 session 摘要后传入 `/drec`。drec 负责：写入 recording 文件 → 格式校验 → 归档 → 原子 commit → 返回文件路径 + commit hash。调用方禁止自行 commit 包含 recording 或 .diwu/ 状态文件。
