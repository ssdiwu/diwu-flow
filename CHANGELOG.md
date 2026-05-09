## [v0.1.1] - 2026-05-10

### Added — dinit 集成 ddoc 提示

- **Step 8：文档生成提示**（`commands/dinit.md`）：validate 通过后根据项目规模自动输出对应建议
  - 正常项目（≥ 500 行）：提示运行 `/ddoc reverse` 生成产品文档到 `.doc/`
  - 极简/空项目（< 500 行）：提示跳过逆向模式，说明门槛和替代路径
- ddoc 本身不改动，仅 dinit 末尾增加衔接提示

---

## [v0.1.0] - 2026-05-09

### Architecture — 六层架构全局落地（PR#9 + PR#10 + PR3 + PR#11 + PR#18）

**PR#9 — Rules 真相源统一重构**
- 新增 `rules/handoff.md`（子代理交接协议）：dtask/drun 主编排者铁律边界、SubagentStart Hook 四维自动注入（Session 摘要 + 任务上下文 + Handoff Report 模板 + Plan→Dtask 门控）
- 新增 `rules/testing.md`（测试分层策略）：L1-L4 四层模型、幅度→验证方式映射、补测试触发条件；分工明确——testing 管"写什么测试"，verification 管"什么算完成"
- 重组 9 个已有 rules 文件边界（workflow/task/file-layout/mindset/verification/constraints/templates/judgments/README），消除职责重叠
- 三处副本同步：`rules/` ↔ `.claude/rules/` ↔ `assets/dinit/assets/rules/` 共 28 diff 一致
- 新增 `agents/README.md` 作为 agents 层导航文档

**PR#10 (PR2) — Architect / Debugger Agent 落地**
- 新增 `agents/architect.md`：技术审稿专家，归属 dtask 定义域，5 种触发条件（新增模块/改变数据流/修改核心抽象/影响 agent 边界/影响 rules 结构）
- 新增 `agents/debugger.md`：异常调查专家，归属 drun 执行域，4 种触发条件（acceptance 不符/3-Strike 工具失败/bug 排查/环境异常）
- 更新 `skills/dtask/SKILL.md` 和 `skills/drun/SKILL.md` 嵌入 agent 路由逻辑
- 新增三级测试：`test_agents_config.py`(L1) / `test_agent_routing.py`(L2) / `test_agent_collaboration.py`(L3)
- 更新 `rules/judgments.md` 纳入 architect/debugger 判定规则

**PR3 — 产品思维层（dpth / dref / dprd）建设**
- **dpth** (`skills/dpth/SKILL.md` + `commands/dpth.md`)：产品思维协作 skill，三模式路由（诊断/创始人/构建者），灵魂三问门控；配套 10 个 references 文件
- **dref** v2.0 重写：从 SOP 模板升级为增强式产品思维——先判真伪需求四维判断，再收敛为可执行检查清单
- **dprd** v2.0 重写：增强式产品论证——灵魂三问方向门控 → JTBD/故事思维/MVP 减法/逆向思维框架按需取用 → 渐进式收束输出 PRD
- 产品层 triggers 全面口语化改造，关键词匹配更自然

**PR#11 (PR4) — didea 入口容器层落地**
- 新增 `skills/didea/SKILL.md`：第 0 层入口容器，6 个动作（create/list/show/refine/archive/push），双入口模型（CLI + 对话式），下游衔接 dpth/dref/dprd/dtask
- 新增 `commands/didea.md` + `scripts/didea_core.py` + `scripts/didea_github.py`
- Plugin 注册：`plugin.json` / `marketplace.json` / `install.sh` / `CLAUDE.md` 同步更新
- 8 个新测试覆盖核心逻辑 + GitHub 集成 + 布局一致性

**PR#18 (PR5) — 说明层重写 + dloop Cron 模式**
- **dloop Cron 模式完整实现**：Cron 定时触发新 session 自动执行 `/drun`，每轮独立 session 不受 context compression 影响
- `scripts/dloop.py start` 自动读取真实 session ID，消除 dummy 窗口问题
- `hooks/scripts/stop_decision.py` cron 终止时自动输出 CronDelete 清理指令
- 新增 `commands/README.md` 和 `skills/README.md` 导航文档
- 说明层口径统一：根 README / 架构规范 / skills README / commands README 数字复核一致

