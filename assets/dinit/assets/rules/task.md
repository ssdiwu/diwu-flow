# 任务状态机

> **规则约束级别说明**：本文件定义任务状态机核心规则。除非特别标注 `[建议]`，否则都是必须遵守的约束。

## acceptance 格式规范（Given/When/Then）

`functional`/`ui`/`bugfix` 类**必须**用 GWT；`infra`/`refactor` 类**可选** `[建议]`。

格式：`"Given [前置条件] When [用户动作] Then [预期结果]"`
- 多条件/结果用"且"连接；单条"且">3 个时拆分
- `infra`/`refactor` 可用简单描述如 `"构建产物不超过 500KB"`

**Then 子句自检**：能否写成 `expect(actual).toBe(expected)`？不能则细化。

## dtask 结构

| 键名 | 类型 | 说明 |
|------|------|------|
| `id` | 数字 | 从 1 递增，永不复用 |
| `title` | 字符串 | 一句话描述（动词开头） |
| `description` | 字符串 | 背景+关键约束 |
| `acceptance` | 数组 | GWT 格式验收场景 |
| `steps` | 数组 | 实施步骤，绝对路径；[锁定]=技术选型，[建议]=实现细节 |
| `files_modified` | 数组 | (可选) 并行冲突检测 |
| `category` | 字符串 | functional/ui/bugfix/refactor/infra |
| `blocked_by` | 数组 | (可选) 前置任务 ID |
| `status` | 字符串 | 运行时状态 |

**任务分类** `[建议]`：

| 分类值 | 适用场景 |
|--------|---------|
| `functional` | 新增业务功能、API、核心逻辑 |
| `ui` | 页面、组件、交互、样式 |
| `bugfix` | 修复已知 bug |
| `refactor` | 不改变行为的代码结构优化 |
| `infra` | 构建、部署、配置、脚本 |

---

## 状态定义与转移

| 状态 | 含义 | 修改权限 |
|------|------|----------|
| InDraft | 需求草稿中 | 主代理可改 title/description/acceptance/steps |
| InSpec | 已确认锁定 | 主代理只能改 status |
| InProgress | 实施中 | 主代理可改 status |
| InReview | 验证中 | 主代理可改 status |
| Done | 已完成 | 主代理可改 status |
| Cancelled | 已取消 | 主代理可改 status |

| 当前 | 事件 | 新状态 | 规则 |
|------|------|--------|------|
| InDraft | 人工确认 | InSpec | Agent 不可再改需求字段 |
| InDraft | 取消 | Cancelled | - |
| InSpec | 开始实施 | InProgress | - |
| InSpec | 发现问题 | (保持) | 退回 InDraft 重确认 |
| InProgress | 完成准备验证 | InReview | - |
| InProgress | 遇阻塞 | InSpec | 记录原因 |
| InProgress | 取消 | Cancelled | - |
| InReview | 通过(小幅度) | Done | 自审 |
| InReview | 通过(大幅度) | Done | 需人工确认 |
| InReview | 失败返工 | InProgress | - |
| InReview | 取消 | Cancelled | - |
| Done | (终态) | — | 忽略所有事件 |
| Cancelled | 重新激活 | InSpec | 直接锁定 |

### 状态转移判定锚点

#### InReview → Done 判定锚点

| 场景 | 判定结果 | 证据等级要求 | 说明 |
|------|---------|-------------|------|
| API/字段契约变更 | 大幅度，需人工确认 | L1-L2 运行态证据 | 必须 REVIEW |
| 单任务 >2000 行 | 大幅度，需人工确认 | L1-L3 自动化证据 | 必须 REVIEW |
| 字段默认值变化影响调用方 | 大幅度，需人工确认 | L1 调用链证据 | 即使行数未超也按大幅度 |
| 小幅度+acceptance 全通过 | 小幅度，自审 Done | L3+ 至少一项 | 无需人工确认 |

> **证据等级参考**（详见 verification.md）：L1=运行态真实输出变化 / L2=调用链命中+状态切换 / L3=自动化测试+断言 / L4=日志截图页面现象 / L5=代码 diff+说明文字。默认 L1-3 主判，L4-5 辅助。仅 L5 不可宣称完成。

#### blocked_by 循环依赖锚点

| 依赖链类型 | 判定结果 |
|-----------|---------|
| A→B→C（无回边） | 合规 |
| A→B→C→A（有回边） | 违规，拒绝 |
| A→B 与 B→A 隐藏在不同描述 | 违规，拒绝 |

## blocked_by 规范

**语义**：前置任务未完成，当前无法开始。
**权限**：InDraft 自由；InSpec 可改需记录；InProgress 及之后不可改（需退回 InSpec）。
**何时使用**：前置任务未 Done 且当前依赖其输出时。已 Done 或仅代码调用关系时不使用。

**合法性检查**：
1. 无循环依赖（A→B→C→A）
2. 状态合理：✅ InSpec/InProgress/InReview；⚠️ InDraft 警告；❌ Done 提示说明即可；❌ Cancelled 拒绝

**自动清理**：
- 触发时机：Session 启动批量检查 / 任务变 Done 时立即清理引用
- 动作：移除已 Done 的 ID，session 文件记录 "Task#N 阻塞解除：Task#M 已完成"

---

## 提交规范（结构化增强）

### 结构化 commit message 格式

推荐使用 5 行固定格式（commit message 最佳实践）：

```
[Task#N] 标题 - completed
Category: functional/ui/refactor/infra/bugfix
Files: src/auth.ts, src/models/user.ts
Evidence: L1-L3 (运行态+自动化)
Status: Done
```

| 行 | 字段 | 说明 |
|---|------|------|
| 1 | 标题行 | `[Task#N] 标题 - completed` 或 `(超前 X/5, blocked_by Task#M)` |
| 2 | Category | 任务分类 |
| 3 | Files | 修改文件列表（逗号分隔） |
| 4 | Evidence | 证据等级范围（L1-L5，见 verification.md） |
| 5 | Status | `Done` 或 `InReview(超前 X/5)` |

### 并行 task 提交——子代理产出标识

多子代理并行时，commit message 中每个子代理的产出分块列出：

```
[Task#N] 标题 - completed (并行)

## 子代理 A (auth 模块)
Files: src/auth.ts, src/middleware.ts
Evidence: L2-L3
Acceptance: [x] GWT-1 PASS [x] GWT-2 PASS

## 子代理 B (payment 模块)
Files: src/payment.ts, src/gateway.ts
Evidence: L1-L3
Acceptance: [x] GWT-1 PASS [ ] GWT-2 FAIL → 已记录阻塞点

Status: InReview(超前 3/5)
```

### Checkpoint 机制

大任务实施过程中记录中间进度，写入 session 文件。

**触发条件**（满足任一即触发）：
- steps 数量 > `checkpoint_min_steps`（默认 5）
- 预估修改行数 > `checkpoint_min_lines`（默认 500）

**记录格式**（追加到当前 session 文件）：

```
### Checkpoint @ 步骤3/8
进度: 完成 auth 模块重构，payment 模块进行中
已修改: src/auth.ts(+120/-80), src/models/user.ts(+15/-5)
下一步: 步骤4 payment 模块重构 → 步骤5 集成测试
回滚方式: git checkout -- src/auth.ts src/models/user.ts
         或 git reset --soft HEAD~1（如已提交）
```
