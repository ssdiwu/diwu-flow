# 设计决策记录

> 每条决策记录一次影响范围 ≥2 模块或多方案选一的设计决定。
> 格式：时间戳 + 决策标题 + 备选方案 + 选定方案 + 影响范围 + 理由。
> 详见 rules/judgments.md §何时写 decisions.md / skills/drec/SKILL.md §设计决策记录

---

### 2026-04-30 22:38:08 统一 runtime state 真相源：引入 dtask-state.json

- **备选方案**:
  - A) 维持分散状态：`dtask.json` 存 status，`dloop-state.json` 存 loop 元数据，owner 信息隐含在 InProgress 唯一性假设中
  - B) 统一 runtime state：新增 `dtask-state.json` 作为 owner/dloop 元数据唯一真相源，`dtask.json` 专注任务定义与 status
- **选定方案**: B
- **影响范围**: Task#26-31 全线（scripts/dtask_state.py / dtask_transition.py / dloop.py / dloop_state.py / stop_decision.py / context_monitor.py / pre_compact.py / task_completed.py / session_start.py / commands / skills / rules 三副本 / assets 模板）
- **理由**:
  - 分散状态下 `dloop-state.json` 与 task owner 无关联，普通 InProgress 断点恢复只能盲取 `ip[0]`，多 session 并发时可能误恢复 чужой 任务
  - 统一后 `dtask-state.json.task_sessions` 提供 session-scoped owner 语义，stop_decision / context_monitor / checkpoint 写入均有明确的 owner 匹配校验
  - `dtask_transition.py` 作为唯一允许同时修改 `dtask.json.status` 与 `dtask-state.json` 的入口，避免半完成状态
  - legacy `dloop-state.json` 迁移路径保留向后兼容

### 2026-05-03 00:14:28 drec 升级为项目状态存档唯一入口

- **备选方案**:
  - A) 保持纯参考型 Skill：drec 只定义格式模板，commit 由调用方（drun 等）自行执行
  - B) drec 成为 commit 唯一入口：写完 recording 后自动执行原子 `git add -A` + `git commit`
- **选定方案**: B
- **影响范围**: skills/drec/SKILL.md（新增原子 Commit 职责章节 + Amend 模式 + 标记清除语义）+ skills/drun/SKILL.md（Session 结束步骤改为调用 /drec）+ hooks/scripts/stop_decision.py（新增 recording 滞后提醒）+ rules/session.md 三副本（提交原子性铁律更新）
- **理由**:
  - 调用方自行 commit 导致 recording 与代码变更分裂为多个 commit，历史不可回溯
  - 统一入口后一个 commit = 一次完整快照（代码 + .diwu/ 状态 + recording），符合原子性原则
  - Amend 模式覆盖「连续任务快速完成」场景，避免每任务一个 noise commit

### 2026-05-03 17:04:32 v0.0.10 精简方案：删除 djug / darc / ddemo 三个废弃能力

- **备选方案**:
  - A) 全部保留但标记 deprecated
  - B) 删除三个能力，合并 darc→dref 功能到 drec，清理全仓库引用
- **选定方案**: B
- **影响范围**: 删除 3 个 Skill 目录 + 1 个 Command + 5 个参考文件；修改 commands/skills/rules 三副本/plugin.json/marketplace.json/install.sh/README.md/.claude/CLAUDE.md 共 ~30 文件；Skills 12→10，Commands 11→12（新增 drec/dref）
- **理由**:
  - djug 内容与 rules/judgments.md 完全重复，无独立方法论价值
  - darc 是纯手动步骤清单，归档规范并入 drec SKILL.md 更符合「Skill 为底」原则
  - ddemo 被 rules/mindset.md 不确定性门控和 dprd 完全覆盖
  - 一次性清理避免技术债务累积，删除后全量测试通过确认无破坏

### 2026-05-04 01:20:47 dadr 并入 ddoc 作为第三种文档模式

- **备选方案**:
  - A) 保持 /dadr 独立 Command，与 /ddoc 并列
  - B) 将 dadr 功能合并到 /ddoc 作为 --mode adr 子模式
- **选定方案**: B
- **影响范围**: scripts/dadr.py → scripts/ddoc_adr.py（重命名）；skills/ddoc/SKILL.md 新增 ADR 模式章节；commands/ddoc.md 重写为三模式入口；commands/dadr.md 删除；plugin.json commands 12→11；rules/file-layout.md/constraints.md/judgments.md 三副本同步；版本号 0.0.10→0.0.11
- **理由**:
  - dadr 和 ddoc 同属「文档产出」领域，独立 command 增加用户认知负担
  - 合并后 /ddoc 统一三种模式（正向/逆向/ADR），用户只需记住一个入口
  - 脚本重命名 dadr.py→ddoc_adr.py 明确归属关系

### 2026-05-04 01:25:26 Agent 模型分级 + drun verifier 终验门控

- **备选方案** (Agent 分级):
  - A) 所有 agent 继承父会话模型（当前行为）
  - B) explorer=haiku（只读探索快速廉价），implementer=sonnet（代码实施质量保证），verifier 继承不变
- **选定方案** (Agent 分级): B
- **备选方案** (verifier 门控):
  - A) 仅 S3/S4 子代理策略触发 verifier，S1/S2 由主代理自审
  - B) 所有路径 Done 前均经 verifier 终验（S3/S4 已调过则跳过）
- **选定方案** (verifier 门控): B
- **影响范围**: agents/explorer.md + agents/implementer.md（frontmatter model 字段）；skills/drun/SKILL.md（closeout 顺序重排：verifier→release→/drec）；rules/task.md/rules/judgments.md/rules/verification.md 三副本（Done 判定门槛更新）；commands/drun.md；tests/level1/test_agents_config.py（新增 required_model 断言）
- **理由**:
  - explorer 只做读操作不需要强推理能力，haiku 快速廉价可大幅降低探索成本
  - implementer 写代码需要质量保证，sonnet 在代码生成上优于 haiku
  - verifier 作为独立验收门可消除主代理自审的确认偏误（confirmation bias）
  - closeout 顺序调整为 verifier→release→/drec，确保验收在状态变更和存档之前