### Bugfix — 批量修复

- **dloop session ownership 修复**：非 owner session 的 PENDING_REC 完全静默；session mismatch 时自动清理 `dtask-state.json` 孤儿状态 → `clear_loop_state()`
- **stop_decision stdout 泄漏修复**：移除 `cron_action` 内部指令泄漏到用户可见输出
- **stop_decision 退出码修正**：无 InProgress 任务时统一 exit(0)，不再显示 error
- **claim owner 防护**：`dtask_transition.py` 增加脚本级 owner mismatch 拒绝验证
- **归档格式修正**：`drec_archive.py` list→dict 标准格式 + max_task_id 防御兼容
- **dvfy 残留清理**：删除 `skills/dvfy/SKILL.md`（溶解到 drun 内部）
- **dadr 残留清理**：从 rules/file-layout.md / mindset.md 三副本移除 dadr 引用

### Documentation — 说明层完善

- 新增 `commands/README.md`（13 Commands 导航文档）和 `skills/README.md`（11 Skills 导航文档）
- `.doc/架构规范.md` 重写为六层架构描述
- 根 `README.md` 全面重写：Layer 1-3 分层表、drun dual-entry 模型、Persistence Policy
- Hook 事件计数从 8 修正为 6（hooks.json 实际事件键数）+ 10 业务脚本 + 1 wrapper

### Testing

- 全量测试 314 → **409 passed**

### Refactoring — 发版前收口

- **dloop 移除 session 模式**：只保留 cron 驱动，删 session 模式全部代码（`--mode` 参数、`decide_loop_mode`、session SID 三分支、session 隔离逻辑），19 个 session 模式测试移除
- **CLAUDE.md 原子化重组**：去重→分层→速查，消除 3 处重复定义，行为铁律三分类，行数 ~140→~100
- **README.md 场景先行重写**：叙事翻转为"问题→能力→设计"，六层架构归 `.doc/`，安装命令修正为 `marketplace add` + `plugin install`
- **rules 通用性修复**：11 文件逐条去 diwu-flow 专属内容，版本号/命名约束/注入机制/三副本回写全部泛化为通用表述
- **docs 同步**：`skills/README.md`、`commands/dloop.md` 同步 dloop 移除 session 模式口径

---

## [v0.0.12] - 2026-05-05

### Infrastructure — Hook 可观测性与阻断策略重构
- **`run_hook.py` 统一包装层**：所有 hook 经 `run_hook.py` 执行，输出统一带 `[事件/脚本名]` 前缀；stderr 追加到 `.diwu/logs/hooks.log`；消除裸 `2>/dev/null || true` 吞错
- **Hook 脚本分级**：`--mode strict`（阻断级，4 个：task_entry_guard/task_created_validate/task_completed/stop_decision）保留退出码；`--mode tolerant`（提示级，5 个）异常时降级为 exit 0 但记录日志
- **hooks.json 全量改造**：所有条目统一走 `run_hook.py --event --script --mode` 三参数格式

### Infrastructure — Session ID 存储隔离与并发安全
- **scoped session 文件**：全局 `/tmp/.claude_main_session` → `/tmp/.claude_main_session_<repo_hash[:16]>`，多仓库并行互不污染
- **原子写入**：`scripts/session_scope.py` 使用 tempfile + fsync + os.replace 四步原子替换，防并发写坏文件
- **读取优先级链统一**：event session_id → `CLAUDE_SESSION_ID` 环境变量 → scoped session 文件 → fallback（dtask_transition）/ 空 string 降级（stop_decision）
- **测试覆盖**：session_start 测试新增 scoped 写入验证 + dtask_transition 新增 TestAutoSessionIdResolution 7 用例

### Infrastructure — 卸载脚本健壮性与跨平台兼容
- **`--uninstall --dry-run`**：预览要删除的 symlink 不实际执行，降低误操作风险
- **realpath 三级 fallback**：`realpath` 命令 → `python3 -c 'os.path.realpath'` → 纯 shell `_normalize_path_shell`，GNU/BSD 兼容
- **路径边界检查**：`_is_under_flow_root()` 归一化后比对 FLOW_ROOT 树内路径，防 sibling 目录同名 symlink 误删

