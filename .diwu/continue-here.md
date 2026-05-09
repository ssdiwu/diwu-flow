# Continue Here — PR5 说明层重写 + dloop cron 模式（下一位 AI 必读）

## 当前分支
- `feature/pr5-surface-model-docs`

## 当前目标（两个独立工作项）

1. **PR5 说明层重写**：统一 `.doc/架构规范.md`、根 README、skills/README.md 等说明层口径，与代码实际结构严格对齐。
2. **dloop cron 模式**：在 `skills/dloop/SKILL.md` 和 `scripts/dloop.py` 中实现 cron 定时循环模式，支持 `--mode cron --interval N` 启动无人值守批量执行。

两者共享同一分支，**不冲突**：说明层改文档口径，cron 模式改实现代码。

## 先说结论
- **PR4 已合并进 `main`**，当前分支就是从最新 `main` 开出来的干净主线。
- 分支包含两个独立工作项：
  - **说明层重写**：把项目的说明层（`.doc/架构规范.md`、根 README、skills/README.md 等）收口到位
  - **dloop cron 模式**：实现定时循环无人值守执行（见 `skills/dloop/SKILL.md` §Cron 模式）
- **不要**在分支里回头重写 rules 真相源、agent 本体，或顺手改与本轮无关的 hooks/scripts 逻辑。

---

## 本轮前的真实状态（必须先接受这些事实）

### 已完成并已合并到 `main`
- PR1：rules 真相源与导航层重构
- PR2：architect / debugger 接入执行链
- PR3：dpth + dref/dprd 增强式改造
- PR4：didea 本体与容器层

### 当前 `main` 的能力格局
- `didea` 已存在，并且是**入口容器层**
- `dpth` / `dref` / `dprd` / `ddoc` 已存在，并且是**产品判断 / 收束层**
- `dtask` / `drun` / `drec` 已存在，并且是**执行层**
- `dloop` 已存在，支持 **session 模式和 cron 模式**（cron 模式正在本分支实现）
- `architect` / `debugger` / `explorer` / `implementer` / `verifier` 已存在，并且 agent 边界已稳定

### PR5 的角色
- PR5 不是“发明新能力”
- PR5 是把**项目已经存在的能力模型**写清楚、写一致、写到正确的说明层位置上

---

## PR5 一句话定义（canonical）

> **PR5 重写项目的说明层与表层能力模型表达：统一 `.doc/架构规范.md`、根 README、skills/README.md 等的角色，让”项目是什么、各层做什么、用户怎么上手”与代码实际结构严格对齐。同时在 dloop 中实现 cron 定时循环模式。**

---

## PR5 的事实源（下一位 AI 必须按这个顺序读）

### A. 第一优先级：设计与边界真相源
1. `.diwu/decisions.md`
   - 重点看：`PR1-PR5 分层实施策略`
   - 这里定义了 PR5 依赖 PR1 / PR4 的原因
2. `.diwu/recording/session-2026-05-08-043652.md`
   - 重点看 37 行之后的“交接给下一位审查型 AI 的关键共识”
   - 这里明确了 PR3 / PR4 / PR5 的边界切法
3. `Issue #8` 的 PR3-PR5 定义评论
   - 已知 canonical comment：`issuecomment-4400717565`
   - 这里给了 PR5 的 In Scope / Out of Scope / Hard Dependencies / Soft Dependencies

### B. 第二优先级：项目结构与规则边界真相源
4. `rules/file-layout.md`
   - 只回答目标项目里“什么东西该放哪里”
   - 不要把插件源码仓结构重新塞回来
5. `rules/constraints.md`
   - 重点看 README / rules / `.doc/` 三者边界
6. `rules/README.md`
   - 看规则目录如何做导航，不要把 README 再写成规则正文

### C. 第三优先级：当前说明层现状（PR5 的主要改动对象）
7. `.doc/架构规范.md`
8. `.doc/README.md`
9. `README.md`
10. 如果存在，再看：`skills/README.md` / `commands/README.md`

### D. 第四优先级：能力现状事实源（用于写说明，不是让你改实现）
11. `.claude-plugin/plugin.json`
   - **插件版本唯一真值来源**
   - Skill / Command 注册数也以它为准
12. `agents/README.md`
13. `skills/didea/SKILL.md`
14. `skills/dpth/SKILL.md`
15. `skills/dref/SKILL.md`
16. `skills/dprd/SKILL.md`
17. `skills/dtask/SKILL.md`
18. `skills/drun/SKILL.md`
19. `commands/*.md` 薄壳入口（用于核对用户入口层）

---

## PR5 In Scope（你可以改什么）

### 1. `.doc/架构规范.md`
重写为双层文档：
- **Part A：能力架构层**
  - Commands / Skills / Agents / Rules / Scripts / Hooks / Assets 如何协作
  - 数据流 / 运行链路 / 层间关系
  - `didea -> dpth/dref/dprd/ddoc -> dtask -> drun -> drec` 的主链
  - `architect` / `debugger` 的位置
- **Part B：源码仓结构规范层**
  - 新 command / skill / agent / rule / README / test / asset 该放哪里
  - `.doc/` / `rules/` / README 的边界
  - 为什么 `rules/file-layout.md` 不讲插件源码仓结构

### 2. `.doc/README.md`
- 改成真正的导航索引
- 告诉读者：先看什么，再看什么
- 每个 `.doc/*.md` 的职责一句话写清

### 3. 根 `README.md`
- 回答三个最重要的问题：
  - 这个项目是什么
  - 有想法 / 要判断 / 要文档 / 要执行时分别该用什么
  - 细节要去哪看
- 只做说明与导航，不写规则正文

