# 子代理交接协议

> **规则约束级别说明**：本文件定义 Agent 间协作的交接真相源。除非特别标注 `[建议]`，否则都是必须遵守的约束。
> 定义 SubagentStart Hook 注入格式、交接报告结构、Agent 设计约束与 Plan→Dtask 门控。
> 与 `verification.md`（证据等级）配合使用：本文件管"怎么交接"，verification 管"什么算完成"。

## 一、主编排者边界

| 主编排者 | 边界 | 不做什么 |
|---------|------|---------|
| `dtask` | 任务定义、状态管理、依赖图、acceptance | 不执行代码、不做验证、不写 recording |
| `drun` | 执行循环：claim→实施→验证→release | 不改 task 定义、不新建任务、不修改 dtask.json 内容字段 |

**铁律**：`dtask` 只管"做什么、做到什么程度算完"，`drun` 只管"怎么做、怎么证明做完了"。两者不越界。

## 二、子代理启动仪式规格

> dtask 定义了并行条件与分工策略。本节定义 SubagentStart Hook 触发时自动注入的内容格式——这是 Skills 中未覆盖的交接协议。

### 自动注入内容清单

SubagentStart Hook 必须向子代理注入以下四项：

#### 1. Session 摘要

```
## 当前 Session
- 时间: [时间戳]
- 目标: [一句话]
- 已完成: Task#N Done, Task#M Done
- 进行中: Task#P InProgress
- 阻塞: Task#Q blocked_by Task#R
```

#### 2. InProgress 任务信息

```
## 当前任务: Task#N [title]
Owner Session: [session_id from .diwu/dtask-state.json.task_sessions]
Acceptance:
- [ ] GWT-1: Given ... When ... Then ...
- [ ] GWT-2: ...
Steps:
1. [锁定] 具体步骤（绝对路径）
2. [建议] 实现细节
```

#### 3. decisions 最近 N 条

```
## 近期决策记录
- [时间] 决策标题 — 结论摘要
- [时间] 决策标题 — 结论摘要
```

默认 N=3；不足 3 条时全部注入。

### 交接清单（子代理必须返回）

子代理完成工作后必须输出以下结构化信息：

```text
## 交接报告 - Task#N

### Acceptance 验证结果
- [x] GWT-1: PASS — [证据简述]
- [ ] GWT-2: FAIL — [失败原因]

### 代码变更摘要
- 新增: path/to/file.ts (+/- 行数)
- 修改: path/to/other.ts (+/- 行数)
- 删除: path/to/old.ts

### 遗留阻塞点
- [阻塞描述] → 影响: [具体影响] → 建议: [下一步操作]

### 下一步前置条件
- [条件1]
- [条件2]
```

**PASS/FAIL 判定规则**：逐条对照 acceptance 的 GWT 条目，每条必须标注 PASS 或 FAIL 并附证据。存在 FAIL 时不得标记 InReview。

## 三、回交模型

### 正向回交（Normal）

子代理正常完成，返回上述交接报告。主代理核对后决定 InReview 或 Done。

### 异常回交（Exception）

| 场景 | 子代理行为 | 主代理处理 |
|------|-----------|-----------|
| 能力不足 | 标记能力缺口 + 已完成部分结果 | 降级方案或升级 agent |
| 阻塞发现 | 返回 BLOCKED 模板 + 阻塞原因 | 评估是否真阻塞 or 可绕过 |
| 超出范围 | 停止 + 报告边界越界 | 收缩范围或拆新任务 |

### 跨域回退（Cross-domain Fallback）

当子代理的工作涉及两个域的交界处（如 explorer 发现需要改代码）：
1. **停止当前域工作**
2. **输出跨域回退报告**：说明在哪一步、需要哪个域、为什么
3. **主代理重新派发到目标域**

> 故障隔离铁律：任何非核心 agent 失败时，必须能退化回 explorer→implementer→verifier 闭环。

## 四、Explorer 双域定位

Explorer 的默认域是**只读调查**，但以下情况触发跨域切换：

| 触发条件 | 切换到 |
|---------|--------|
| 发现代码 bug 且修复 < 20 行 | implementer（直修） |
| 发现架构问题需多文件协调 | 回交主代理重新规划 |
| 确认需求理解有偏差 | 回交主代理澄清 |

## 五、Handoff Matrix

| 派发方 | 接收方 | 典型场景 | 回交产物 |
|--------|--------|---------|---------|
| drun (主代理) | explorer | 首次接触代码库、追踪依赖 | 调查报告 + 建议方案 |
| drun (主代理) | implementer | 明确实现路径后的代码修改 | 交接报告（含 Acceptance 结果） |
| drun (主代理) | verifier | 实施完成后独立验收 | 验证报告（PASS/FAIL + 证据） |
| explorer | implementer | explorer 直修小 bug | 简化交接（仅变更摘要） |
| implementer | verifier | S3 流水线自动衔接 | 完整交接报告 |

## 六、Agent 设计约束

> 从 `mindset.md` 迁入。Agent 是能力容器不是岗位标签。

- **能力驱动**：先编排任务节点→识别能力需求→有对应 agent 就派发→无则标记能力缺口
- **不强塞职责**：不要把完整 workflow SOP 塞进 agent prompt
- **负面清单优先**：每个 agent 必须明确"不做什么"；没有负面清单的 agent 必然越界
- **新 Agent 门槛**：某类能力缺口需在 ≥3 个不同任务中重复出现、且边界清晰可独立，才值得设计
- **故障隔离**：任何非核心 agent 失败时，必须能退化回 explorer→implementer→verifier 闭环

## 七、Plan→Dtask 门控

> 从 `mindset.md` 迁入。守卫实现：`plan_exit_hint.py`（ExitPlanMode 强提示）+ `task_entry_guard.py`（Edit|Write 实施入口守卫）

- **Plan 不是执行契约**：Plan 输出是架构设计方案，不是可直接实施的任务定义
- **大计划先落任务**：≥3 步的实施工作必须先落地为 `dtask.json` 条目（含 GWT acceptance），再进入 `/drun` 循环
- **小改动可直做**：<3 步且结果可预期的小改动可直接执行
- **双守卫分层**：退出 plan 时有强提示，进入 Edit/Write 写阶段有实施入口守卫
- **覆盖范围明确**：当前守卫仅覆盖 Edit|Write 主写入路径；Bash 路径暂不拦截，后续可补