### Changed — [Breaking] /dend → /dstop 迁移 + dloop 三件套统一
- **[Breaking]** `/dend` 重命名为 `/dstop`（Command 名称变更）
- **[Breaking]** 删除 `scripts/dend.py`，停止逻辑（cancel）内联到 `scripts/dloop.py stop` 子命令（三件套：start/status/stop）
- `tests/test_dend.py` → `tests/test_dstop.py`，测试入口统一为 `dloop.py stop`
- 全量同步所有文档中的 `/dend` 引用为 `/dstop`（skills/commands/hooks/README.md/.doc/ 共 ~13 处）

### Refactoring — Skills 分层瘦身（rules 权威源原则）
- **drec SKILL.md 403 → 225 行（-44%）**：删除与 rules/ 重复的格式规则内容，替换为 `rules/session.md` + `rules/templates.md` 引用索引；Amend 碎片合并为 §4 单一权威章节；归档策略压缩为 3 行摘要 + 引用 `drec_archive.py aggregate_pitfalls()`
- **dtask SKILL.md 323 → 181 行（-44%）**：删除与 `rules/task.md` 重复的 ~133 行（状态机/GWT/task 结构/blocked_by/提交规范/Checkpoint），替换为 §0 前置依赖引用索引
- **dcorr.md 241 → 34 行（-86%）**：仅保留触发条件（6 条）+ 执行指引（引用 `skills/dcorr/SKILL.md` 五步协议）
- **所有权原则确立**：rules/ = 宪法级格式约束（hook 注入 system prompt），skills/ = 操作手册（仅保留独有流程和契约）

### Documentation — 三迭代文档补全与规则同步
- **README.md**：安装表补充 `--uninstall [--dry-run]`；仓库结构 scripts/ 补充 session_scope
- **`.doc/架构规范.md`**：Hook 表头更新为 run_hook.py 包装格式；新增包装层语义章节；SessionStart 写入目标改为 scoped 路径
- **`.doc/工程规范.md`**：引用索引表新增卸载健壮性条目
- **`rules/file-layout.md`**（三副本同步）：运行时文件表新增 scoped session 文件条目
- **`rules/constraints.md`**（三副本同步）：Concurrency 约束补充原子写入实例说明
- **测试修复**：`test_task_168_no_hardcoded_paths` 补充三元表达式 else fallback 白名单正则

### Configuration — recording_archive_threshold 调降
- **阈值从 50 → 30**：活跃 session 项目（如本插件自身开发）47 个 recording 即触发归档，50 偏高
- **全量同步 9 处**：dsettings.json（运行时配置）+ stop_archive.py + drec_archive.py（代码 DEFAULTS）+ file-layout.md（三副本）+ 状态文件规格.md + dsettings-guide.md + README.md + dsettings.json.template + drec SKILL.md（文档/模板）
- **归档执行**：19 个 session 文件归档至 archive/recording/2026-04/ 和 2026-05/，36 条 pitfalls 聚合

### Changed — Commit Message 格式重设计（中文分类前缀）
- **前缀体系重构**：commit message 从固定 `[recording] Session ...` 前缀改为基于内容的中文分类前缀：`[功能]`/`[界面]`/`[修复]`/`[重构]`/`[基建]`/`[记录]`
- **映射规则**：前缀取自 dtask.json 的 `category` 字段（functional→[功能], ui→[界面], bugfix→[修复], refactor→[重构], infra→[基建]）；纯 `.diwu/` 状态文件变更统一用 `[记录]`
- **同步更新**：`skills/drec/SKILL.md` §Commit Message 格式 + `.claude/rules/task.md` §提交规范 + `assets/dinit/assets/rules/task.md` 模板三处同步
- **历史清理**：30 个旧 `[recording]` 前缀 commit 通过 `filter-branch` 批量重写为分类格式

### Fixed — dtask-state.json 一致性检查强化
- **drun SKILL.md**：新增 commit 前必做步骤——Read `dtask-state.json` 确认磁盘状态干净（非 dloop 模式确认无残留 `active:true`；dloop 最后一轮确认最终文件不含冗余 key）
- **dloop SKILL.md**：结束检查清单第 3 项从验证 `dloop: null` 存在改为验证**最终干净状态**（`{version, task_sessions}` 不含 `dloop`/`pending_recording` key）；新增字段丢失风险说明（`sync_runtime_state()` 覆写行为）

