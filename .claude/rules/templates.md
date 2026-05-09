# 格式模板

> **规则约束级别说明**：本文件定义格式模板的通用规则。除非特别标注 `[建议]`，否则都是必须遵守的约束。

## 文档铁律（跨文档通用）

| 文档类型 | 核心铁律 |
|---------|---------|
| **PRD** | 序号层级 `1.→1.1→1.1.1→•→。`；纯中文（除 ID/CSV/API 等行业术语）；业务视角，不干涉技术实现 |
| **Acceptance** | GWT 格式 `Given...When...Then`；Then 子句可断言为 expect/assert；单条"且"≤3 个 |
| **Session 记录** | 时间戳必须 `date '+%Y-%m-%d %H:%M:%S'` 获取；最新 session 在最前面 |
| **Task.json** | steps 绝对路径；[锁定] 标注技术选型，[建议] 标注实现细节 |

## BLOCKED / REVIEW / PENDING 格式

### BLOCKED
```
BLOCKED - 需要人工介入
当前任务: Task#N - [标题]
阻塞原因: [具体原因]
需人工帮助: [操作步骤]
解除后: InSpec → InProgress
```

### PENDING REVIEW
```
PENDING REVIEW - 超前实施已达上限
等待验收: Task#N  |  已超前: Task#X, Task#Y (N/5)
```

### REVIEW 请求
```
REVIEW - 请求人工审查
Task#N: [标题]  |  修改范围: [文件路径]
验收验证: - [x] [条目] — [方法]
等待: 人工确认后 Done
```

## DECISION TRACE

**框架定位**：现象→判断→动作的结构化输出。证据=现象，规则命中+排除项=判断，下一步=动作。

```
DECISION TRACE
结论: [BLOCKED|CONTINUE|REVIEW|SKIP]
规则命中: - [规则条目]
证据: - [事实数据]
排除项: - [为什么不是其他结论]
下一步: - [立即执行的动作]
```

## Session 文件格式

```markdown
## Session YYYY-MM-DD HH:MM:SS
### Task#N: [标题] → [状态]
**实施内容**: - [工作项]
**验收验证**: - [x] [acceptance] ([方法])
**提交**: commit [hash]
### 下一步: [计划]
### 本次踩坑/经验
- [类别] 现象 → 根因 → 误判 → 正确做法
### 错误追踪表（可选）
| 时间戳 | 工具 | 错误摘要 | 尝试 | 解决方式 | 类别 |
```

**禁止 YAML front matter**：Session 文件**禁止**以 `---` 开头或包含 `---...---` 包裹。

## CONTINUOUS_MODE_COMPLETE

```
CONTINUOUS MODE COMPLETE - 所有可执行任务已完成
已完成: Task#A, Task#B  |  剩余: Task#X(InDraft), Task#Y(BLOCKED)
本轮连续完成 N 个任务
```

## 最小规格通用模板

```text
目标：   一句话描述这次要得到的结果
输入：   已知材料 / 关键约束 / 外部依赖 / 必填参数 / 可选参数
输出：   最终产物 / 存放位置 / 返回形式 / 命名规则
格式：   必含字段 / 顺序要求 / 结构要求
验收标准：什么证据算完成 / 验证哪一层 / 边界不能破 / 待验证项
```

### 按类型收口规格

| 类型 | 重点写清 |
|------|---------|
| **实现型** | 改哪条能力边界 / 不允许扩大范围 / 完成后看什么运行态变化 |
| **排查型** | 已知现象 / 最小复现 / 已排除项 / 怀疑链路 / 最小验证 |
| **回归型** | 验证哪条能力边界 / 样本前提 / 预期输出与失败信号 / 可接受降级 |
| **评审型** | 哪些风险 / 行为变化在哪 / 契约是否漂移 / 测试缺口与未验证项 |

## Checkpoint 格式模板

> 从 `rules/task.md` 提取并统一到此处的 Checkpoint 格式。

触发条件（满足任一）：
- steps 数量 > `checkpoint_min_steps`（默认 5）
- 预估修改行数 > `checkpoint_min_lines`（默认 500）

```
### Checkpoint @ 步骤3/8
进度: 完成 auth 模块重构，payment 模块进行中
已修改: src/auth.ts(+120/-80), src/models/user.ts(+15/-5)
下一步: 步骤4 payment 模块重构 → 步骤5 集成测试
回滚方式: git checkout -- src/auth.ts src/models/user.ts
         或 git reset --soft HEAD~1（如已提交）
```

> 退化信号与止损动作见 `skills/dcorr/SKILL.md` §Step 1 触发条件。
> 可调参数见 `assets/dinit/assets/dsettings.json.template`（唯一真实来源）。

## Handoff Report 模板（交接报告）

> 从 `rules/handoff.md` §二 交接清单提取标准化。子代理完成工作后必须输出此结构。

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

> 完整交接协议（注入格式、回交模型、Handoff Matrix）见 `rules/handoff.md`。

## 验证脚本模板

**smoke.sh**：JSON 合法性检查（关键状态文件），exit 0。
**task_<id>_verify.sh**：按 acceptance 编写验证逻辑，exit 0 成功。
