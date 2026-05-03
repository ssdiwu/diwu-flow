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

### 2026-05-02 21:33:04 project-pitfalls 注入策略：按类别分段摘要替代全文截断

- **备选方案**:
  - A) 全文截断：简单粗暴一刀切，超过上限直接截断尾部
  - B) 按类别分段摘要：解析 `## 类别` 分段，每类提取现象列一行一条+计数，末尾追加提示行
- **选定方案**: B
- **影响范围**: hooks/scripts/session_start.py（注入逻辑重写）+ rules/pitfalls.md（文档更新）+ rules/session.md（Preflight 第4步描述更新）+ assets 模板 + .claude/rules/ 副本 = **5+ 模块**
- **理由**:
  - 全文截断会丢失类别结构信息，用户看不到踩坑分类全貌
  - 分段摘要在长度可控（8000 字符上限）的同时保留了项目高频踩坑的分类可读性
  - 末尾「详细条目见 .diwu/project-pitfalls.md」提示引导用户查阅完整数据
  - 纯模板文件（无真实数据）不注入，避免噪音

### 2026-05-02 21:54:43 截断策略重构（Task#59）+ 去重合并策略（Task#60）

- **备选方案** (截断策略):
  - A) 维持全文截断，仅调大上限（4000→8000）
  - B) 替换为按 `## 类别` 分段摘要模式（已在上个 session 选定并实施）
- **选定方案**: B（延续上个 session 决策，本 session 落地到 session_start.py 代码实现）

- **备选方案** (去重合并策略):
  - A) 全局去重：跨 session 合并同类别的所有条目
  - B) 仅同 session + 同类别去重，保留跨 session 的复发信号
- **选定方案**: B
- **影响范围**: session_start.py（注入逻辑）+ 3 个测试用例适配新行为 + darc SKILL.md（归档第4步增加去重子步骤）
- **理由**:
  - 截断策略已在 21:33 session 决定为分段摘要模式，本 session 是代码落地
  - 跨 session 去重会丢失时间线信息（同一问题反复出现是重要的复发信号）
  - 同 session 内合并既减少冗余又保留归档粒度，不过度聚合

### 2026-05-03 02:12:04 _find_skills_dir() 多候选路径探测替代单路径硬编码

- **备选方案**:
  - A) 保持单路径 `PLUGIN_ROOT / "skills"` + 要求用户手动配置或创建 symlink
  - B) 多候选路径自动探测：marketplace → marketplaces → PLUGIN_ROOT/skills → 依次尝试
- **选定方案**: B
- **影响范围**: scripts/dinit.py 核心加载逻辑——影响所有使用 dinit 初始化的项目
- **理由**:
  - CC 插件安装后的实际目录结构存在 marketplace/marketplaces 拼写差异（不同 CC 版本行为不一致）
  - 单路径假设在真实用户项目中必然失败（skills/ 目录不存在于用户项目根目录）
  - 多候选探测是零配置兼容的唯一可行方案，fallback 链覆盖所有已知布局

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

### 2026-05-03 16:29:25 Plan→Dtask 门控机制：JSON marker 替代 file_path 判定

- **备选方案**:
  - A) 维持 file_path 判定方式（旧 contract，CC 实际不再传此字段）
  - B) JSON marker 方案：plan_exit_hint.py 用 tool_input.plan 创建含 session_id + 行数的 JSON marker，task_entry_guard 解析 JSON 判定
- **选定方案**: B
- **影响范围**: hooks/scripts/plan_exit_hint.py + hooks/scripts/task_entry_guard.py（双守卫核心逻辑）
- **理由**:
  - ExitPlanMode hook contract 变更：CC 实际传 tool_input.plan 而非 tool_input.file_path
  - 旧 contract 导致 marker 永远创建不了 → task_entry_guard hard block 静默失效（最危险的安全模式：看起来在工作实际不工作）
  - JSON marker 含 session_id 支持 cross-session stale 清理，比纯 file_path 判定更健壮

### 2026-05-03 17:04:32 v0.0.10 精简方案：删除 djug / darc / ddemo 三个废弃能力

- **备选方案**:
  - A) 全部保留但标记 deprecated
  - B) 删除三个能力，合并 darc 归档功能到 drec，清理全仓库引用
- **选定方案**: B
- **影响范围**: 删除 3 个 Skill 目录 + 1 个 Command + 5 个参考文件；修改 commands/skills/rules 三副本/plugin.json/marketplace.json/install.sh/README.md/.claude/CLAUDE.md 共 ~30 文件；Skills 12→10，Commands 11→12（新增 drec/dref）
- **理由**:
  - djug 内容与 rules/judgments.md 完全重复，无独立方法论价值
  - darc 是纯手动步骤清单，归档规范并入 drec SKILL.md 更符合「Skill 为底」原则
  - ddemo 被 rules/mindset.md 不确定性门控和 dprd 完全覆盖
  - 一次性清理避免技术债务累积，删除后全量测试通过确认无破坏

### 2026-05-03 17:25:15 版本号回退 0.1.0→0.0.10：acceptance 契约优先原则

- **备选方案**:
  - A) 保持 0.1.0（语义上算 minor 升级合理，且已写入多文件）
  - B) 回退到 0.0.10（acceptance 明确写了 0.0.10，违反 acceptance 即违反验收契约）
- **选定方案**: B
- **影响范围**: plugin.json + marketplace.json + install.sh + CHANGELOG.md + README.md 共 5 文件版本号回退
- **理由**:
  - acceptance 是验收契约不是建议，实施前未与 acceptance 对齐是实施错误
  - 0.1.0 暗示有 breaking change 或重要新功能，但本次实际是精简（删除功能），语义不符
  - 即使多文件已写入 0.1.0，回退成本低于 acceptance 契约失效导致的信任损失

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