### Refactoring — /simplify 路径常量提取与代码审查修复
- **路径常量统一**：硬编码路径字符串提取为模块级常量，消除跨文件不一致风险
- **代码审查修复**（2 项 commit）：/simplify 流程中发现并修复的边界条件和遗漏引用
- **rules 同步更新**：`9a00e1d` 规则文件内容同步至 `.claude/rules/` 和 `assets/dinit/assets/rules/`

### Infrastructure — pending_recording 自愈增强
- **stale 标记清除**：Task#91 closeout 后自动清理残留的 `pending_recording` 标记，防止后续 session 误触发 Amend 模式

### Cleanup
- **worktree 残留清理**：删除 48 个带 `' 2'` 后缀的 worktree 副本文件（历史操作遗留）

---

## [v0.0.11] - 2026-05-04

### Added
- **`.doc/` 产品文档目录**：bootstrap 四文档——README（索引+快速开始）、架构规范、状态文件规格（dtask.json / dtask-state.json）、工程规范（commit/message/session/pitfalls）
- **`scripts/drec_archive.py` 归档自动化脚本**：move 策略（移动非 symlink 至 archive 子目录按月份分片）+ 11 个行为测试覆盖选文件规则/分片逻辑/踩坑聚合/边界条件

### Changed
- **drec 主执行顺序合同变更**：`/drec` 执行流程从"先 commit 再可选归档"改为"先归档后 commit"，归档产物纳入同一 commit（commands/drec.md 全文替换 + SKILL.md 归档章节重写 + 执行步骤 Step 4/5 对调）
- **dstat nested archive 目录适配**：`get_archive_status()` 从 `glob("recording_*.md")` 改为 `(archive_dir / "recording").glob("**/*.md")`，支持归档后嵌套子目录结构
- **test_doc_consistency 三副本收口**：file-layout 检查从两副本（root/local）扩展为三副本（root/local/asset）；删除对不存在文件（api.md/product.md/schema.md）的引用；新增 `.doc/README.md` 链接有效性检查
- **file-layout `.doc/` 结构描述同步**：rules/file-layout.md 及其 .claude/rules/ 和 assets/ 副本共三处，均补充 `.doc/` 目录结构定义

### Fixed
- **Stop hook Chain A status 二次防御**：`decide_default_mode()` / `decide_loop_mode()` 在 resolution.is_match 后增加 task['status']=='InProgress' 二次验证，防止 stale entry 导致误判 block
- **verifier 遗留修复（3 项）**：drec SKILL.md 前缀修正、drec_archive.py docstring 补全、Chain A 加固后测试断言同步更新

---

## [v0.0.10] - 2026-05-03

### Added
- **pending_recording 三层兜底机制**：L0 release 写标记 → L1 Stop Hook 强制门控（.diwu/ dirty + session 匹配 + 30min 阈值）→ L2 drec Amend 模式（未分享 commit 保护 + success-only 清除语义）
- **`show-pending` / `clear-pending` CLI 子命令**：drec SKILL.md 前置检查和收尾清除走 canonical 入口，每次调用自动触发 self-heal
- **commands/drec.md**：新薄壳命令，/drec 成为真实 command 入口
- **commands/dref.md**：新薄壳命令，需求细化清单的 command 入口

### Changed
- **Stop Hook `git status --short` 解析修复**：`split(None, 1)` 替代 `strip()+l[3:]`，正确处理带前导空格的 dirty 路径（如 ` M .diwu/file`）
- **dinit.py sync-skills 双计数修复**：`repair_kind` 本地变量追踪操作类型，修复 symlink 修复被误报为 CREATED 的 bug
- **drec SKILL.md 归档聚合指引扩展**：从单段描述扩展为完整归档规范（双轨总览、触发条件、5步手动流程、3种产物格式、5项验收、5条约束）
- **dref SKILL.md 适配**：去平台耦合（移除 AskUserQuestion）、删自定义状态机（待评估/已确认等）、删 Phase 5 自动写文件、triggers 缩减至 6 个、depends 链接 dprd

