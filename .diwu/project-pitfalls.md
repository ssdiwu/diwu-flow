# 项目踩坑聚合表

> 按 Layer 2 类别标签聚类。来源列写具体 session 文件名。
> 最后更新：2026-05-04 02:04（Session 归档 #13 个 session）

## 环境漂移

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 发版时切 release 分支导致 .diwu/ 从工作区消失 | release 分支不含 .diwu/ 的 commit，误判为需 .gitignore 排除 | worktree 隔离模式：临时副本清理敏感文件，主工作区零触碰 | session-2026-04-29-231715.md |
| /dstat 输出「2 小时前」实际仅 41 分钟 | 数据源表缺少 date 命令导致执行者只能脑补 | 强制数据源覆盖所有输出字段所需输入 | session-2026-04-30-001113.md |
| stop_decision.py 缩进 bug 多轮 Edit 无法匹配 | Write 重写后中文注释含特殊字符/缩进，误判为 Edit string matching 问题 | 直接用 Write 重写整文件（含缩进修复），再用 sed 修单个 emoji | session-2026-04-30-235640.md |

## 读层现象

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 初始方案将 Agents 改为知识文件放入 skills-domain/ | Agent 设定文件和 Skill 知识文件是不同层次 | Agent 保持 .md 设定文件格式不变，不混入 skills/ | session-2026-04-27-235327.md |
| 测试 RULES_DIR 指向 .claude/rules/ 但 diwu-flow 的 rules 在项目根目录 | 迁移遗留路径差异，误判为新引入的测试失败 | 修正测试常量，先确认实际目录布局 | session-2026-04-28-132536.md |
| 归档 Session 计数 3 vs 实际 7 | 数据源描述「取最新 1-2 个」被理解为全部读取范围 | 同一数据源的不同用途（展示 vs 统计）必须拆分为独立条目 | session-2026-04-30-001113.md |
| stop_decision.py 注释描述 BLOCKED 为独立停止条件，代码实际无此分支 | 注释/文档误导导致理解偏差 | 以代码行为为准，文档必须与代码逻辑严格对齐 | session-2026-04-30-021120.md |
| 旧 test_inspec_auto_advances 断言需要从 True 改为 False | 新设计下默认模式不续跑，旧测试是行为迁移而非 bug fix | 改完核心逻辑后同步迁移受影响的测试断言 | session-2026-04-30-012359.md |
| decide_default_mode 中引用了 cwd 变量但函数签名没有此参数 | NameError 导致 5 个测试失败 | 改完函数内部变量依赖后立即跑定向测试，不等到全量回归 | session-2026-04-30-224210.md |
| 先前 commit/recording 已写 completed，但 dtask 验收里仍有未落地项 | 把历史结论当成现场真值 | 收尾前回到当前 dtask.acceptance 和工作树逐条对照 | session-2026-04-30-233841.md |

## 分层未拆清

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 计划阶段多次引用 "Crush" 而非 "OpenCode" | 未核对目标平台名称 | 计划确认前仔细核对目标平台名称 | session-2026-04-27-235327.md |
| 「有 plan 就直接干」跳过 /dtask | plan mode 输出视觉上等价于 dtask，但本质是架构方案不是执行契约 | 拆出双守卫 hook（ExitPlanMode 提示 + Edit/Write 入口守卫） | session-2026-04-29-183637.md |
| task_entry_guard 阻断 Plan mode 写计划文件 → dtask.json 为空时死锁 | workflow 白名单未包含 Plan mode 路径 | 白名单应包含 Plan mode 路径，且逻辑需显式注释 | session-2026-04-30-001113.md |
| notify() 中 open('/dev/tty') 在测试环境无 TTY 时抛 OSError | 所有外部交互（OS 通知/TTY/子进程）未 try/except 包裹 | 测试环境不能假设任何 OS 设施存在，外部交互必须 try/except | session-2026-04-30-012359.md |
| start 语义「清理+继续」与 status「清理+告知」混淆 | stale 检测提前返回 stale_cleaned，未继续启动 | start 的 stale 检测是清理后继续启动（不提前返回） | session-2026-04-30-190038.md |
| 抽共享 stop helper 时漏了继续分支依赖的 nx/rev 局部变量 | stop 判定层和 continue 选任务层没有一起重构 | 抽公共判定时必须同时盘点调用方在非终止路径上还依赖哪些局部状态 | session-2026-04-30-194500.md |
| Edit 工具多行中文匹配反复失败（5 次） | 文件可能有不可见编码差异（BOM/零宽字符） | 该文件用 Python 脚本做精确字节级替换；单行 Edit 可用但多行中文块不稳定 | session-2026-04-30-224210.md |
| 误以为 allow_stop 输出到 stderr 实际是 stdout | 分支1 用 print(...) 而非 print(..., file=sys.stderr) | 阅读代码确认输出流，测试断言对齐实际行为 | session-2026-04-30-235640.md |

