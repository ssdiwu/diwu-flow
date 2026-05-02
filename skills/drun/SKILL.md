---
name: drun
version: "1.0"
type: rule
description: "单任务执行器——启动（Preflight 5 步）、上下文恢复、归档检查、任务选择、Session 结束协议、执行验证循环"
triggers:
  - "Session 启动或结束"
  - "选择下一个任务"
  - "判断是否续跑"
  - "归档旧任务"
  - "用户说 session、启动、下一步、续跑、归档"
  - "需要执行验证循环"
keywords:
  - "session"
  - "启动"
  - "Preflight"
  - "单任务执行"
  - "执行验证"
depends:
  - dtask
  - dvfy
  - djug
  - dcorr
  - drec
effort: high
argument-hint: "[功能描述] [category] [blocked_by]"
---

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

1. 写入 recording/session 文件（必须运行 date 获取真实时间戳），记录 Session 标题、处理的任务及状态、验收验证结果、下次应该做什么
2. **将 recording 与本轮代码变更一并 commit**（不单独成 commit）

> **（R1）**：写入 session 文件前必须 Read 当前 session 文件尾部，确认追加位置正确。

3. 如有重大设计决策，追加到 decisions.md
4. 确保 task.json 反映最新状态；若本轮已完成实施与验证，最后一步必须用 `dtask_transition.py release` 将任务显式切到 `Done` 或 `InReview`

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
| 3 | 怎么判断这轮做成了？ | 对应 `acceptance` 条目 + dvfy 证据等级（L1-L3 主判） |
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

**调用顺序**：dtask(实施) → dvfy(验证) → djug(判定) → dcorr(纠偏)

执行完毕后停止，输出完成摘要。如需连续执行多个任务，使用 `/dloop`。

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

### 并行规则

多步骤间可并行当且仅当：
- 文件路径无重叠（files_modified 交集为空）
- 无数据依赖（步骤 B 不需要步骤 A 的产出作为输入）
- 每个并行分支独立委托一个 implementer（或完整流水线）

---

## 约束

**stop hook 注入行为**：当 stop hook 注入 InSpec 任务信息到上下文时，Agent 必须**暂停并等待用户明确指示**（将任务改为 InProgress 或给出新指令），**禁止假设沉默=授权而自动执行步骤**。

> 连续循环功能已拆分至 `/dloop`。/drun 是单任务执行器——做一件事，做完就停。