### 4. skills/README.md（如存在）
- 修正 Skill 类型分布统计，与实际 frontmatter 一致

### 5. 表层能力模型说明层结论
- `drun dual-entry`
- `dloop session / cron 双模式`（见 `skills/dloop/SKILL.md` §Cron 模式）
- Persistence Policy
- command / skill 的新增、删减、溶解原则
- `dstop` 这类 command-only 特例的定位

### 6. dloop cron 模式实现（本分支已并入）
- 修改 `skills/dloop/SKILL.md` 补充 cron 模式说明
- 修改 `scripts/dloop.py`、`scripts/dtask_state.py`、相关 hooks 实现 cron 模式运行链路
- 补充 `tests/level2/` 与 `tests/level2_scripts/` 对应测试
- 保持实现范围聚焦在 dloop cron 模式本身，不扩散到其他能力

---

## PR5 Out of Scope（绝对不要碰）

- 不改 `rules/` 真相源正文
- 不改 `agents/` 本体
- 不改 `skills/` / `commands/` / `agents/` 其他本体实现（`dloop` cron 模式相关改动除外）
- 不实现 `drun dual-entry` 行为本身（只能写说明层结论）
- 不改 `didea` / `dpth` / `architect` / `debugger` 的行为逻辑
- 不趁机做”顺手优化”
- 不新增与本轮无关的 hooks / scripts 改造

---

## 关键边界（下一位 AI 极易误判）

### 1. `.doc/` vs `rules/` vs `README`
- `.doc/` = **设计文档真相源**
- `rules/` = **运行规则真相源**
- `README` = **说明 / 导航层**

不要做这些事：
- 把规则写进 README
- 把设计 rationale 写进 rules
- 把插件源码仓结构规则塞进 `rules/file-layout.md`

### 2. PR5 不是实现层 PR
你可能会忍不住改这些实现文件来“让文档更对齐”——不要这样做：
- `skills/didea/SKILL.md`
- `skills/dpth/SKILL.md`
- `skills/dref/SKILL.md`
- `skills/dprd/SKILL.md`
- `skills/dtask/SKILL.md`
- `skills/drun/SKILL.md`
- `agents/*.md`
- `commands/*.md`

PR5 的正确动作是：**先以现有实现为事实，再改说明层。**

### 3. 数量统计不要凭感觉写
所有计数（Skill / Command / Agent / Hook 事件 / 脚本数）都必须先核实再写。
建议以这些为准：
- `.claude-plugin/plugin.json` → skills / commands 注册数
- `agents/*.md` → agent 文件数
- `hooks/hooks.json` → hook 事件数
- `hooks/scripts/*.py` → hook 脚本数

---

## 当前推荐的实施顺序（照着做）

1. **先读事实源**（上面 A → D 的顺序）
2. **先重写 `.doc/架构规范.md`**
   - 这是 PR5 的主骨架
3. **再改 `.doc/README.md`**
   - 让 `.doc/` 内部导航成立
4. **再改根 `README.md`**
   - 让项目外部入口成立
5. **判断是否真的需要 `skills/README.md` / `commands/README.md`**
   - 没必要就不要为了“完整”而新增
6. **最后统一核对数字、链接和交叉引用**
7. **跑全量测试**

---

## 当前已知的真实数字（但写入说明前仍建议复核）

> 注意：这些是当前会话已观察到的事实，不等于你可以不复核就直接写入文档。

- Skill 注册数：11（以 `.claude-plugin/plugin.json` 为准）
- Command 注册数：13（以 `.claude-plugin/plugin.json` 为准）
- Agent 文件数：5（`architect/debugger/explorer/implementer/verifier`）
- Rules 文件数：14
- Hook 事件数：8（SessionStart / TaskCreated / PreToolUse(Bash) / PreToolUse(ExitPlanMode) / PreToolUse(Edit|Write) / TaskCompleted / Stop / PreCompact）
- Hook 业务脚本数：11（不含 run_hook.py wrapper）
- 插件版本：`0.0.12`（唯一真值来源：`.claude-plugin/plugin.json`）

---

## 建议你重点核实的文件引用

在写说明层前，至少核实这些文件是否真实存在、表述是否稳定：
- `commands/didea.md`
- `skills/didea/SKILL.md`
- `skills/dpth/SKILL.md`
- `skills/dref/SKILL.md`
- `skills/dprd/SKILL.md`
- `skills/dtask/SKILL.md`
- `skills/drun/SKILL.md`
- `agents/README.md`
- `rules/file-layout.md`
- `rules/constraints.md`
- `rules/README.md`
- `.doc/架构规范.md`
- `.doc/README.md`
- `README.md`

---

## 验证标准（Done 之前必须满足）

1. `python3 -m pytest tests/ -q` 全量通过
2. `.doc/` 内交叉引用完整
3. 所有 README 中的 Skill / Command / Hook 数量与实际一致
4. 根 README 能清晰回答：
   - 我有想法 → 用什么
   - 我要做产品判断 / 需求细化 / PRD → 用什么
   - 我要执行任务 → 用什么
5. README 只做说明与导航，不新增规则正文
6. `.doc/架构规范.md` 能同时解释：
   - 能力架构层
   - 源码仓结构层

---

## 当前分支与远端状态
- 当前分支：`feature/pr5-surface-model-docs`
- 这是从 **已合并 PR4 的最新 `main`** 开出来的干净主线
- 你接手后，优先在这个分支继续，不要回到 PR4 分支补工作

---

## 最后一句提醒
- **先读、先核实、再写。**
- PR5 最容易犯的错不是“写错字”，而是**拿旧理解重写说明层**，把已经在 PR1-PR4 收口的边界又写乱。
- 你接手前，请先把上面的事实源逐个读完，再开始改文档。