## 路由护栏契约

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| plugin.json 声明 agents 字段触发 Invalid input | v0.10.x 已踩过的坑 | diwu-flow 必须不声明 agents 字段，使用默认路径自动发现 | session-2026-04-27-235327.md |
| Edit 工具要求先 Read 才能编辑同一文件 | 遗忘此约束导致编辑被拒绝 | 编辑前先确认已 Read | session-2026-04-28-132536.md |
| Stop hook 只支持 decision/reason/continue/stopReason | 任何自定义 key（如 hookSpecificOutput）都会被忽略 | Stop 下归档建议只能通过 reason 字段传递 | session-2026-04-29-013953.md |
| 遇到可查证的事实性问题时先 AskUserQuestion | 用户反馈「应该自己查而不是问」 | 可查证的问题应先用工具获取再给方案 | session-2026-04-30-001524.md |
| decide() 函数签名变更时旧测试未同步更新 | 新增 cwd + loop_state 参数导致 6 个 TypeError | 修改核心函数签名后必须 grep 所有调用点并逐一适配 | session-2026-04-30-012359.md |
| public/main force push 被拒绝 | 每次发版都是独立 clean commit，非线性历史 | force push 是正常发版流程的一部分，非异常操作 | session-2026-04-30-022201.md |
| PreToolUse hook stdin JSON 字段与环境变量混淆 | 环境变量方式只在手动测试时生效 | hooks 通过 stdin JSON 传 tool_name/tool_input/session_id | session-2026-04-29-005143.md |

## 验证误读

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 上下文压缩后凭 summary 声称全部完成但实际有 3 处口径残留 | 仅靠测试通过不能证明文档一致性 | 补充 grep 残留扫描作为额外验证步骤 | session-2026-04-29-183637.md |
| task_entry_guard 阻断 Write 工具写入 drelease.sh | dtask.json 无活跃任务 → 误判为需先创建任务 | 基础设施修复（非业务实施）通过 Bash 路径绕过是已知缺口 | session-2026-04-29-231715.md |
| classify() 条件 2 无可执行任务开始生效但旧测试未提供 dtask.json | 旧测试缺少前置数据 | 为所有 active=true 的测试补充 dtask.json 含可执行任务 | session-2026-04-30-190038.md |
| 测试入口没注入 DIWU_SILENT 环境变量，以为修了静默仍然弹窗 | 误判为运行时开关失效，实际是测试 harness 没接上 | 「测试期行为开关」必须同时落 runtime 和测试入口两层 | session-2026-04-30-194500.md |
| README 清单漏了 dloop，skill 数量 11 vs 实际 12 | 把文档口径当成现场真值 | 涉及计数/资产数量时先用文件系统或命令校验再回写文档 | session-2026-04-30-221947.md |
| 测试数据缺 started_at 字段导致 sync_runtime_state 返回 invalid | dloop schema 校验 started_at 必须非空 | 测试构造数据必须完整符合 schema（含 started_at/stopped_at/stop_reason） | session-2026-04-30-235640.md |

## 数据缺口

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 历史遗留 Task#15/Task#23 未落地 dtask.json | 「有 plan 就直接干」跳过 /dtask | 通过 Plan→Dtask 双守卫在流程层面封堵 | session-2026-04-29-231715.md |
| task_entry_guard 扫描真实 home 下 ~/.claude/plans，其他项目残留 plan 也阻断当前项目测试 | 把「用户全局态」当成「当前项目上下文」 | 所有 guard 类逻辑都要先有当前项目 marker/provenance，再读取全局目录 | session-2026-04-30-233841.md |

