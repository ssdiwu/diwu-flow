# 任务工作流

> **规则约束级别说明**：本文件定义任务从规划到实施到验证的核心工作流。Session 生命周期管理见 `session.md`。除非特别标注 `[建议]`，否则都是必须遵守的约束。

## 思维框架：从现象到动作

所有规则都是「现象 → 判断 → 动作」这条链的具体实例。违反这条链的规则是空壳，缺少这条链的工作是空转。

| 环节 | 含义 | 常见缺失 |
|------|------|---------|
| **现象** | 看到了什么（事实、数据、异常） | 抽象描述代替具体观察 |
| **判断** | 据此得出什么结论（依据什么） | 跳步到动作，或缺少依据 |
| **动作** | 接下来要做什么（具体行动） | 停在理解层，不推动执行 |

这条框架优先于任何具体规则。当规则和框架冲突时，先检查是否真的满足了三段论。

---

## 任务规划

### 触发条件
- 用户讨论想法/需求/功能设计
- dtask 为空或用户要求分解
- 用户描述较大功能需拆分步骤

### 分解流程

**示例锚点驱动**：执行前必读对应示例文件。

| 操作 | 必读示例文件 | 用途 |
|------|-------------|------|
| 生成 PRD | .claude/examples/prd.md | 对齐 PRD 格式和要素 |
| 写 acceptance | .claude/examples/acceptance.md | 对齐 GWT 格式和可断言性 |
| 拆解任务 | .claude/examples/task_breakdown.md | 对齐粒度和 blocked_by |
| 写 session 记录 | .claude/examples/session_record.md | 对齐记录格式 |

**需求精炼** `[建议]`：每次只问一个问题；提出 2-3 方案并推荐。

**InDraft 阶段**：提炼功能点 → 拆分为可描述任务 → 定义验收条件 → 识别依赖排序 → 展示结果 → 写入 dtask（状态 InDraft）。

**InSpec 阶段**：人工确认后 Agent 改为 InSpec；此后只能修改 status 字段；需改需求则退回 InDraft。

### 任务粒度标准
代码 < 2000 行；有明确 acceptance（GWT）；有清晰 steps（绝对路径）；不依赖未完成任务或在 blocked_by 标注。

### dtask 写入规则
状态一律 InDraft；ID 递增不复用；category: functional/ui/bugfix/refactor/infra；追加到列表末尾；必须含 acceptance（GWT）；steps 必须自包含。

---

## 任务实施

InSpec → InProgress → InReview → Done 完整流程：

### 不确定性决策节点（实施前必过）

| 判断问题 | 可预期 | 不可预期 |
|---------|--------|---------|
| 团队做过类似？ | 做过 | 没做过 |
| 90% 把握？ | 有 | 没有 |
| 外部依赖可控？ | 可控 | 不可控 |
| 多模块集成测过？ | 测过 | 没测过 |

**全部可预期** → 直接 InProgress；**任一不可预期** → 先 `/ddemo` 验证再 InProgress。

### 实施步骤
1. 状态改为 InProgress
2. 阅读任务描述/验收条件/实施步骤
3. [建议] 按项目既有模式实现；推荐顺序：验收测试框架 → 单元测试 → 实现
4. 文件路径修改后 grep 验证无残留
5. 按 workflow.md §验证要求验证
6. 通过后改 InReview；小幅度自审 Done，大幅度输出 REVIEW

**大幅度修改**：API/字段变更 或 单任务 >2000 行。其余自审即可。

**自审原则** `[建议]`：只实现 acceptance 要求，不多不少；不引入技术债。

### 执行偏差规则

> 详细锚点见 judgments.md §执行偏差分级

| 偏差等级 | 权限 | 例子 | 记录要求 |
|---------|------|------|---------|
| L1: Bug 修复 | 自动修复 | 类型错误/import缺失/语法错误 | session 文件 |
| L2: 关键缺失 | 自动补充 | 缺少错误处理/输入验证 | session 文件 |
| L3: 阻塞问题 | 自动修复 | 依赖缺失/配置格式错误 | session 文件 |
| L4: 架构变更 | **必须问用户** | 新建数据库表/切换框架/破坏性 API 变更 | DECISION TRACE |

单任务累计 L1-L3 ≤5 次，超则评估 acceptance/steps 缺陷。

### 提交规范

**时机**：常规=Done 时提交；超前=InReview 时立即提交。
**message**：常规 `[Task#N] 标题 - completed`；超前 `(超前 X/5, blocked_by Task#M)`。
**内容**：代码 + dtask + session 文件，同一 commit。

#### 提交粒度

**粒度约束**：单 task 单提交；只交 task 相关文件。

**内容清单**：
- 代码变更（仅当前 task 涉及的文件）
- dtask（状态更新）
- session 文件（记录）

#### 禁止行为

- **顺手改其他文件**：不得借 task A 的 context 顺手修改无关文件
- **批量更新多 task**：不得在单个 commit 中更新多个 task 状态或跨越多个 task 边界
- **无关格式调整**：不得包含与 task 目标无关的格式、注释、空白符调整

### 子代理策略

> 并行/串行选择见 judgments.md §并行与串行选择

**并行条件**（同时满足）：问题域不相交、无共享写文件、files_modified 无重叠。
**串行条件**（满足任一）：后步依赖前步输出 / 需积累上下文。

**专业化分工** `[可选]`：探索类 haiku 只读；验证类跑测试；实施类主模型写代码。
**Worktree 隔离** `[建议]`：并行实施可用 worktree 隔离。
**Coordinator Pattern**：dtask 状态由主代理维护。
**超前计数器**：主代理内存维护，session 重启后统计 InReview+blocked_by 恢复。
**启动仪式**（强约束）：SubagentStart Hook 自动注入最新 session 摘要 + InProgress 任务 title/acceptance/steps + decisions.md 最近 3 条。
**交接清单**（实施子代理必须返回）：acceptance PASS/FAIL 逐条 + 代码变更摘要 + 遗留阻塞点 + 下一步前置条件。

---

## 验证要求

**核心原则**：未验证 = 未完成。所有 acceptance 逐条验证通过后才标记 InReview。

**验证方式**：
1. 自动化（推荐）：`.claude/checks/task_<id>_verify.sh`
2. 手动：Agent 提供步骤清单 → 人工反馈 PASS/FAIL
3. 人工审查：大幅度修改输出 REVIEW 请求
4. 独立验证（可选）：verifier agent

**基线验证**：smoke.sh 验证基线环境。
**测试分层** `[建议]`：大幅度→浏览器工具；小幅度→lint/build/单元测试。
**运行态验证** `[建议]`：代码层通过后还需确认运行时走到新链路（日志/断言/真实请求/hooks 触发）。
**失败处理**：保持 InProgress，修复后重新验证。