### Removed
- **skills/djug/**：内容与 rules/judgments.md 完全重复，无独立方法论价值
- **skills/darc/**：纯手动步骤清单，已并入 drec SKILL.md 归档聚合指引章节
- **skills/ddemo/** + **commands/ddemo.md**：Demo 功能由 /dprd 内联验证流程替代
- plugin.json 中 djug/darc/ddemo 注册条目已清理

### Fixed
- Stop Hook `_check_pending_recording_gate()` 在 `decide_loop_mode()` 中被 `save_runtime_state()` 覆盖的问题——gate 检查移至 save 之前


# Changelog

All notable changes to diwu-flow will be documented in this file.

## [0.0.9] - 2026-05-02

### dloop start 返回文案修正（Task#58）

- **修复**：`dloop.py start` 的 `formatted_text` 和 `message` 从"首轮开始: Task#N"改为"请立即发起 /drun 完成首轮任务"，消除 Agent 绕过 /drun 直接实施的问题

### project-pitfalls.md 摘要注入模式（Task#59）

- **截断上限**：`MAX_PITFALLS_LEN` 4000 → 8000
- **摘要模式**：替换全文截断为按 `## ` 类别分段生成摘要——每类列出全部现象列（一行一条 + 计数），末尾提示"详细条目见 .diwu/project-pitfalls.md"
- **截断策略**：从最旧类别开始逐类裁剪，保证保留的最新类别完整（P1 补丁修复了初版实现的无限循环 bug）
- **测试**：新增 `test_truncation_never_cuts_newest_category_mid_section` 验证多类别裁剪后最新类别完整性

### darc 踩坑聚合去重合并（Task#60）

- **去重合并**：归档踩坑聚合时，同一 session + 同一类别标签的条目合并为一条
- **不去重范围**：不跨 session 去重（保留复发信号），不过期清理（保留所有历史条目）

## [0.0.8] - 2026-05-02

### project-pitfalls.md 自动注入（SessionStart hook）

- **核心变更**：`session_start.py` 新增 pitfalls 自动注入能力——每次 Session 启动时自动读取 `.diwu/project-pitfalls.md` 并注入 system prompt，无需 AI 手动读取
- **模板跳过**：结构化判定纯模板文件（含 HTML 注释 + 占位行 + 表头但无真实数据），不注入噪音；保留模板头但填了真实条目的文件正常注入
- **长度裁剪**：硬上限 4000 字符，超长内容按 `## ` 段落边界截断并标注 `[... 已裁剪早期条目 ...]`
- **HTML 噪音剥离**：注入前自动移除 `<!--` 开头的注释行
- **文档同步**：rules/pitfalls.md、rules/session.md、rules/README.md、drun SKILL.md、README.md、assets 模板及 .claude/rules 副本全部更新为"SessionStart 自动注入"口径
- **测试**：新增 8 个行为测试覆盖 6 个关键场景

## [0.0.7] - 2026-05-01

### dloop 安全网双层落地 + README 产品级重写 + 归档体系完善

- **dloop 安全网**（5 轮补丁）：task_entry_guard 退出码修正 exit(1)→exit(2)、dummy SID 首轮绑定窗口兼容、session_id 所有者判别、检查顺序修正（fail-fast 移到宽泛放行前）、dloop active 时 block Edit/Write；SKILL.md 检查清单 + stop_decision 清理后验证 dloop 已清空
- **drelease.sh**：public tag 同步机制修复 + 历史 tags 补推 + 标签竞态修复 + 修复 commit 中残留活跃 dloop runtime state
- **Task#48-54**：插件硬编码路径修复（conftest.py/commands/*.md 7 文件）、Stop hook 非法 decision 清零、auto session ID 解析、stop_decision 提示/cwd/install 边界修正
- **Task#55-57**：/drun 细粒度子代理委托机制、dtask SKILL.md Step 3 common.py 路径兼容性修复、归档 marker 机制 + dtask.json 清理
- **README 产品级重写**：架构总览 Mermaid 图 + Hook 事件表 + Skill 索引 + 完整工作流说明
- **归档**：Task #33-#57 共 25 个终态任务归档 + 踩坑聚合 ~40 条写入 project-pitfalls.md

## [0.0.6] - 2026-04-30

### Runtime State 统一 + /dloop v3 简化 + Plan-Guard + 大规模 Bugfix 收口

- **Runtime State 统一**（Tasks#26-30）：dtask-state.json 作为 runtime owner/dloop 元数据真相源；session-scoped 断点恢复；契约全链同步（dtask_transition.py / hooks / dloop）
- **/dloop 大幅简化 v3**（Tasks#33-39）：移除复杂状态机，回归 while(未停止){ /drun } 薄壳循环；plan-guard hard block（Plan mode 下阻止 Edit/Write）；loop 计数重排
- **decisions.md 激活**（Task#32）：集成到 /drec → 三层软强制（必须/建议/可选）+ 门槛分档
- **五项 Bugfix 批量收口**（Tasks#38-42）：测试去重（conftest.py）、防御守卫（task_entry_guard）、marker 闭环（dinit uninstall）、原子写入规则（rules/session.md 提交铁律）
- **五项 Bugfix 第二批**（Tasks#43-47）：plan-guard 精确匹配（排除非 plan 文件）、uninstall 安全清理（realpath 规范化精确匹配替代前缀匹配）、dinit 类型修复、DFS 栈修复
- **SKILL.md H1 标题统一**：9 个文件统一为 dxxx 短格式，与注册名对齐
- **提交原子性铁律**：新增 rules/session.md 规则——dtask.json 状态变更必须与代码变更同一 commit
- **归档收尾**：踩坑聚合 30 条 + archive summary 更新