## 其他

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 文件命名约定混淆 | 插件内自定义内容以 d 开头 | drelease.sh 非 release.sh，统一 d 前缀 | session-2026-04-27-235327.md |
| 同一账号下不能同时存在 private/public 同名仓库 | GitHub 限制 | 私有仓库改名（diwu-flow-dev），公开仓库用原名 | session-2026-04-29-013953.md |
| shell for 循环变量展开错误导致多个 skill 名被拼成一个长文件名 | SKILLS 变量包含空格分隔的多个 skill 名未被正确 word-split | 确保循环变量赋值和展开均无空格干扰，或用 while IFS= read -r | session-2026-04-30-213630.md |
| smoke.sh 中变量直接写成 $SKILL_COUNT）被全角标点污染 | set -u + 全角标点上下文里触发坏变量名 | shell 输出里统一使用 ${VAR} 包裹变量，避免与中文/全角标点相邻 | session-2026-04-30-221947.md |
| 按旧 Task 实施时 Task 边界不清晰 | Task#28 里混着已验过的 finding 和新迁移工作 | 先把 dtask 任务边界收口到可执行状态再实现，避免计划层与实现层互相污染 | session-2026-04-30-221947.md |

---

## 归档批次：2026-05-02（Task #33-#57，25 个任务）

### 环境漂移（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| drelease.sh 验证在真实 origin/public 上跑污染 remote | 未隔离测试环境 | drelease.sh 验证必须在临时 clone + bare remotes 中隔离执行 | session-2026-05-01-195628.md |
| 测试残留 /tmp/.claude_main_session 文件导致 release 时 owner_mismatch | tearDown 写错路径（双 main 拼写）且清理不完整 | 测试 tearDown 应清理完整路径，含所有可能的临时文件变体 | session-2026-05-01-135130.md |
| drelease.sh worktree 内 cd 导致相对路径 public remote 失效 | 验证时未用绝对路径配置 remote | 验证时必须用绝对路径配置 remote 或在 ORIGINAL_DIR 下操作 | session-2026-05-01-182642.md |

### 读层现象（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| Agent Explore 子 API 报错（MiniMax M2.7 invalid params） | 大型信息收集任务完全依赖子 agent | 核心数据源应直接 Read/Glob/Grep，不应完全依赖子 agent | session-2026-05-01-195640.md |
| awk 计数 Skills 表格显示 11 而非 12 | awk 范式匹配边界误差 | 多种计数方式交叉验证更可靠 | session-2026-05-01-195640.md |
| scan-repo 的 file_count bug 在批量修复期间已被顺带修复但缺少回归测试 | 顺带修复未被显式验证锁定 | 补充回归测试锁定行为，防止未来回退 | session-2026-05-01-235505.md |
| SKILL.md H1 标题用 diwu-xxx 但文件夹/frontmatter 用 dxxx | 命名空间不一致 | 统一为与注册名一致的短格式 | session-2026-05-01-035028.md |
| dtask_state.py ACTIVE_TASK_STATUSES 含拼写错误 InProcess | 代码缺陷未被早期发现 | 定期 grep 六态定义常量与实际使用是否一致 | session-2026-04-30-221947.md |

