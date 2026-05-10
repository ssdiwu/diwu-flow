---
name: drun
version: "1.0"
description: "当需要启动 Session 执行任务、恢复上下文、选择下一任务或结束当前 Session 时使用"
depends:
  - dtask
  - dcorr
  - drec
effort: high
argument-hint: "[功能描述] [category] [blocked_by]"
---

## 不可协商规则

- Session 启动必须按 Preflight→上下文恢复→归档检查→任务选择顺序串行执行，Preflight 失败则停止
- 任务状态变更必须通过 `dtask_transition.py` claim/release 显式完成，禁止直接手改 dtask.json.status
- closeout 顺序铁律：整理摘要 → decisions → verifier → release → /drec，不可跳序
- drun 是单任务执行器，执行完毕后停止；批量连续执行必须使用 `/dloop`
- stop hook 注入 InSpec 任务信息时必须暂停等待用户明确指示，禁止假设沉默=授权而自动执行

# drun

Session 生命周期管理：从启动到结束的完整协议，含执行验证循环。单任务执行器——做一件事，做完就停。

---

## Session 启动（必须按顺序执行）

**执行顺序约束**：Step 1-4 串行（Preflight 失败则停止）；Step 5 可选；Step 2/3 的 task.json 读取可合并。

### 1. Preflight 检查

**基线验证**：运行 smoke.sh（如存在），验证基线环境。

**三唯一确认**：
- 唯一主线目录：本轮任务唯一允许承接主要实现和验收的目录
- 唯一运行入口：本轮要验证主链是否真的经过的实际启动/调用入口
- 唯一 canonical：当前必须以其为准的说明、接口或规则文件

**5 问开工检查**：
1. 这件事能不能直接做，还是先探索/先验证/先写最小规格？
2. 本次唯一主线目录、唯一运行入口、唯一 canonical 是什么？
3. 当前最可能先判断错的地方是什么？
4. 进入实施前最少要拿到哪些判别依据？
5. 完成后用哪类高等级证据判断结果成立？

**误判表预加载**：project-pitfalls.md 已由 SessionStart hook 自动注入到上下文（见 `## 项目历史踩坑经验` 段落），执行时直接对照检查即可，无需再手动读取；exceptions.md 仍需按需读取。

**其他检查**：git status 确认工作区状态；recording/ 最新 session 中是否有未解决阻塞记录。

### 2. 上下文恢复
- **优先**读取 continue-here.md（如存在），读完后删除
- 否则读取最新 1-2 个 session 文件
- 读取 decisions.md（如存在）
- 运行 git log --oneline -20

### 3. 归档检查
- 统计 task.json 中 Done/Cancelled 任务数量
- 超过阈值（默认 20）时触发归档
- 更新 task.json 只保留活跃任务

### 4. 任务选择策略
- **优先恢复** 当前 session 在 `.diwu/dtask-state.json.task_sessions` 中 owner 匹配的 InProgress 任务
- 否则选第一个 InSpec 任务，检查 blocked_by：
  - 为空/不存在 / 全部 Done → 可开始
  - 存在 InReview 且超前未达上限 → 可超前（标记 InReview + 立即 commit）
  - 达到超前上限 → 输出 PENDING REVIEW
- **禁止**选择 InDraft 任务
- 进入实施前必须先通过 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py claim --task-id N --cwd <proj>` 显式完成 `InSpec -> InProgress`（`--session-id` 默认 `auto`，按优先级自动解析：session 文件 → 环境变量 → drun-<timestamp> fallback）
- 实施完成后的最终状态也必须通过 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py release --task-id N --to inreview|done|inspec|cancelled --cwd <proj>` 显式完成；不得手改 `dtask.json.status`（`--session-id` 同样默认 `auto`）

### 5. 环境初始化（可选）
- 运行 init.sh（如存在）
- 运行基线测试（build/lint），失败则先修复

---

## Session 结束