## [0.0.5] - 2026-04-30

### drelease.sh Worktree 隔离 + /dloop 连续循环 + drun 单任务化

- **drelease.sh 重写为 worktree 隔离模式**：临时 worktree 清理敏感文件后推 public，主工作区零触碰；修正 annotated tag 推送策略
- **/dloop 连续循环**：新增 dloop/dend command 对，实现 while(未停止){ /drun } 自动循环；stop_decision 双模式重构（normal + continuous_mode）
- **drun 纯单任务化**：从多任务调度器简化为单任务执行器——做一件事做完就停
- **stop_decision 修正**：BLOCKED 死代码清理 + README 状态机图对齐 diwu-workflow
- **dstat.md**：补全 YAML frontmatter（description/argument-hint/allowed-tools/effort）

## [0.0.4] - 2026-04-29

### Agent Taxonomy v2：核心收缩

- **领域 Agent 移除**：删除 ui-designer、frontend-architect、backend-architect、devops-architect、performance-optimizer、api-tester、legal-compliance 共 7 个领域 agent
- **核心 Agent 保留**：explorer（只读探索）、implementer（代码实施）、verifier（独立验证）成为唯一执行 primitive
- **verifier 增强**：新增 Failure Mode 和 Authority 声明，明确权限边界
- **理由**：agent 设计从角色驱动转向能力驱动，按任务节点的能力需求派发；领域方法论内容应归 skills/rules 层，而不是自动调度执行单元

## [0.0.3] - 2026-04-29

### 工作流资产初始化

- **版本号同步**：0.0.1 → 0.0.3（triple bump，跳过已废弃的 0.0.2 中间状态）
- **CLAUDE.md 同步**：更新插件版本号和索引表
- **worktree 资产**：新增 `.diwu/checks/smoke.sh`（基线环境验证脚本）、`.diwu/archive/.gitkeep`、`dsettings.json`、`dtask.json`、`decisions.md`
- **初始 session 记录**：4 个历史 session 文件归档

## [0.0.2] - 2026-04-29

### 公开仓库适配 + Checkpoint 修正

- **公开仓库地址更新**：diwu-flow-public → diwu-flow
- **/dinit 刷新**：rules + skills symlink + smoke.sh 统一初始化路径
- **Checkpoint 修正**：仅在有 InProgress 任务时创建 checkpoint 文件；文件前缀改为 `checkpoint-` 避免命名冲突

## [0.0.1] - 2026-04-29

### 新增（从 diwu-workflow v0.10.x 迁移重构）

- **多平台支持**：Skills 为底 Commands 为壳架构，支持 Claude Code / Codex CLI / OpenCode
- **10 个 Skill**：drun, dtask, dvfy, djug, dcorr, dprd, drec, darc, ddoc, ddemo
- **执行 Agent（初始 10 个，含 7 个领域专家）**：explorer, implementer, verifier + ui-designer / frontend-architect / backend-architect / devops-architect / api-tester / performance-optimizer / legal-compliance
  （注：7 个领域专家在 v0.0.4 已移除，参见该版本变更）
