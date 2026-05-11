---
name: drun
version: "2.0"
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
- 任务状态变更必须通过 `dtask_transition.py` claim/release 显式完成，禁止直接手改 dtask.toml.status
- closeout 顺序铁律：整理摘要 → decisions → verifier → release → /drec，不可跳序
- drun 是单任务执行器，执行完毕后停止；批量连续执行必须使用 `/dloop`
- stop hook 注入 InSpec 任务信息时必须暂停等待用户明确指示，禁止假设沉默=授权而自动执行

# drun

Session 生命周期管理：从启动到结束的完整协议，含执行验证循环。单任务执行器——做一件事，做完就停。

---

## Session 启动（R1）

按以下顺序串行执行（Preflight 失败则停止）：

### 1. Preflight

运行 smoke.sh（如存在）；确认三唯一（主线目录/运行入口/canonical）；完成 5 问开工检查（见 `rules/mindset.md` §不确定性门控）；确认工作区状态。

### 2. 上下文恢复（R1 核心）

**读取优先级**（按顺序尝试，第一个成功即停）：

| 优先级 | 来源 | 动作 |
|--------|------|------|
| 1 | `continue-here.md` | 读完后**立即删除**此文件 |
| 2 | 最新 1-2 个 session 文件 | 读 `.diwu/recording/` 下最新文件 |
| 3 | `decisions.md` | 如存在则读取 |
| 4 | `git log --oneline -20` | 了解最近变更脉络 |

> **为什么先读 continue-here.md**：断点恢复是最高优先级上下文。该文件由 context window 压缩或手动中断时写入，内容是"从哪继续"的唯一权威来源。

### 3. 归档检查（R2）

Done/Cancelled 任务数超阈值（默认 20）时触发归档：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/drec_archive.py run --cwd <项目根目录>
```

> **什么时候检查**：每次 Session 启动时，在任务选择之前。命中阈值时必须先归档再选任务，避免 stale 数据干扰选择判断。

### 4. 任务选择策略（R3）

| 优先级 | 条件 | 动作 |
|--------|------|------|
| **P0 恢复** | `dtask-state.toml.task_sessions` 中有 owner 匹配当前 session 的 InProgress 任务 | 直接恢复该任务 |
| **P1 正常** | 第一个无 blocked_by 阻塞的 InSpec 任务 | 准备开始 |
| **P1 超前** | 存在 InReview 且超前未达上限（dloop_review_cap） | 可超前实施 |
| **禁止** | InDraft 任务 | 不允许选择 |

blocked_by 判定：
- 为空 / 不存在 / 全部 Done → 可开始
- 存在 InReview 且超前未达上限 → 可超前（标记 InReview + 立即 commit）
- 达到超前上限 → 输出 PENDING REVIEW

### 5. 环境初始化（可选）

运行 init.sh / 基线测试。

---

## 状态管理命令（R4）

所有状态变更必须通过 `dtask_transition.py` 显式完成：

```bash
# Claim: InSpec → InProgress（必须在选择任务后、实施前执行）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py claim --task-id N --cwd <proj>

