---
name: dtask
version: "1.0"
type: rule
description: "任务管理核心方法论——状态机、GWT 验收、task.json 结构、规划分解、实施流程、提交规范、子代理策略"
triggers:
  - "创建或管理任务"
  - "写 acceptance 验收条件"
  - "规划任务分解"
  - "判断任务状态转移"
  - "管理 blocked_by 依赖"
  - "写 commit message"
  - "用户说 任务、task、规划、分解、验收"
keywords:
  - "任务管理"
  - "状态机"
  - "GWT"
  - "acceptance"
  - "task.json"
  - "blocked_by"
  - "commit"
depends:
  - dvfy
  - djug
effort: high
argument-hint: "[功能描述] [category] [blocked_by]"
---

# dtask

任务管理核心方法论：从需求到验收的完整生命周期。

---

## 状态机

### 状态定义

| 状态 | 含义 | 修改权限 |
|------|------|----------|
| InDraft | 需求草稿中 | 主代理可改 title/description/acceptance/steps |
| InSpec | 已确认锁定 | 主代理只能改 status |
| InProgress | 实施中 | 主代理可改 status |
| InReview | 验证中 | 主代理可改 status |
| Done | 已完成 | 主代理可改 status |
| Cancelled | 已取消 | 主代理可改 status |

### 状态转移表

| 当前 | 事件 | 新状态 | 规则 |
|------|------|--------|------|
| InDraft | 人工确认 | InSpec | Agent 不可再改需求字段 |
| InDraft | 取消 | Cancelled | - |
| InSpec | 开始实施 | InProgress | - |
| InSpec | 发现问题 | (保持) | 退回 InDraft 重确认 |
| InProgress | 完成准备验证 | InReview | - |
| InProgress | 遇阻塞 | InSpec | 记录原因 |
| InProgress | 取消 | Cancelled | - |
| InReview | 通过(小幅度) | Done | 自审 |
| InReview | 通过(大幅度) | Done | 需人工确认 |
| InReview | 失败返工 | InProgress | - |
| InReview | 取消 | Cancelled | - |
| Done | (终态) | — | 忽略所有事件 |
| Cancelled | 重新激活 | InSpec | 直接锁定 |

### InReview → Done 判定锚点

| 场景 | 判定结果 | 证据等级要求 |
|------|---------|-------------|
| API/字段契约变更 | 大幅度，需人工确认 | L1-L2 运行态证据 |
| 单任务 >2000 行 | 大幅度，需人工确认 | L1-L3 自动化证据 |
| 字段默认值变化影响调用方 | 大幅度，需人工确认 | L1 调用链证据 |
| 小幅度+acceptance 全通过 | 小幅度，自审 Done | L3+ 至少一项 |

> 证据等级：L1=运行态 / L2=调用链 / L3=自动化断言 / L4=表面观察 / L5=间接推断。仅 L5 不可宣称完成。

### blocked_by 循环依赖锚点

| 依赖链类型 | 判定结果 |
|-----------|---------|
| A→B→C（无回边） | 合规 |
| A→B→C→A（有回边） | 违规，拒绝 |
| A→B 与 B→A 隐藏在不同描述 | 违规，拒绝 |

---

## Acceptance 格式（GWT）

`functional`/`ui`/`bugfix` 类**必须**用 GWT；`infra`/`refactor` 类**可选**。

格式：`"Given [前置条件] When [用户动作] Then [预期结果]"`
- 多条件/结果用"且"连接；单条"且">3 个时拆分
- `infra`/`refactor` 可用简单描述如 `"构建产物不超过 500KB"`

**Then 子句自检**：能否写成 `expect(actual).toBe(expected)`？不能则细化。

---

## task.json 结构

| 键名 | 类型 | 说明 |
|------|------|------|
| `id` | 数字 | 从 1 递增，永不复用 |
| `title` | 字符串 | 一句话描述（动词开头） |
| `description` | 字符串 | 背景+关键约束 |
| `acceptance` | 数组 | GWT 格式验收场景 |
| `steps` | 数组 | 实施步骤，绝对路径；[锁定]=技术选型，[建议]=实现细节 |
| `files_modified` | 数组 | (可选) 并行冲突检测 |
| `category` | 字符串 | functional/ui/bugfix/refactor/infra |
| `blocked_by` | 数组 | (可选) 前置任务 ID |
| `status` | 字符串 | 运行时状态 |

### 运行时真相源

- `dtask.json`：任务定义与 `status` 的真相源
- `dtask-state.json`：运行态 owner / dloop 元数据真相源
- `scripts/dtask_transition.py`：唯一允许同时修改 `dtask.json.status` 与 `dtask-state.json` 的入口

