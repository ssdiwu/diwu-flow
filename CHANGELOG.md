# Changelog

All notable changes to diwu-flow will be documented in this file.

## [0.0.6] - 2026-05-03

### 新增

- **dref Skill**：需求细化清单方法论。通过 5 阶段工作流（吸收分析→洞察提问→收尾→输出清单→智能拆分保存），帮助用户将模糊想法转化为可执行的检查清单，保存到 `docs/Optimization requirements/`。支持领域感知（前端/后端/性能/UX/DevOps）和自适应行为。

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
