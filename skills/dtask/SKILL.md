---
name: dtask
version: "1.1"
type: rule
description: "任务管理操作手册——规划分解、实施流程、max-id 脚本调用、子代理策略、Done 判定矩阵"
triggers:
  - "创建或管理任务"
  - "规划任务分解"
  - "判断任务状态转移"
  - "用户说 任务、task、规划、分解、验收"
keywords:
  - "任务管理"
  - "规划"
  - "分解"
  - "验收"
  - "子代理"
depends: []
effort: high
argument-hint: "[功能描述] [category] [blocked_by]"
---

# dtask

任务管理操作手册：从需求到验收的完整生命周期。

> **规则约束（状态机、GWT 格式、task.json 结构、blocked_by 规范、提交规范）的权威定义在 `rules/task.md`**，本文件只保留 dtask 独有的操作流程和脚本调用。

## 前置依赖：rules/ 任务约束

创建和管理任务前，以下格式规则由 hook 自动注入 system prompt（`rules/task.md`），Agent 必须遵守：

| 规则 | 权威来源 | 要点 |
|------|---------|------|
| 状态机（6 态 + 转移表 + InReview→Done 锚点） | `rules/task.md` §状态定义与转移 | InDraft→InSpec→InProgress→InReview/Done，显式迁移 |
| GWT acceptance 格式 | `rules/task.md` §acceptance 格式规范 | Given...When...Then，functional/ui/bugfix 必用 |
| task.json 结构（id/title/description/acceptance/steps/...） | `rules/task.md` §dtask 结构 | 键名、类型、含义完整定义 |
| blocked_by 规范（语义/权限/合法性检查/自动清理） | `rules/task.md` §blocked_by 规范 | 无循环依赖，Done 后自动清理引用 |
| 任务分类（functional/ui/bugfix/refactor/infra） | `rules/task.md` §任务分类 | category 取值范围 |
| 提交规范（结构化 commit message + 并行 task 标识） | `rules/task.md` §提交规范 | 5 行固定格式 |
| Checkpoint 格式 | `rules/templates.md` §Checkpoint | steps>5 或行数>500 时触发 |

---

## 运行时真相源

- `dtask.json`：任务定义与 `status` 的真相源
- `dtask-state.json`：运行态 owner / dloop 元数据真相源
- `scripts/dtask_transition.py`：唯一允许同时修改 `dtask.json.status` 与 `dtask-state.json` 的入口

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
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "${CLAUDE_PLUGIN_ROOT}/scripts/common.py" ]; then
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/common.py" --max-task-id --cwd <项目根目录>
else
  echo '[dtask] WARNING: CLAUDE_PLUGIN_ROOT 未设置或 common.py 不存在，无法自动获取 max-id' >&2
  echo '{"ok":false,"error":"需要通过 CLAUDE_PLUGIN_ROOT 访问 common.py，或手动读取 .diwu/dtask.json + archive/"}' >&2
fi
```

取返回的 `max_id` + 1 作为新任务起始 id（严禁 id 复用）。

> **跨平台兼容**：`${CLAUDE_PLUGIN_ROOT}` 在 CC 插件环境自动可用；Codex/OpenCode 通过 symlink 安装后路径不同；非插件项目需依赖 fallback 链。若全部失败输出明确错误提示而非隐式 FileNotFoundError。

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

## Done 判定矩阵

> 原 dvfy §Done 判定规则，现归 dtask 管辖。证据等级定义见 `rules/verification.md` §L1-L5。未验证 = 未完成。

### 证据等级组合判定

| 证据等级组合 | 判定动作 | 标注要求 |
|-------------|---------|---------|
| 全部 L1-3 通过 | Agent 自审 + verifier 终验后 Done | session 文件逐条标注 PASS + 验证方法 |
| L1-3 部分 + L4 补充 | Agent 自审后 Done | L4 项标注「待人工确认」+ 后续验证方式 |
| 仅 L4 或 L4-5 | **不允许 Done** | 标注 InReview + 「待验证」+ 原因 + 后续方式 |
| 仅 L5 | **禁止宣称完成** | 保持 InProgress，补充真实验证 |

### 与验证方式的映射

详见 `rules/verification.md` §运行态验证方法指引（L1 运行态 / L2 调用链 / L3 自动化断言 / L4 表面观察 / L5 间接推断）。默认 L1-3 主判，L4-5 辅助。仅 L5 不可宣称完成。

**失败处理**：保持 InProgress，修复后重新验证。
