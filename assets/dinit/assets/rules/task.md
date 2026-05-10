# 任务状态机 — Persistent Task 真相源

> **规则约束级别说明**：本文件定义任务状态机核心规则。
> **定位**：`.diwu/dtask.json` 中 task 条目的 schema 真相来源与状态机契约。不承载实施流程（见 `skills/drun/SKILL.md`）或验收证据标准（见 `rules/verification.md`）。

## acceptance 格式规范

`functional`/`ui`/`bugfix` 类**必须**用 GWT；`infra`/`refactor` 类可选。

格式：`"Given [前置条件] When [用户动作] Then [预期结果]"`
- 多条件/结果用"且"连接；单条"且">3 个时拆分
- **Then 子句自检**：能否写成 `expect(actual).toBe(expected)`？

## dtask 结构

| 键名 | 类型 | 说明 |
|------|------|------|
| `id` | 数字 | 从 1 递增，永不复用 |
| `title` | 字符串 | 一句话描述（动词开头） |
| `description` | 字符串 | 背景+关键约束 |
| `acceptance` | 数组 | GWT 格式验收场景 |
| `steps` | 数组 | 实施步骤，绝对路径；[锁定]=技术选型 |
| `files_modified` | 数组 | (可选) 并行冲突检测 |
| `category` | 字符串 | functional/ui/bugfix/refactor/infra |
| `blocked_by` | 数组 | (可选) 前置任务 ID |
| `status` | 字符串 | 运行时状态 |

**运行态真相源**：`.diwu/dtask.json`(status) / `.diwu/dtask-state.json`(runtime 元数据) / `scripts/dtask_transition.py`(唯一状态转移入口)。

## 状态定义

| 状态 | 含义 | 修改权限 |
|------|------|----------|
| InDraft | 需求草稿中 | 可改所有字段 |
| InSpec | 已确认锁定 | 只改 status |
| InProgress | 实施中 | 改 status |
| InReview | 验证中 | 改 status |
| Done | 已完成 | 终态 |
| Cancelled | 已取消 | 终态 |

| 当前 → 事件 → 新状态 | 规则 |
|----------------------|------|
| InDraft → 确认 → InSpec | 不可再改需求字段 |
| InDraft → 取消 → Cancelled | - |
| InSpec → 开始 → InProgress | - |
| InSpec → 发现问题 → (保持) | 退回 InDraft |
| InProgress → 完成 → InReview | - |
| InProgress → 遇阻塞 → InSpec | 记录原因 |
| InProgress → 取消 → Cancelled | - |
| InReview → 通过(小) → Done | 自审 |
| InReview → 通过(大) → Done | 需人工确认 |
| InReview → 失败 → InProgress | 修复后重验 |
| Done/Cancelled | 终态，忽略所有事件 |
| Cancelled → 激活 → InSpec | 直接锁定 |

> 状态迁移通过 `dtask_transition.py` 执行。

### Architect 审稿 Gate

架构级变更（新增模块/改数据流/改核心抽象）时：InSpec 阶段必须 architect 审阅；InReview 阶段验证 constraints.md 六维约束。禁止绕过。

---

## blocked_by 规范

**语义**：前置任务未完成，当前无法开始。
**权限**：InDraft 自由；InSpec 可改需记录；InProgress+ 不可改。
**何时使用**：前置任务未 Done 且依赖其输出。仅代码调用时不使用。

**合法性检查**：
1. 无循环依赖（A→B→C→A）
2. 状态合理：✅ InSpec/InProgress/InReview；❌ Cancelled 拒绝

**自动清理**：Session 启动 / 任务变 Done 时移除已 Done ID。

## 不做的事

- 不生成中间 PRD markdown 文件
- 不自动将任务改为 InSpec

> commit message 格式见 `rules/templates.md`。