### 分层未拆清（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| Task#57 marker 设计未分析 guard 执行链顺序就实现 | 代码写在 _is_workflow_file() exit(0) 之后，永远不可达 | 先画完整执行链路图确认插入点可达性再编码 | session-2026-05-02 00:11:35 |
| 5 轮迭代修一个 guard 函数 | 每轮只解决上一轮回归，未穷举输入空间真值表 | 设计阶段先穷举 (状态×输入) 组合 → 标注期望行为 → 一次性实现 | session-2026-05-01-204342.md, session-2026-05-01-215721.md, session-2026-05-01-220204.md |
| Task#44 发现两层 bug 叠加：表面问题修了但深层问题仍在 | 只追踪代码位置未追踪完整数据流 | 复现时必须追踪完整数据流而非仅看代码位置 | session-2026-05-01-034711.md |
| 操作纪律不落地 = 下次必犯（dloop active=true 被 commit） | 仅靠"记住"不可靠 | 必须同时写 SKILL.md 检查清单 + 代码安全网双重兜底 | session-2026-05-01-195628.md |
| Task#41 和 #42 共享 dtask_transition.py 并行 agent 冲突 | 共享文件的任务并行会冲突 | 共享文件的任务必须串行或合并为一个 agent 执行 | session-2026-05-01-032552.md |
| Fix#1 阈值判定作用域错误——判断"目录下有没有大文件"而非"这个 plan 是否够大" | 变量命名不精确反映语义（plan_lines vs max_lines） | 变量命名要精确反映语义和判定域 | session-2026-05-01-040416.md |
| 上轮修复只解决可达性没考虑语义正确性 | 两步问题拆成两次修，设计阶段未列全输入组合 | 设计阶段就列出所有输入组合的真值表 | session-2026-05-01-202846.md |
| 三次修复都指向同一模式：过宽的匹配范围 | 全局扫表/子串匹配/无契约字段回退 | 每次修复后必须验证"不匹配边界"而非仅验证"匹配边界" | session-2026-05-01-040416.md |
| Task#41 acceptance 含糊（三种可能修复方向未锁定） | 审查阶段未要求决策者明确选择就落 InDraft | 审查阶段应要求明确决策方向再落 InDraft | session-2026-05-01-032552.md |
| drec 写入时追加到已有 session 文件而非新建独立文件 | 违反每次 session 必须新建独立文件的规则 | 每次必须新建独立文件，文件名由当前时间戳决定 | session-2026-05-01-195640.md |

### 路由护栏契约（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| baa064d 误清 dtask.json 的 22 条 Done 任务 | 普通 session 直接覆盖 status 真相源，违反只有 /drec 能归档的规则 | 补 guard 检测（任务数大幅缩减时 exit(2)）+ /drec 归档前 marker 放行 | session-2026-05-01-234739.md, session-2026-05-01-235505.md |
| Guard 检查顺序即优先级：精确拦截被宽泛放行覆盖 | _has_active_task（宽泛放行）在 dloop guard（精确拦截）之前 | fail-fast guard 必须放在宽泛放行条件之前 | session-2026-05-01-201911.md |
| 安全守卫判别维度只有"是否活跃"没有"谁在操作" | active=true 是状态标记不是权限标记 | Guard 判别维度不能只有状态必须有 caller 身份 | session-2026-05-01-202846.md |
| Hook 阻止机制用错退出码：exit(1) 非 exit(2) | PreToolUse exit(1)=non-blocking, exit(2)=deny, exit(0)=allow | 改 hook 前必须先确认平台文档的退出码语义 | session-2026-05-01-205841.md, session-2026-05-01-215721.md, session-2026-05-01-220204.md |
| dummy 窗口 foreign session 放行的 tradeoff 未正式落盘 | 藏在代码注释/测试 docstring 里 | 已知 tradeoff 必须写进 SKILL.md 并用测试锁定行为 | session-2026-05-01-215721.md, session-2026-05-01-220204.md |
| dloop 有三阶段生命周期但 guard 假设单一 active 状态 | stop_decision.py 延迟绑定架构产生 dummy→real 过渡 | guard 必须分别处理三阶段而非假设单一状态 | session-2026-05-01-204342.md |
| Task#43 plan 文件信号来源在 hook contract 中未定义 | event 无标准字段携带 plan 路径 | 实现时需定义回退策略不能假设信号存在 | session-2026-05-01-034711.md |