**任务分类**：

| 分类值 | 适用场景 |
|--------|---------|
| `functional` | 新增业务功能、API、核心逻辑 |
| `ui` | 页面、组件、交互、样式 |
| `bugfix` | 修复已知 bug |
| `refactor` | 不改变行为的代码结构优化 |
| `infra` | 构建、部署、配置、脚本 |

### blocked_by 规范

**语义**：前置任务未完成，当前无法开始。
**权限**：InDraft 自由；InSpec 可改需记录；InProgress 及之后不可改（需退回 InSpec）。
**何时使用**：前置任务未 Done 且当前依赖其输出时。已 Done 或仅代码调用关系时不使用。

**合法性检查**：
1. 无循环依赖（A→B→C→A）
2. 状态合理：InSpec/InProgress/InReview；InDraft 警告；Done 提示说明即可；Cancelled 拒绝

**自动清理**：
- 触发时机：Session 启动批量检查 / 任务变 Done 时立即清理引用
- 动作：移除已 Done 的 ID，session 文件记录 "Task#N 阻塞解除：Task#M 已完成"

---

## 任务规划

### 触发条件
- 用户讨论想法/需求/功能设计
- task.json 为空或用户要求分解
- 用户描述较大功能需拆分步骤

### 分解流程

**InDraft 阶段**：提炼功能点 → 拆分为可描述任务 → 定义验收条件 → 识别依赖排序 → 展示结果 → 写入 task.json（状态 InDraft）。

**InSpec 阶段**：人工确认后 Agent 改为 InSpec；此后只能修改 status 字段；需改需求则退回 InDraft。

### 任务粒度标准
代码 < 2000 行；有明确 acceptance（GWT）；有清晰 steps（绝对路径）；不依赖未完成任务或在 blocked_by 标注。

### Step 3：确定新任务 ID

写入前必须运行脚本获取最大序号（优先使用脚本，手动读取为 fallback）：

```bash
# 优先级 1（唯一可靠路径）：CC 插件环境变量
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/common.py --max-task-id --cwd <项目根目录>

# 优先级 1 失败时的诊断与降级：
#   CLAUDE_PLUGIN_ROOT 未设置 → 非 CC 插件环境或未安装
#   common.py 位于插件仓库内，非插件项目无法通过相对路径定位
#   降级策略：手动读取 dtask.json + archive/ 获取 max_id
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "${CLAUDE_PLUGIN_ROOT}/scripts/common.py" ]; then
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/common.py" --max-task-id --cwd <项目根目录>
else
  echo '[dtask] WARNING: CLAUDE_PLUGIN_ROOT 未设置或 common.py 不存在，无法自动获取 max-id' >&2
  echo '{"ok":false,"error":"需要通过 CLAUDE_PLUGIN_ROOT 访问 common.py，或手动读取 .diwu/dtask.json + archive/"}' >&2
fi
# → 输出: {"ok": true, "max_id": N, "source": "dtask.json|archive|empty"}
```

取返回的 `max_id` + 1 作为新任务起始 id（严禁 id 复用）。

> **跨平台兼容**：`${CLAUDE_PLUGIN_ROOT}` 在 CC 插件环境自动可用；Codex/OpenCode 通过 symlink 安装后路径不同；非插件项目需依赖优先级 2/3 的 fallback 链。若全部失败输出明确错误提示而非隐式 FileNotFoundError。

### task.json 写入规则
状态一律 InDraft；ID 递增不复用；category: functional/ui/bugfix/refactor/infra；追加到列表末尾；必须含 acceptance（GWT）；steps 必须自包含。

**格式化约束**：写入 dtask.json 时必须使用 `json.dump(data, f, indent=2, ensure_ascii=False)` 格式化为多行可读 JSON（禁止整行压缩）。新任务应**追加**到现有 tasks 数组末尾并重新序列化整个文件，保持缩进一致。

> **文件操作安全（R1）**：修改已有文件前先 Read 当前内容；整文件重写先 Read 完整文件；新建文件确认不存在后再 Write。
>
> **（R1）写入 dtask.json 前必须先 Read 当前完整内容**（含 tasks 数组和已有任务数据），避免覆盖或结构破坏。

---

## 任务实施

### 不确定性决策节点（实施前必过）

| 判断问题 | 可预期 | 不可预期 |
|---------|--------|---------|
| 团队做过类似？ | 做过 | 没做过 |
| 90% 把握？ | 有 | 没有 |
| 外部依赖可控？ | 可控 | 不可控 |
| 多模块集成测过？ | 测过 | 没测过 |

