# Changelog

All notable changes to diwu-flow will be documented in this file.

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

## [0.0.4] - 2026-04-29

### Agent Taxonomy v2：核心收缩

- **领域 Agent 移除**：删除 ui-designer、frontend-architect、backend-architect、devops-architect、performance-optimizer、api-tester、legal-compliance 共 7 个领域 agent
- **核心 Agent 保留**：explorer（只读探索）、implementer（代码实施）、verifier（独立验证）成为唯一执行 primitive
- **verifier 增强**：新增 Failure Mode 和 Authority 声明，明确权限边界
- **理由**：agent 设计从角色驱动转向能力驱动，按任务节点的能力需求派发；领域方法论内容应归 skills/rules 层，而不是自动调度执行单元

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
