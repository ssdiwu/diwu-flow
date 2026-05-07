# Continue Here — PR2 定义已就位

## 当前分支
- `feature/pr2-architect-debugger`

## 本次已完成
- 已基于最新 `main`（PR1 已合并）重新校准 PR2 边界。
- 已确认：PR2 不再做 rules 真相源重构；PR1 已把 `architect` / `debugger` 的规则边界写进 `rules/`，PR2 只负责把它们接入真实执行链。
- 用户明确要求：**不要新增或改写 `.diwu/dtask.json`**，本次只提供接手说明。

## PR2 一句话定义
- **PR2：将 `architect` 作为 `dtask` 的技术审稿 gate，将 `debugger` 作为 `drun` 的异常调查第一责任 Agent，并补齐 agent 行为测试；不改 rules 真相源，不引入新 command/skill，不触碰说明层重写。**

## In Scope
- 新建 `agents/architect.md`
- 新建 `agents/debugger.md`
- 修改 `skills/dtask/SKILL.md`：接入 architect gate 的触发条件、输入/输出、消费方式
- 修改 `skills/drun/SKILL.md`：接入 debugger 异常优先路由、回交 `implementer`、再进 `verifier`
- 最小修改 `agents/README.md`：补 architect/debugger 速查项
- 最小修改 `rules/judgments.md`：补 architect/debugger 的 dispatch 判断锚点
- 新增测试，覆盖 agent 配置、路由和协作行为

## Out of Scope
- 不改 `rules/handoff.md` / `rules/task.md` / `rules/workflow.md` 的真相源边界
- 不新增 `darch` / `ddebug` skill 或 command
- 不改 `commands/` 薄壳入口
- 不做 `.doc/架构规范.md`、根 `README.md`、`skills/README.md` 的说明层重写（留给 PR5）
- 不把 `testing-rule`、`didea`、`ddoc`、`dprd` 混进 PR2
- **不改 `.diwu/dtask.json`**

## 关键边界
- `architect` 属于 **`dtask` 定义域**，不是 `drun` 执行域。
- `debugger` 属于 **`drun` 执行域**，不是 `dcorr` 的替代品。
- `debugger` 负责诊断，不直接修代码；标准链路应为：
  - `debugger` → `implementer` → `verifier`
- `architect` 负责实施前技术审稿，不替代 `dprd` 的产品判断，也不替代 `ddoc` 的完整设计文档输出。

## 推荐实施顺序
1. 先补 `agents/architect.md` / `agents/debugger.md`
2. 再改 `skills/dtask/SKILL.md` 接 architect gate
3. 再改 `skills/drun/SKILL.md` 接 debugger path
4. 最后最小同步 `agents/README.md` / `rules/judgments.md`
5. 补测试并跑全量 `pytest tests/ -q`

## 建议修改文件
- `agents/architect.md`
- `agents/debugger.md`
- `agents/README.md`
- `skills/dtask/SKILL.md`
- `skills/drun/SKILL.md`
- `rules/judgments.md`
- `tests/level1/test_agents_config.py` 或拆成更细的 agent 配置测试
- `tests/level2/` 下新增 architect/debugger 路由测试
- `tests/level3/` 下新增 agent 协作一致性测试

## 已确认的非目标判断
- 旧讨论里提到改 `rules/workflow.md`，现在应降级为**尽量不改**；PR2 真实主战场是 `skills/` + `agents/` + 测试。
- `testing-rule` 已拆到独立 issue，不要重新并回 PR2。

## 落地时优先验证
- `architect` 是否只在 `dtask` 侧触发，且不会越界到 `drun`
- `debugger` 是否在“异常排查”场景下直接优先于 `explorer`
- `debugger` 输出是否为短诊断报告，而不是直接修复代码
- `implementer` / `verifier` 现有链路是否仍保持稳定

## 参考事实来源
- `rules/task.md` 已写入 architect gate
- `rules/handoff.md` 已写入主编排者边界与 handoff 协议
- `agents/README.md` 当前只有 `explorer` / `implementer` / `verifier`
- `skills/dtask/SKILL.md` 与 `skills/drun/SKILL.md` 仍未接入 architect/debugger 的真实行为

## 给下一位 AI 的注意事项
- 先读当前 `main`/本分支上的 `rules/task.md`、`rules/handoff.md`、`agents/README.md`、`skills/dtask/SKILL.md`、`skills/drun/SKILL.md`，再动手。
- 不要回头重写 PR1 已稳定的 rules 边界。
- 不要擅自补 `.doc/` 或 `README` 说明层内容。
- 用户这轮只要你准备好 PR2 的接手上下文，后续实现交给另一位 AI。