### 验证误读（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 脚本级 returncode 断言 ≠ hook 运行时行为验证 | pytest 只证明脚本返回了什么码不证明 CC 是否真的拦截 | 测试断言必须与平台文档的退出码语义对齐 | session-2026-05-01-205841.md, session-2026-05-01-215721.md, session-2026-05-01-220204.md |
| _run() 返回值从 (rc,out) 改为 (rc,out,err) 后部分调用点未同步解包 | 只改了部分调用点导致 ValueError | 改函数签名后必须 grep 所有调用点统一修改再跑测试 | session-2026-05-01-135130.md |
| Bug 2 调整优先级后只改现有用例断言没锁住新行为回归 | 调整优先级后需新增"两者同时存在时的优先权"独立用例 | 行为变更必须新增独立用例锁住新语义 | session-2026-05-01-182642.md, session-2026-05-01-195628.md |
| Task#45 acceptance 初版要求"目录为空"与"保留无关 symlink"矛盾 | destructive 行为更容易满足 acceptance 但恰恰是要防止的 | acceptance 必须显式排除 destructive 路径 | session-2026-05-01-034711.md |
| 手动验证脚本路径用相对路径导致 FileNotFoundError | 未先用绝对路径排除环境问题 | 应先用绝对路径排除环境问题再断言业务逻辑 | session-2026-05-01-201911.md |
| Edit 工具上下文压缩后 "String to replace not found" 反复失败 | 依赖压缩后的缓存而非当前精确内容 | Edit 前必须 Read 获取当前精确内容，不能依赖上下文缓存 | session-2026-05-02 00:11:35 |

### 数据缺口（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| v0.0.3 tag 指向孤立 clean commit 从未推送到 public | 早期 drelease.sh worktree 产物生成了 clean commit 但未推送 public | 发版后必须 git ls-remote --tags public 独立验证，不信任 origin 状态 | session-2026-05-01-043916.md |
| drelease.sh 原 Step 3 只推当前版本 tag 不处理历史遗留 | public tag 可能指向 origin commit（含敏感文件历史） | public tag 必须指向 clean commit 且每次发版顺带同步缺失历史 tags | session-2026-05-01-043916.md |
| dtask SKILL.md 缺少 Step 3 命令模板导致非 CC 平台找不到 common.py | Skill 和 Command 中关键命令模板不同步 | 应在 Skill（跨平台底层）和 Command（CC 专属）中同步维护关键命令模板 | session-2026-05-01-234739.md |

---

## 归档批次：2026-05-04（Session #58-#76，19 个任务，13 个 session）

### 环境漂移（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| macOS `sed -i ''` 对含点号数字（如 `0.1.0`）替换不生效 | BSD sed 转义行为与 GNU sed 差异 | 涉及版本号/含点字符串替换统一用 Python `str.replace()` | session-2026-05-03-172515.md, session-2026-05-03-180459.md |
| CC `/plugin` 报 "not found" | 先查远程 marketplace 未查本地 installed_plugins.json | 插件加载问题先查本地注册表再查远程源 | session-2026-05-03-180459.md |

### 读层现象（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| Task#64 symlink 只修检测不修根因（broken symlink） | 发现 broken artifact 后未追问「为什么第一次就建错了」→ expected_target 硬编码相对路径是根因 | 发现 broken artifact 必须追查首次创建逻辑，不能只补检测 | session-2026-05-03-002855.md, session-2026-05-03-004525.md |
| PLUGIN_ROOT 是仓库路径但 CC 从 marketplace 加载 skill | dinit.py 写死唯一源路径，未考虑 CC 插件安装后的实际目录结构（marketplace vs marketplaces 拼写差异 + 多候选路径） | 涉及「CC 从哪加载」的问题必须验证实际加载路径，不能假设仓库路径即运行时路径 | session-2026-05-03-021204.md |
| validate_skills_src typo 导致 NameError 崩溃但 pytest 未覆盖此路径 | 重构后变量名拼写错误，类型检查器不捕获，单元测试未覆盖真实 CLI 调用链 | 重命名/重构后必须跑一次真实 CLI 调用链验证（不只是单元测试） | session-2026-05-03-100308.md |