**全部可预期** → 直接 InProgress；**任一不可预期** → 先验证再 InProgress。

### 实施步骤
1. 通过 `python3 scripts/dtask_transition.py claim --task-id N --session-id SID --cwd <proj>` 显式完成 `InSpec -> InProgress`
2. 阅读任务描述/验收条件/实施步骤
3. 按项目既有模式实现；推荐顺序：验收测试框架 → 单元测试 → 实现
4. 文件路径修改后 grep 验证无残留
5. 逐条验证 acceptance
6. 通过 `dtask_transition.py release` 进入 `InReview/Done/InSpec/Cancelled`；小幅度自审 Done，大幅度输出 REVIEW

**大幅度修改**：API/字段变更 或 单任务 >2000 行。其余自审即可。

**自审原则**：只实现 acceptance 要求，不多不少；不引入技术债。

### 执行偏差规则

| 偏差等级 | 权限 | 例子 | 记录要求 |
|---------|------|------|---------|
| L1: Bug 修复 | 自动修复 | 类型错误/import缺失/语法错误 | session 文件 |
| L2: 关键缺失 | 自动补充 | 缺少错误处理/输入验证 | session 文件 |
| L3: 阻塞问题 | 自动修复 | 依赖缺失/配置格式错误 | session 文件 |
| L4: 架构变更 | **必须问用户** | 新建数据库表/切换框架/破坏性 API 变更 | DECISION TRACE |

单任务累计 L1-L3 ≤5 次，超则评估 acceptance/steps 缺陷。

---

## 提交规范

### 结构化 commit message 格式

```
[Task#N] 标题 - completed
Category: functional/ui/refactor/infra/bugfix
Files: src/auth.ts, src/models/user.ts
Evidence: L1-L3 (运行态+自动化)
Status: Done
```

### 并行 task 提交——子代理产出标识

```
[Task#N] 标题 - completed (并行)

## 子代理 A (auth 模块)
Files: src/auth.ts, src/middleware.ts
Evidence: L2-L3
Acceptance: [x] GWT-1 PASS [x] GWT-2 PASS

Status: InReview(超前 3/5)
```

### 提交粒度

- **粒度约束**：单 task 单提交；只交 task 相关文件
- **禁止行为**：顺手改其他文件 / 批量更新多 task / 无关格式调整

### Checkpoint 机制

大任务实施过程中记录中间进度，写入 session 文件。

**触发条件**（满足任一即触发）：
- steps 数量 > 5（默认）
- 预估修改行数 > 500（默认）

---

## 子代理策略

**并行条件**（同时满足）：问题域不相交、无共享写文件、files_modified 无重叠。
**串行条件**（满足任一）：后步依赖前步输出 / 需积累上下文。

| 要素 | 说明 |
|------|------|
| 专业化分工 | 探索类轻量级只读代理；验证类跑测试；实施类主模型写代码 |
| Worktree 隔离 | 并行实施可用 worktree 隔离 |
| Coordinator Pattern | task.json 状态由主代理维护 |
| 超前计数器 | 主代理内存维护，session 重启后统计恢复 |
| 交接清单 | acceptance PASS/FAIL 逐条 + 代码变更摘要 + 遗留阻塞点 + 下一步前置条件 |

### 派发规则（核心三件套）

| 需求 | 派发 | 说明 |
|------|------|------|
| 读代码 / 搜文件 / 架构分析 / 技术调研 | `explorer` | 只读，不改文件 |
| 改文件 / 写代码 / 跑命令 / bug 修复 | `implementer` | 唯一写入点 |
| 独立验收 / stub 检测 / acceptance 反向验证 | `verifier` | 只读，不信自述 |
| 无匹配能力 | 标记「能力缺口」 | 不在 task 内临时发明新 agent |

> 完整的 agent 设计原则与判断锚点见 `rules/mindset.md` §Agent 设计约束 和 `rules/judgments.md` §五、Agent Dispatch 判断

---

## 验证要求

**核心原则**：未验证 = 未完成。所有 acceptance 逐条验证通过后才标记 InReview。

| 验证方式 | 适用场景 |
|---------|---------|
| 自动化（推荐） | verify.sh 脚本 |
| 手动 | Agent 提供步骤清单 → 人工反馈 |
| 人工审查 | 大幅度修改 REVIEW 请求 |
| 独立验证 | 独立第三方验证 |

**失败处理**：保持 InProgress，修复后重新验证。
