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
- 任务状态变更必须通过 `dtask_transition.py` claim/release 显式完成，禁止直接手改 dtask.toml.status
- closeout 顺序铁律：整理摘要 → decisions → verifier → release → /drec，不可跳序
- drun 是单任务执行器，执行完毕后停止；批量连续执行必须使用 `/dloop`
- stop hook 注入 InSpec 任务信息时必须暂停等待用户明确指示，禁止假设沉默=授权而自动执行

# drun

Session 生命周期管理：从启动到结束的完整协议，含执行验证循环。单任务执行器——做一件事，做完就停。

---

## Session 启动

按以下顺序串行执行（Preflight 失败则停止）：

1. **Preflight**：运行 smoke.sh（如存在）；确认三唯一（主线目录/运行入口/canonical）；完成 5 问开工检查（见 `rules/mindset.md` §不确定性门控）；确认工作区状态
2. **上下文恢复**：读 continue-here.md（存在则读后删除）或最新 1-2 个 session 文件 + decisions.md + `git log --oneline -20`
3. **归档检查**：Done/Cancelled 任务数超阈值（默认 20）时触发归档
4. **任务选择**：
   - 优先恢复 owner 匹配的 InProgress 任务
   - 否则选第一个无 blocked_by 阻塞的 InSpec 任务（允许超前实施至 dloop_review_cap 上限，详见 `rules/task.md` §blocked_by 规范）
   - 禁止选择 InDraft 任务
   - 必须通过 `dtask_transition.py claim` 显式完成 InSpec→InProgress
5. **环境初始化**（可选）：运行 init.sh / 基线测试

---

## Session 结束

### closeout 顺序

**铁律**：整理摘要 → decisions → verifier → release → /drec。不可跳序。

1. 整理 session 摘要（任务状态、实施内容、验收证据、下一步计划）
2. 如有重大设计决策，追加到 decisions.md（三档标准见 `rules/session.md` §何时写 decisions.md）
3. **verifier 终验**（S1/S2 路径标 Done 前必须；S3/S4 已调过则跳过；infra/refactor 纯度量可跳过）。输入 acceptance + 变更文件列表，输出 PASSED/GAPS_FOUND/HUMAN_NEEDED（三分支判定见 `agents/verifier.md`）
4. **release**：`dtask_transition.py release` 切到 Done 或 InReview
5. **调用 `/drec`**：写入 recording + 原子 commit（详见 drec SKILL.md）

> **pending_recording 兜底**：release 自动写入 pending_recording 标记。忘记调 /drec 时 Stop Hook 强制拦截。commit 前必须 Read dtask-state.toml 确认无 dloop 残留。

### 完成前四问

标 InReview/Done 前必答（详见 `rules/verification.md` §完成前四问）：验证层？走到新链路？结果变化？已验证/未验证清单？

### Context Window 管理

接近上限时自动压缩，允许无限期继续工作。不因 token 预算提前停止。

---

## 执行验证循环

每轮执行前明确：当前任务（dtask title+description）、这轮怎么做（steps[i]）、怎么判断做成（acceptance + L1-L3 证据等级，见 `rules/verification.md`）、结果更新到哪（dtask.toml status + recording Checkpoint）。

**调用顺序**：dtask(实施/验证) → dcorr(纠偏)

> 状态变更必须 Read 当前值再写；JSON indent=2, ensure_ascii=False。

---

## 子代理委托

按**每个步骤**独立判断是否拆分，非整个任务一次性派发。

### 决策矩阵

| 维度 | A（轻量） | B（中等） | C（重量） |
|------|----------|----------|----------|
| 改动幅度 | <200 行 | 200-2000 行 | >2000 行 或 API 契约变更 |
| 不确定性 | 团队做过，>90% | 有已知未知量 | 首次做 / 外部依赖 |
| 验证需求 | 自审(L3+) | 需独立检查 | 必须 L1-L2 |

### 派发策略

| 策略 | 条件 | 流水线 |
|------|------|--------|
| S1 直做 | 全 A | 主代理直接执行 |
| S2 探索+实施 | 不确定 B/C | explorer → implementer |
| S3 实施+验证 | 幅度 C 或 验证 C | implementer → verifier |
| S4 完整流水线 | 不确定 C+验证 C 或幅度 C+不确定 B/C | explorer → implementer → verifier |
| S5 异常诊断 | 工具失败/结果不符/异常排查 | debugger → implementer → verifier |

默认 S1，只有命中 B/C 才升级。各 agent 定义见 `agents/` 目录。

### 退化路径

- explorer 失败 → 主代理自行探索 → implementer
- implementer 失败 → dcorr 纠偏 → 重试
- verifier 失败 → 主代理自审(L3+) → 标记 InReview 或请求人工
- debugger 失败 → 退化回 explorer 或升级人工

### 并行规则

步骤间可并行当且仅当：文件路径无重叠 + 无数据依赖。每个并行分支独立委托。

> Debugger 触发条件和路由详见 `agents/debugger.md`。异常场景下 debugger 优先于 explorer。

---

## 约束

**stop hook 注入行为**：注入 InSpec 任务信息时必须暂停等待用户指示，禁止假设沉默=授权。

批量执行功能已拆分至 `/dloop`。drun 是单任务执行器。
