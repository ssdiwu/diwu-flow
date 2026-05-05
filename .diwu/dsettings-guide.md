# dsettings.json 配置说明

> 本文件为 `.diwu/dsettings.json` 的逐项配置指南。
> 修改后立即生效，无需重启。模板来源：`assets/dinit/assets/dsettings.json.template`

---

## 一、自动续跑控制

### `continuous_mode`（布尔值，默认 `true`）

控制 Stop 事件触发时是否自动推入下一个任务。

| 值 | 行为 |
|---|------|
| `true` | 任务完成后自动注入下一个 InSpec 任务，**阻止会话结束** |
| `false` | 输出完成摘要 + 下一任务信息，**允许会话正常结束** |

> **使用场景**：批量跑任务时开 `true`；想逐个验收或手动控制节奏时改为 `false`。

---

## 二、归档阈值

### `task_archive_threshold`（数字，默认 `20`）

Done/Cancelled 任务数达到此值时触发归档（写入 `.diwu/archive/task_archive_YYYY-MM.json`）。

### `recording_archive_threshold`（数字，默认 `30`）

Session 记录文件数达到此值时触发归档（写入 `.diwu/archive/recording_YYYY-MM-DD.md`）。

### `recording_retention_days`（数字，默认 `30`）

归档时保留最近 N 天的 recording 文件，超出范围的清理。

---

## 三、审查与超前实施

### `review_limit`（数字，默认 `5`）

允许「超前实施」的最大任务数。当 InReview 任务达到此数量时停止自动续跑，提示人工验收。

> 超前实施 = 当前任务 Done 后，下一个 InSpec 任务被直接执行并标记为 InReview，不等人工确认。

---

## 四、上下文监控（context_monitor）

这三个参数控制**写工具调用密度检测**，防止长 session 中 context window 过度膨胀而不自知。

### `context_monitor_warning`（数字，默认 `30`）

写工具（Edit/Write/Bash）调用次数达到此值时发出**警告提醒**。

### `context_monitor_critical`（数字，默认 `50`）

写工具调用次数达到此值时触发**自动 checkpoint**（写入 `.diwu/recording/checkpoint-*.md`），记录当前进度以便 context 压缩后恢复断点。

### `context_monitor_delay`（数字，默认 `10`）

在 critical 阈值之上额外容忍的调用次数。实际触发 checkpoint = critical + delay = **60 次**。

> **通俗理解**：连续编辑/执行 30 次提醒你一下；到 60 次自动存个进度快照。调高则更少打扰，调低则更早保护。

---

## 五、退化信号检测（drift_detection）

检测 Agent 是否偏离正轨（走神、死循环、越界编辑）。**仅提醒不阻断**，始终 exit 0。

### `drift_detection.enabled`（布尔值，默认 `true`）

总开关。设为 `false` 关闭所有退化检测。

### `drift_detection.checks`（数组，默认全部启用）

四种检测器：

| 检测器 | 检测什么 | 触发条件 |
|--------|---------|---------|
| `edit_streak` | 连续编辑不验证 | 连续 Edit/Write 达到 `edit_streak_threshold` 次（默认 5），中间无 Bash 执行 |
| `pure_discussion` | 纯讨论不动手 | 连续非文件修改操作达 `pure_discussion_threshold` 次（默认 10） |
| `repetitive_loop` | 重复循环模式 | 同一工具+相同参数连续重复 3 次 |
| `scope_drift` | 编辑范围越界 | Edit/Write 的目标文件不在当前 InProgress 任务的 `files_modified` 列表中 |

### `drift_detection.edit_streak_threshold`（数字，默认 `5`）

edit_streak 触发阈值。连续编辑 N 次未跑测试/构建就提醒验证。

### `drift_detection.pure_discussion_threshold`（数字，默认 `10`）

pure_discussion 触发阈值。纯讨论 N 次提醒落地。

### `drift_detection.scope_drift_tolerance`（字符串，默认 `"high"`）

scope_drift 容忍度。`"high"` = 同目录或同文件名即放行；可扩展 `"medium"` / `"low"` 等级。

---

## 六、子代理配置

### `subagent_concurrency`（数字，默认 `3`）

并行子代理的最大数量。任务间无文件冲突时可同时派发多个子代理。

### `subagent_explore_model`（字符串，默认 `"haiku"`）

探索型子代理使用的模型。`"haiku"` 最快最省；可改 `"sonnet"` 提升质量。

### `subagent_implement_model`（字符串，默认 `"inherit"`）

实施型子代理使用的模型。`"inherit"` = 继承主会话模型；也可指定 `"sonnet"` / `"opus"`。

---

## 七、错误注入与追踪（高级功能）

> 这两个功能用于**跨 session 错误模式学习**，帮助 Agent 从历史踩坑中积累经验。

### `error_injection.enabled`（布尔值，默认 `true`）

**错误注入开关**。开启后，系统会在新 session 启动时从历史踩坑记录中提取常见错误模式，「注入」到 Agent 上下文中作为预防性提示。

> 类比：就像老员工给新人的「避坑清单」。不是真的制造错误，而是把过去踩过的坑提前告诉你。

### `error_injection.max_sessions`（数字，默认 `3`）

最多回溯多少个历史 session 来提取错误模式。值越大参考样本越多，但 context 占用也越多。

### `error_tracking.enabled`（布尔值，默认 `true`）

**错误追踪开关**。开启后，同一工具连续失败时会启动 **3-Strike 协议**：

| 尝试 | 策略 | 注入内容 |
|------|------|---------|
| 第 1 次 | 诊断并修复根因 | 温和提醒：诊断根因，如有踩坑考虑记录 |
| 第 2 次 | 更换根本不同的方法 | 强烈建议：换工具/换文件/换策略 |
| 第 3+ 次 | 广泛重新思考或升级用户 | 阻止继续：质疑假设，考虑升级用户 |

状态持久化在 `/tmp/diwu_ctx_<pid>_errtrack`，冷却窗口 60 秒。

---

## 八、辅助功能

### `snapshot_dedup_sec`（数字，默认 `600`）

快照去重时间窗口（秒）。同一文件在 N 秒内的多次编辑只算一次快照更新，避免频繁刷屏。

### `recording_reminder.enabled`（布尔值，默认 `true`）

Session 结束前是否提醒写入 recording 文件。

### `pitfalls.archive_aggregate`（布尔值，默认 `true`）

归档时是否自动将各 session 的踩坑记录按类别聚类，追加到 `.diwu/project-pitfalls.md`。

---

## 快速调整建议

| 场景 | 改什么 | 改成什么 |
|------|--------|---------|
| 不想自动续跑 | `continuous_mode` | `false` |
| 任务多怕 context 爆 | `context_monitor_critical` | `30`（更早 checkpoint） |
| 子代理想用更好的模型 | `subagent_explore_model` | `"sonnet"` |
| 不想看退化提醒 | `drift_detection.enabled` | `false` |
| 不需要错误注入学习 | `error_injection.enabled` | `false` |
| 不需要 3-Strike 重试机制 | `error_tracking.enabled` | `false` |
| 并行更多子代理 | `subagent_concurrency` | `5` 或更高 |