在 session 结束前（含 context window 接近上限时）：

### 完成前四问（标 InReview/Done 前必答）

| # | 问题 | 回答格式 |
|---|------|---------|
| 1 | 验证的是哪一层？ | 文档 / 代码 / 配置 / 调用链 / 运行态 / 输出 |
| 2 | 是否真的走到了新链路？ | 是/否 + 证据（日志/断点/请求追踪） |
| 3 | 结果是否出现可识别变化？ | 变化描述 + 变化前后对比 |
| 4 | 哪些部分已验证，哪些未验证？ | 已验证清单 + 未验证清单 |

1. 整理 session 内容摘要（处理了哪些任务、实施内容、验收验证结果、下一步计划）
2. 如有重大设计决策，追加到 decisions.md
3. **verifier 终验**（S1/S2 路径标 Done 前必须执行；S3/S4 已调过 verifier 则跳过；infra/refactor 简单度量可跳过）

#### Verifier 终验规则

| 维度 | 规则 |
|------|------|
| **触发条件** | S1/S2 路径（主代理自审 / explorer→implementer）标 Done 前 |
| **跳过条件** | S3/S4 路径已调用 verifier 终验；或 category 为 infra/refactor 且改动为纯度量调整 |
| **输入** | acceptance 条目列表 + implementer 交接报告中的文件列表（非 git diff --stat） |
| **输出** | `PASSED`（全部通过→release Done）/ `GAPS_FOUND`（有缺口→保持 InProgress 修复）/ `HUMAN_NEEDED`（需人工判断→release InReview） |
| **三分支** | PASSED → Step 4 release Done；GAPS_FOUND → 返回实施修复缺口后重新验证；HUMAN_NEEDED → Step 4 release InReview |

> 输出状态与 `agents/verifier.md` 第 38 行定义一致。

4. **release**：用 `dtask_transition.py release` 将任务显式切到 `Done` 或 `InReview`
5. **调用 `/drec` 完成 recording 写入与原子 commit**（详见 drec §原子 Commit 职责 §调用契约），由 drec 统一负责：写入文件 → git add -A 全量变更 → git commit

> **pending_recording 兜底**：`release` 命令会自动在 `dtask-state.json` 写入 `pending_recording` 标记。若忘记调 `/drec`，Stop Hook 会检测到此标记并强制拦截，要求先执行 `/drec` 清除标记后才允许继续。详见 stop_decision §pending_recording 门控。

> **dtask-state.json 状态一致性检查（commit 前必做）**：
> 在调用 `/drec` 前，必须 Read `.diwu/dtask-state.json` 确认磁盘内容与预期一致：
> - **非 dloop 模式**：`task_sessions` 中当前任务的 owner 记录应已由 `release` 清理
> - **dloop 模式（最后一轮）**：`stop_decision.py` 已通过 `clear_loop_state()` + `save_runtime_state()` 清理 dloop；后续 `sync_runtime_state()` 或 `dtask_transition.py release` 可能再次覆写该文件——**最终磁盘文件应为干净状态 `{version, task_sessions}`（不含 `dloop`/`pending_recording` key），若仍含 `dloop: null` 等冗余字段说明最后一次覆写未执行或失败**
> - 若发现 `dloop.active=true` 残留则绝对禁止 commit

> **（R1）**：写入 session 文件前必须 Read 当前 session 文件尾部，确认追加位置正确。

> **closeout 顺序铁律**：整理摘要 → decisions → verifier → release → /drec。不可跳序，不可省略 verifier（除非命中跳过条件）。

> **详细 recording 格式和踩坑记录格式见 drec skill**

### Context Window 管理
- context window 接近上限时会自动压缩，允许无限期继续工作
- 不要因 token 预算担忧而提前停止任务
- 始终保持最大程度的自主性

---

## 执行验证循环

每轮执行前必须明确回答：

