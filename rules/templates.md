# 格式模板与参数

> **规则约束级别说明**：本文件定义格式模板与参数的通用规则。除非特别标注 `[建议]`，否则都是必须遵守的约束。

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

**禁止 YAML front matter**：Session 文件**禁止**以 `---` 开头或包含 `---...---` 包裹。`---` 在 Markdown 中是 front matter 语法，渲染器会将包裹内容当作元数据隐藏。Session 文件必须直接以 `## Session` 开头。

- **正例**：文件第一行就是 `## Session 2026-04-14 18:44:09`
- **反例**：文件开头写 `---` 再跟 `## Session ...`（整篇内容被渲染器隐藏）
- **反例**：文件末尾加闭合 `---`（中间内容被当作 front matter 元数据）

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

## 退化信号-止损动作对照表

| 退化信号 | 止损动作 |
|---------|---------|
| edit_strek（反复沿用已否定路径） | 回到现象层，重新定义问题 |
| pure_discussion（输出像套路不像当前任务） | 补正例/反例/边界例 |
| repetitive_loop（改动无运行态证据） | 停止宣称完成，先补验证 |
| context_rot（讨论膨胀、边界萎缩） | 压缩高价值前提，只保留当前范围 |
| scope_drift（同一前提反复重讲） | 把前提外化到 README/规范/任务卡片 |
| acceptance_drift（历史材料长、动作模糊） | 拆大任务，回到最小可执行单元 |

## 可调参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 超前上限 | 5 | 最多同时超前实施的任务数（dsettings.json） |
| task_archive_threshold | 20 | Done/Cancelled 任务超此数触发归档（dsettings.json） |
| recording_archive_threshold | 50 | session 文件超此数触发归档（dsettings.json） |
| recording_retention_days | 30 | 归档时保留最近 N 天（dsettings.json） |
| snapshot_dedup_sec | 600 | 快照去重时间窗口秒数（dsettings.json，stop_background.py 读） |
| context_monitor_warning | 30 | WARNING 阈值：工具调用次数（dsettings.json） |
| context_monitor_critical | 50 | CRITICAL 阈值：触发阻塞提醒（dsettings.json） |
| context_monitor_delay | 10 | CRITICAL+DELAY 延迟阈值（dsettings.json） |
| continuous_mode | true | 持续运行模式开关（dsettings.json，stop_decision.py 读） |
| drift_detection | enabled | 退化检测开关（dsettings.json） |
| subagent_concurrency | 3 | 子代理最大并行数（dsettings.json，subagent_start.py 读） |
| subagent_explore_model | haiku | 探索类子代理模型（dsettings.json，subagent_start.py 读） |
| subagent_implement_model | inherit | 实施类子代理模型（dsettings.json，subagent_start.py 读） |
| pitfalls.archive_aggregate | true | 归档时聚合踩坑到 pitfalls（dsettings.json，stop_archive_agg.py 读） |
| error_injection.enabled | true | PreToolUse 错误/决策注入开关（dsettings.json） |
| error_injection.max_sessions | 3 | 注入时扫描的最近 session 数量（dsettings.json） |
| error_tracking.enabled | true | PostToolUseFailure 3-Strike 协议开关（dsettings.json） |
| recording_reminder.enabled | true | PostToolUse 写后记录提醒开关（dsettings.json） |
| error_cooldown_sec | 60 | 同一工具失败计数的冷却窗口秒数（dsettings.json） |

## 验证脚本模板

**smoke.sh**：JSON 合法性检查（dtask + dsettings.json），exit 0。
**task\_\<id\>\_verify.sh**：按 acceptance 编写验证逻辑，exit 0 成功。
