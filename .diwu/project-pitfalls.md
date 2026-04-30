# 项目踩坑聚合表

> 按 Layer 2 类别标签聚类。来源列写具体 session 文件名。
> 最后更新：2026-05-01 00:50

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