| # | 问题 | 回答来源 |
|---|------|---------|
| 1 | 当前任务是什么？ | dtask 当前 InProgress 任务的 `title` + `description` |
| 2 | 这轮准备怎么做？ | steps 中当前步骤的绝对路径和具体操作 |
| 3 | 怎么判断这轮做成了？ | 对应 `acceptance` 条目 + 证据等级（L1-L3 主判，见 dtask §Done 判定矩阵） |
| 4 | 结果更新到哪？ | dtask.json（状态变更）+ recording/session（进度记录） |

> **（R1+R2）**：更新 dtask.json status 前 **Read 当前 status 值**；写入 JSON 必须 **indent=2, ensure_ascii=False**。

> **状态流转约束**：`/drun` 的任务状态必须按 `InSpec -> InProgress -> InReview/Done/...` 顺序推进。开始执行用 `dtask_transition.py claim`，收尾判定用 `dtask_transition.py release`；不要直接手改 `status` 跳步完成。

> 状态文件映射（复用现有机制，不新建文件）：
> - 目标+边界 → dtask.json `description` + `acceptance[]`
> - 拆解+状态 → dtask.json `tasks[]` + `status`
> - 运行态 owner / loop → `.diwu/dtask-state.json`
> - 每轮进度 → recording/session Checkpoint（格式见 `rules/templates.md`）
> - 验收标准 → dtask.json `acceptance[]`
> - 验证脚本 → `.diwu/checks/smoke.sh`

**调用顺序**：dtask(实施/验证) → dcorr(纠偏)

执行完毕后停止，输出完成摘要。如需连续执行多个任务，使用 `/dloop`。

---

## 运行态验证方法

代码层验证（lint/build/测试）通过后，还需确认运行时真的走到新链路：

| 方法 | 适用场景 | 操作 |
|------|---------|------|
| 关键点加日志/断言 | 有源码访问权限 | 在加载点插入，确认执行路径经过新代码 |
| 发起真实请求 | API / CLI / Web 服务 | 确认输出因改动而变化 |
| 检查产物生成 | 构建任务 / 插件项目 | 验证 hooks 是否触发、产物是否存在且正确 |
| 端到端走查 | UI / 多模块集成 | 从用户操作入口走到最终输出，全程有据 |

对于插件类项目（如 diwu-flow 本身）：验证 hooks 是否被触发、产物是否被生成、JSON 是否合法。

---

## 细粒度子代理委托

> 按**每个步骤**独立判断是否拆分子代理，而非整个任务一次性派发。

### 决策矩阵（三维度 → 四策略）

每个 steps[i] 执行前过矩阵判断：

| 维度 | 值 A（轻量） | 值 B（中等） | 值 C（重量） |
|------|------------|------------|------------|
| **改动幅度** | <200 行，单点修改 | 200-2000 行 | >2000 行 或 API 契约变更 |
| **不确定性** | 团队做过类似，把握 >90% | 有已知未知量但可控 | 首次做 / 外部依赖 / LLM 行为不确定 |
| **验证需求** | 自审即可（L3+） | 需要独立检查 | 必须有 L1-L2 运行态证据 |

### 派发策略

| 策略 | 触发条件 | Agent 流水线 | 说明 |
|------|---------|-------------|------|
| **S1: 直做** | 幅度 A + 不确定 A + 验证 A | 主代理直接执行 | 不拆分，最快路径 |
| **S2: 探索+实施** | 不确定 B 或 C | `explorer` → `implementer` | 先调研再写代码 |
| **S3: 实施+验证** | 幅度 C 或 验证 C | `implementer` → `verifier` | 写完独立验收 |
| **S4: 完整流水线** | 不确定 C + 验证 C 或幅度 C + 不确定 B/C | `explorer` → `implementer` → `verifier` | 三阶段全走 |
| **S5: 异常诊断修复** | 工具失败/结果不符/运行时报错（异常排查场景） | `debugger` → `implementer` → `verifier` | debugger 优先于 explorer，诊断后回交修复 |