# Release: InProgress → 目标状态（必须在验证完成后执行）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py release --task-id N --to done|inreview|inspec|cancelled --cwd <proj>
```

| 目标状态 | 使用场景 |
|---------|---------|
| `done` | 验收全部通过（S1/S2 自审 或 S3/S4 verifier PASSED） |
| `inreview` | 需人工审查（verifier HUMAN_NEEDED 或 超前实施） |
| `inspec` | 需重新审视需求（发现方向偏差） |
| `cancelled` | 任务不再需要 |

---

## Session 结束

### closeout 顺序

**铁律**：整理摘要 → decisions → verifier → release → /drec。不可跳序。

1. 整理 session 摘要（任务状态、实施内容、验收证据、下一步计划）
2. 如有重大设计决策，追加到 decisions.md（三档标准见 `rules/session.md` §何时写 decisions.md）
3. **verifier 终验**（见下方 R5）
4. **release**：`dtask_transition.py release` 切到 Done 或 InReview
5. **调用 `/drec`**：写入 recording + 原子 commit（详见 drec SKILL.md §调用契约）

> **pending_recording 兜底**：release 自动写入 pending_recording 标记。忘记调 /drec 时 Stop Hook 强制拦截。commit 前必须 Read dtask-state.toml 确认无 dloop 残留。

### 完成前四问

标 InReview/Done 前必答（详见 `rules/verification.md` §完成前四问）：验证层？走到新链路？结果变化？已验证/未验证清单？

---

## Verifier 终验规则（R5）

| 维度 | 规则 |
|------|------|
| **触发条件** | S1/S2 路径（主代理自研 / explorer→implementer）标 Done 前 |
| **跳过条件** | S3/S4 路径已调用 verifier 终验；或 category 为 infra/refactor 且改动为纯度量调整 |
| **输入** | acceptance 条目列表 + implementer 交接报告中的文件列表（非 git diff --stat） |
| **输出** | `PASSED`（全部通过→release Done）/ `GAPS_FOUND`（有缺口→保持 InProgress 修复）/ `HUMAN_NEEDED`（需人工判断→release InReview） |
| **三分支** | PASSED → Step 4 release Done；GAPS_FOUND → 返回实施修复缺口后重新验证；HUMAN_NEEDED → Step 4 release InReview |

> 输出状态与 `agents/verifier.md` 定义的 PASSED/GAPS_FOUND/HUMAN_NEEDED 一致。

---

## 运行态验证方法（R6）

drun 是执行引擎，必须教 AI 怎么拿 L1/L2 证据：

| 方法 | 适用场景 | 操作 |
|------|---------|------|
| **日志断言** | 有源码访问权限 | 在加载点插入 assert，确认执行路径经过新代码 |
| **真实请求** | API / CLI / Web 服务 | 发起请求后确认输出因改动而变化 |
| **产物检查** | 构建任务 / 插件项目 | 验证 hooks 触发、产物存在且正确 |
| **E2E 走查** | UI / 多模块集成 | 从用户操作入口走到最终输出，全程有据 |

> 选择依据：优先用能证明"真的走到了新链路"的方法。L1/L2 > L3 > L4 > L5。详见 `rules/verification.md` §运行态验证方法指引。

---

## 执行验证循环

每轮执行前明确：当前任务（dtask title+description）、这轮怎么做（steps[i]）、怎么判断做成（acceptance + L1-L3 证据等级，见 `rules/verification.md`）、结果更新到哪（dtask.toml status + recording Checkpoint）。

**调用顺序**：dtask(实施/验证) → dcorr(纠偏)

> 状态变更必须 Read 当前值再写；JSON indent=2, ensure_ascii=False。

---

## 子代理委托（R7）

按**每个步骤**独立判断是否拆分子代理，而非整个任务一次性派发。

### 决策矩阵（三维度 → 四策略）

每个 steps[i] 执行前过矩阵判断：

| 维度 | A（轻量） | B（中等） | C（重量） |
|------|----------|----------|----------|
| 改动幅度 | <200 行 | 200-2000 行 | >2000 行 或 API 契约变更 |
| 不确定性 | 团队做过，>90% | 有已知未知量 | 首次做 / 外部依赖 |
| 验证需求 | 自审(L3+) | 需独立检查 | 必须 L1-L2 |

| 策略 | 条件 | 流水线 |
|------|------|--------|
| S1 直做 | 全 A | 主代理直接执行 |
| S2 探索+实施 | 不确定 B/C | explorer → implementer |
| S3 实施+验证 | 幅度 C 或 验证 C | implementer → verifier |
| S4 完整流水线 | 不确定 C+验证 C 或幅度 C+不确定 B/C | explorer → implementer → verifier |

默认 S1，只有命中 B/C 才升级。各 agent 定义见 `agents/` 目录。

### 各阶段输入输出契约（R8）

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
- 任务 acceptance 条目列表
- Implementer 交接报告中的变更文件列表

输出:
- PASSED / GAPS_FOUND(具体缺口) / HUMAN_NEEDED(原因)
```

> 以上为最小字段清单。完整模板见 `rules/handoff.md` §二 交接清单。

### 退化路径（R9）

**优先级约定**：debugger 优先于 explorer 调用。退化链中 debugger 失败后才 fallback 到 explorer。

| 失败 agent | 退化动作 |
|------------|---------|
| debugger | 退化回 explorer 或升级人工介入 |
| explorer | 主代理自行探索（Read/Grep）→ implementer |
| implementer | dcorr 纠偏协议 → 重试 |
| verifier | 主代理自审(L3+) → 标记 InReview 或请求人工 |

故障隔离铁律：任何非核心 agent 失败时，必须能退化回 explorer→implementer→verifier 闭环。

### 并行规则（R10）

步骤间可并行当且仅当：**文件路径无重叠** + **无数据依赖** + **独立委托三条件全满足**。每个并行分支独立委托。

---

## Context Window 管理

接近上限时自动压缩，允许无限期继续工作。不因 token 预算提前停止。

---

## 约束

**stop hook 注入行为**：注入 InSpec 任务信息时必须暂停等待用户指示，禁止假设沉默=授权。

批量执行功能已拆分至 `/dloop`。drun 是单任务执行器。