### 分层未拆清（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| Stop hook 阻止 dloop 继续——release 与 Stop hook 时序竞争导致 iteration 未递增 | dloop 的 iteration 递增依赖 Stop hook 执行，与 task_completed.py 异步追踪存在时间窗口 | dloop 运行时状态写入/读取必须通过 dtask-state.json 统一入口，避免多 hook 竞态 | session-2026-05-03-001428.md, session-2026-05-03-002855.md |
| dloop state 写入端(dloop.py)与读取端(stop_decision.py)分离，读取端可能读到过期数据 | stop_decision.py 读内存缓存而非磁盘最新值 | 读取 runtime state 前必须 sync_runtime_state() 强制 reload 或用 dtask.json Done 列表 fallback | session-2026-05-03-100308.md |
| task_entry_guard 在 dloop 活跃时拦截非 owner session 的 Edit/Write | guard 仅判别「是否有活跃任务」未判别「谁在操作」 | Guard 判别维度必须有 caller 身份，不能只有状态标记 | session-2026-05-03-170432.md |
| Task#71 acceptance 写 0.0.10 但实施时直接升到 0.1.0 | acceptance 是验收契约不是建议，实施前未对齐 | 版本号等契约字段在实施前必须先确认 acceptance 与目标一致 | session-2026-05-03-172515.md |

### 路由护栏契约（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| ExitPlanMode hook contract 变更：tool_input.file_path 为空，实际传 tool_input.plan | plan_exit_hint.py 用旧 contract（file_path）判断 plan 路径 → marker 永远创建不了 → task_entry_guard hard block 静默失效 | Hook 开发必须验证 CC 实际传入的字段名，不能用假设的 contract | session-2026-05-03-162925.md, session-2026-05-03-173333.md |
| task_entry_guard 拦截 Edit/Write 导致 dloop 非 owner session 无法写文件 | guard 仅拦截 Edit\|Write 主写入路径，Bash 路径不拦截 | 已知缺口：基础设施修复可通过 Bash 路径绕过 guard；长期应增加白名单或身份识别 | session-2026-05-03-170432.md |
| Plan→Dtask 门控双守卫：ExitPlanMode 强提示 + Edit/Write 入口守卫 | 原 plan mode 输出视觉上等价于 dtask 但本质是架构方案不是执行契约 | 双守卫分层：退出 plan 时强提示进入 /dtask；进入 Edit/Write 写阶段时实施入口守卫 | session-2026-05-03-162925.md |

### 验证误读（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| 引入 4 个 bug 的 PR 本身成为踩坑来源 | 功能验证只覆盖 happy path（插件仓库自身），未覆盖用户项目场景（tmp_dir 跨目录、默认模式无 dloop、有历史 Done 任务） | 修改涉及路径计算或全局状态读写时，必须在边界场景（跨盘/空值/预填充数据）下验证 | session-2026-05-03-004525.md |

### 数据缺口（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| dtask.json 中 Task#72-74 已标记 Done 但状态仍为 InDraft | release 脚本只更新 pending_recording 标记未同步 dtask.json.status | release 后立即校验 dtask.json.status 与目标一致，dtask_transition.py 应原子更新两文件 | session-2026-05-04-020408.md |
| dtask_transition API 参数命名不统一：claim 用 --task-id（单数），mark-inspec 用 --task-ids（复数），release 用 --task-id + --to | 三个子命令独立设计未统一命名规范 | API 设计时先定义统一命名约定（单数/复数/动词一致性），再实现各子命令 | session-2026-05-04-012526.md |
| context 截断后 session ID 变化导致 owner mismatch | dtask-state.json.task_sessions 中旧 session ID 与新 session 不匹配 | context 截断恢复后需先 adopt（重新认领任务）再 release，不能直接操作旧 owner 任务 | session-2026-05-04-012526.md |

### 其他（新增）

| 现象 | 根因 | 正确做法 | 来源 |
|------|------|---------|------|
| dtask.json 在 context 截断后损坏（Task#71 后出现重复数据） | 截断恢复时 JSON 写入追加而非覆盖 | context 截断后恢复 dtask.json 前先用 head 截断到合法 JSON + json.load 验证完整性 | session-2026-05-04-012047.md |
| 清理内置 TaskCreate 追踪器时误删了 dtask.json 中 Task#72-74 | 把「清理 TaskList 缓存」和「清理 dtask.json 任务」混为一谈 | TaskList 是 CC 内置追踪器（可安全清理），dtask.json 是项目真相源（不可随意删除条目） | session-2026-05-04-012047.md |