> **默认 S1**：只有命中 B/C 维度时才升级策略。宁可直做不要过度拆分。

### 各阶段输入输出契约

#### Stage 1: Explorer（只读调研）

```
输入:
- 任务描述 + 当前步骤的 steps[i]（绝对路径）
- 已知上下文：相关文件列表、已有代码结构

输出（交接报告）:
## 交接报告 - Task#N Step[i] 调研
### 发现
- [关键发现：现有实现、依赖关系、潜在风险]
### 风险评估
- [风险项 + 影响范围 + 缓解建议]
### 实施建议
- [推荐方案 + 需要注意的坑]
### 遗留阻塞点
- [如有阻塞 → 影响 → 建议]
```

#### Stage 2: Implementer（代码实施）

```
输入:
- 任务 acceptance 条目（GWT）
- 步骤具体内容 steps[i]
- Explorer 交接报告（如有 Stage 1）

输出（实施报告）:
## 交接报告 - Task#N Step[i] 实施
### Acceptance 验证结果
- [x] GWT-1: PASS — [证据简述]
- [ ] GWT-2: FAIL — [失败原因]

### 代码变更摘要
- 新增: path/to/file.ts (+/- 行数)
- 修改: path/to/other.ts (+/- 行数)

### 遗留阻塞点
- [如有]
```

#### Stage 3: Verifier（独立验收）

```
输入:
- 任务 acceptance 条目
- Implementer 实施报告（含变更文件列表）
- **不读** recording/ 中任何内容

输出（验证报告，见 verifier agent 定义的标准格式）
```

### 退化路径

任何非核心 agent 失败时退化回：
- explorer 失败 → 主代理自行探索（Read/Grep）→ implementer
- implementer 失败 → dcorr 纠偏协议 → 重试
- verifier 失败 → 主代理自审（L3+ 证据）→ 标记 InReview 或请求人工
- debugger 失败 → 退化回 explorer 重分析或升级人工

### 并行规则

多步骤间可并行当且仅当：
- 文件路径无重叠（files_modified 交集为空）
- 无数据依赖（步骤 B 不需要步骤 A 的产出作为输入）
- 每个并行分支独立委托一个 implementer（或完整流水线）

### Debugger 异常路由

> 详见 `agents/debugger.md`。debugger 属于 **drun 执行域**，异常场景时直接优先于 explorer。

**触发条件**（满足任一即走 debugger 路由，跳过 explorer）：

| # | 条件 | 说明 |
|---|------|------|
| 1 | 实施结果与 acceptance 预期不符 | 运行时报错/输出格式错误/行为偏差 |
| 2 | 工具失败达 3-Strike 阈值 | 同一错误模式出现 3 次 |
| 3 | 明确 bug 排查场景 | 用户报告缺陷/回归问题/偶发复现 |
| 4 | 环境异常 | 依赖不可用/配置漂移/状态不一致 |

**标准链路**：`debugger` → `implementer` → `verifier`

**与 3-Strike 协议的衔接**：第 3 次工具失败后，drun 不再继续重试，而是派发 debugger 诊断根因。

**回交模型**：debugger 输出 `Debugger Report`（根因假设 + 证据需求 + 修复方向）→ implementer 按 report 修复 → verifier 验收。

**不触发 debugger 的场景**：
- 首次接触代码库（仍走 explorer）
- 工具偶发失败 1-2 次（正常重试范围内）
- 纯探索性任务无异常信号

---

## 约束

**stop hook 注入行为**：当 stop hook 注入 InSpec 任务信息到上下文时，Agent 必须**暂停并等待用户明确指示**（将任务改为 InProgress 或给出新指令），**禁止假设沉默=授权而自动执行步骤**。

> 批量执行功能已拆分至 `/dloop`（cron 驱动）。/drun 是单任务执行器——做一件事，做完就停。