- **8 个 Command**：/drun, /dtask, /dinit, /dprd, /dadr, /ddoc, /ddemo, /dcorr
- **8 个 Hook 事件**：TaskCompleted, TaskCreated, PreToolUse(Bash), Stop, PreCompact, SessionStart + context_monitor + stop_archive(内联)
- **install.sh**：全平台安装脚本（claude-code / codex / opencode / all）
- **drelease.sh**：发布脚本（私有→公开仓库自动排除敏感文件）
- **dsess → drun 重命名**：合并 Session 管理与自动执行引擎为统一 Skill
- **README 迁移指引**：以 Curio 为实际示例，两步迁移（安装插件 + /dinit 刷新）
- **rules/ 目录**：顶层规则集（exceptions/templates/file-layout/constraints/judgments 等）

### Round 3 审查修复（5 commits）

#### 插件格式对齐
- **hooks.json 重写为 CC 插件官方格式**：
  - 顶层 `hooks` 包裹（原为裸事件对象）
  - `PreToolExecution` → `PreToolUse`（CC 官方事件名）
  - `${CLAUDE_PROJECT_DIR}` → `${CLAUDE_PLUGIN_ROOT}`（插件路径变量）
  - `PreCompaction` → `PreCompact`（CC 官方事件名）
- **plugin.json author**: string → object（通过 `claude plugin validate`）
- **marketplace.json**: 移除非法根级 description（通过 `claude plugin validate`）

#### Agent 字段恢复
- explorer/implementer/verifier 恢复 `memory` + `maxTurns` 字段
  - Round 2 误删（官方仅不支持 `permissionMode`，非 memory/maxTurns）
  - 测试从"验证不存在"反转为"验证存在且类型正确"

#### Stub 脚本清理
- 删除 5 个遗留/stub 脚本：stop_snapshot.py, stop_integrity.py, stop_archive_agg.py, stop_blocking.py, pre_tool_use_bash.py
- 删除 2 个关联测试：test_stop_blocking.py, test_pre_tool_use_bash.py
- L3 测试清单更新（EXPECTED_DIWU_FILES 对齐当前 hooks.json 注册表）

#### 失真引用修正
- `inject_errors_decisions.py`: rules/session.md + pitfalls.md + assets 副本（4 处）从"已实现"改为"待实现"（文件不存在）

#### 真实 Hook 运行形态修复（4 轮迭代）
- **context_monitor.py**:
  - 补全 `main()` 入口 + cache 持久化 + tool 分类计数 + warning(30)/checkpoint(60) 两级输出
  - `_classify_tool()` 从 stdin JSON 读 `tool_name`（CC PreToolUse 真实格式），回退环境变量（手动测试兼容）
  - 接入 hooks.json PreToolUse 事件（matcher: Bash）
- **stop_archive.py**:
  - 最终方案：从 hooks.json Stop 事件移除，整合进 `stop_decision.py` 内部 import 调用
  - 归档建议合并到 `decision:"block"` 的 reason 中（带 ℹ 前缀标识 advisory）
  - 无活跃任务时返回 `{}` 允许停止（纯建议不阻塞停止行为）

#### 其他修复
- README 兼容性表 OpenCode: "Custom Tools (Zod)" → "声明式索引（Plugin + Command 映射）"
- `.diwu/archive/.gitkeep`: 新增占位文件（修复 clean clone 下测试断言失败）

### 变更（从 diwu-workflow v0.10.x）

- **Rules 精简重构**（13 → 12 文件）：
  - 删除 `correction.md`（内容 100% 被 dcorr Skill 覆盖）
  - 重写 session.md / workflow.md / pitfalls.md / judgments.md / mindset.md（消除内容重叠）
  - 所有 rules 文件控制在 200 行以内
- **drun SKILL.md 增强**：执行验证循环改为显式四问框架 + 状态文件映射表
- **plugin.json agents 字段移除**：使用默认路径自动发现
- **Hooks 精简**：22 → 8 个（精选核心 + unwired 脚本接线）

### 移除

- `rules/correction.md`（→ dcorr Skill 完全覆盖）
- 5 个 stub/legacy hook 脚本（Round 3 清理）
- 2 个废弃测试文件

### 修复

- `stop_decision.py` f-string 语法错误
- `test_doc_consistency.py` 路径修正
- inject_errors_decisions.py 事实错误引用（4 处）
- CC 插件 hook 格式全面对齐（settings 格式 → 插件官方格式）
- Stop hook 输出字段合法性（自定义 key → decision/reason 顶层字段）
- clean clone 测试缺失 .diwu/archive 目录
