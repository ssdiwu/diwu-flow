# 判断锚点集中管理

> **规则约束级别说明**：本文件集中管理所有判断性规则的示例锚点。按任务阶段分为四段式索引。判断性规则必须提供正例、反例、边界例作为执行依据。

## 一、启动判断

### 基线失败时先修基线还是继续

**规则来源**：session.md §Preflight 检查

- **正例**：`smoke.sh` 中定义的 build 或 lint 失败。结论：先修复基线，再开始新任务。
- **反例**：明知 build/lint 失败仍直接将任务设为 InProgress 并继续开发。结论：违规。
- **边界例**：失败项来自不在 `smoke.sh` 范围内的可选集成测试。结论：可记录风险后继续，但不得声称"基线通过"。
- **结论输出**：使用 `DECISION TRACE` 记录失败命令、日志证据、继续或暂停的理由。

### 不确定性决策

**规则来源**：workflow.md §不确定性决策节点

- **正例**：任务是「给 API 接口加一个字段」，团队做过多次，结果完全确定。结论：直接 InProgress。
- **反例**：任务涉及 Prompt 改写让 LLM 输出特定格式，LLM 行为有不确定性。结论：先 /ddemo 验证 Prompt 稳定性，再 InProgress。
- **边界例**：任务是「集成两个已各自验证过的模块」，但组合行为未测试。结论：不可预期，先 /ddemo 做集成验证。

### 入口门控（任务推进方式选择）

**规则来源**：mindset.md §不确定性门控

| 推进方式 | 条件（满足任一即走此路径） |
|---------|--------------------------|
| **直接做** | 改动范围小 + 结果可预期 + 预期差异一句话说清 |
| **先写最小规格** | 结果不能一句话说清 / 依赖外部系统或运行时链路 / 第一次做的新能力 / 输出需稳定格式 / 需要交接 |
| **先探索验证** | 外部依赖多且不可控 / 加载策略容易漂移 / 组合行为不稳定 / 真实落点不明确 / 回滚成本高 |

---

## 二、实施判断

### 大幅度修改判定

**规则来源**：workflow.md §任务实施

- **正例**：接口响应字段发生变更，或单任务代码改动超过 2000 行。结论：大幅度修改，必须输出 REVIEW 请求并等待人工确认。
- **反例**：只修复内部实现 bug，API/字段不变，改动 120 行。结论：小幅度修改，可自审后 Done。
- **边界例**：改动 600 行但跨多个核心模块并引入兼容层。结论：若 API/字段无变化可按小幅度执行；只要契约变化即强制按大幅度处理。
- **结论输出**：使用 `DECISION TRACE` 记录 API 变更证据与 `git diff --stat` 数据。

### 执行偏差分级

**规则来源**：workflow.md §执行偏差规则

- **正例（Level 2 自动补充）**：实现用户注册时发现缺少 email 格式校验，acceptance 没写但显然需要。结论：Level 2 自动补充，写入 session 文件记录。
- **反例（Level 4 必须问用户）**：发现 PostgreSQL 比 MySQL 更适合当前场景，想换数据库。结论：Level 4 架构变更，停下问用户并输出 DECISION TRACE。
- **边界例**：需要新增一个工具函数且不改变 API。结论：如果 < 20 行，按 Level 2 处理；如果引入新的公共接口，按 Level 4 处理。

### 并行与串行选择

**规则来源**：workflow.md §子代理策略

- **正例**：子代理 A 仅修改 `src/auth/`，子代理 B 仅修改 `src/payment/`，无共享写文件。结论：可并行。
- **反例**：两个子代理都要修改 `src/models/user.ts` 或同一迁移文件。结论：必须串行。
- **边界例**：代码目录不同，但都依赖同一个生成产物（如 `openapi.json`）。结论：先串行生成共享产物，再并行执行剩余步骤。
- **结论输出**：使用 `DECISION TRACE` 记录模块边界、共享写文件检查结果和执行顺序。

### 任务选择与超前实施

**规则来源**：session.md §任务选择策略

- **正例**：Task#21 为 InSpec，`blocked_by=[20]`；Task#20 为 InReview，当前超前计数 2/5。结论：可超前实施 Task#21，完成后标记 InReview 并提交，计数更新为 3/5。
- **反例**：Task#21 为 InSpec，`blocked_by=[20]`；Task#20 为 InProgress，或当前已超前 5/5。结论：跳过 Task#21，选择下一个可执行任务。
- **边界例**：`blocked_by=[18,20]`，其中 Task#18 已 Done、Task#20 为 InReview，当前超前 4/5。结论：先清理已 Done 依赖，再允许超前至 5/5；达到上限后输出 PENDING REVIEW。
- **结论输出**：使用 `DECISION TRACE` 记录 dtask 状态、blocked_by 明细和超前计数。

---

## 三、验收判断

### InReview → Done 是否需人工确认

**规则来源**：task.md §状态转移判定锚点

- **正例**：存在 API/字段契约变更，或单任务改动超过 2000 行。结论：先输出 REVIEW，人工确认后再 Done。
- **反例**：小幅度修改且 acceptance 全部通过。结论：可自审后直接 Done。
- **边界例**：改动行数未超 2000，但字段默认值变化会影响调用方行为。结论：按大幅度处理，走人工确认。
- **结论输出**：使用 `DECISION TRACE` 记录契约变化证据、改动规模和最终状态决策。

### blocked_by 何时不该写

**规则来源**：task.md §blocked_by 规范

- **正例（应该写）**：Task#9 依赖 Task#8 生成的迁移文件，Task#8 未 Done。结论：写入 `blocked_by=[8]`。
- **反例（不该写）**：当前任务只是调用已稳定函数，且前置任务已 Done。结论：不写 blocked_by，在 description 说明即可。
- **边界例**：前置任务为 InReview，当前任务只依赖其稳定接口。结论：可不写 blocked_by，但需在 description 明确假设；若接口仍可能变动则写入。
- **结论输出**：使用 `DECISION TRACE` 记录依赖关系、前置状态和是否写入 blocked_by。

### 循环依赖识别

**规则来源**：task.md §blocked_by 规范

- **正例**：新增依赖后形成 A→B→C→A。结论：拒绝写入并提示重排任务顺序。
- **反例**：依赖链为 A→B→C（无回边）。结论：允许写入。
- **边界例**：A→B 与 B→A 藏在不同描述中。结论：仍按循环处理并拒绝写入。
- **结论输出**：使用 `DECISION TRACE` 记录完整依赖链和合法性检查结果。

---

## 四、纠偏判断

### continuous_mode 是否应自动续跑

**规则来源**：session.md §持续运行模式

- **正例**：`continuous_mode=true`（默认）；Task#10 刚 Done；存在 Task#11 为 InSpec 且无阻塞。结论：自动续跑，Stop hook 输出 block 继续 Task#11。
- **反例**：`continuous_mode=false`；Task#10 刚 Done（小幅度修改）；存在 Task#11 为 InSpec 且无阻塞。结论：不续跑，输出完成摘要停止等待人工介入。
- **边界例 A**：`continuous_mode=false`；当前任务为 InProgress（未完成）。结论：仍续跑，断点恢复优先级高于 continuous_mode 设置。
- **边界例 B**：`continuous_mode=false`；存在未提交变更。结论：仍续跑，防止工作丢失优先于 continuous_mode 设置。
- **边界例 C**：`continuous_mode=true`；Task#10 Done 但为大幅度修改（API 变更）。结论：不续跑，输出 REVIEW 请求等待人工确认。
- **边界例 D**：`continuous_mode=true`；超前已达上限（PENDING REVIEW）。结论：不续跑，输出 PENDING REVIEW 等待验收。
- **结论输出**：使用 `DECISION TRACE` 记录 continuous_mode 配置值、当前任务状态、是否有未提交变更、候选下一任务列表和最终决策。

### 何时写入 recording

**规则来源**：session.md §Session 结束

- **正例**：本次 session 有 task 状态变化（InSpec→InProgress、InProgress→InReview 等）、有 git commit、有重要设计决策讨论。结论：写入新 session 文件。
- **反例**：本次 session 只是简单问答、确认状态、阅读文件没有任何修改或决策。结论：不写入。
- **边界例**：本次 session 有实质性讨论和方案决策但尚未产生代码修改。结论：写入新 session 文件，记录讨论结论和方案决策。
- **结论输出**：判断是否存在实质性工作（task 状态变化、git commit、文件修改、重要决策），无实质性工作则跳过写入。

### 何时写 decisions.md

**规则来源**：session.md §Session 结束

- **正例**：从多个方案中选定设计方向（如"引入 README 索引层"代替全量 glob 扫描），**且影响范围 ≥2 个命令/模块**。结论：写 decisions.md。
- **反例**：记录本次 session 做了什么、下一步计划。结论：写入新 session 文件，不写 decisions.md。
- **边界例**：重构某命令的定位（如"/ddemo 从分析报告改为落地文档生成器"）。结论：写 decisions.md（定位变更是设计决策）。
