# dsettings.toml 配置说明

> 本文件为 `.diwu/dsettings.toml` 的逐项配置指南。
> 修改后立即生效，无需重启。模板来源：`assets/dinit/assets/dsettings.toml.template`

---

## 一、归档阈值

### `task_archive_limit`（数字，默认 `20`）

Done/Cancelled 任务数达到此值时触发归档（写入 `.diwu/archive/task_archive_YYYY-MM.json`）。

### `recording_file_limit`（数字，默认 `30`）

Session 记录文件数达到此值时触发归档（写入 `.diwu/archive/recording_YYYY-MM-DD.md`）。

### `recording_keep_days`（数字，默认 `30`）

归档时保留最近 N 天的 recording 文件，超出范围的清理。

---

## 二、审查与超前实施

### `dloop_review_cap`（数字，默认 `5`）

允许「超前实施」的最大任务数。当 InReview 任务达到此数量时停止自动续跑，提示人工验收。

> 超前实施 = 当前任务 Done 后，下一个 InSpec 任务被直接执行并标记为 InReview，不等人工确认。

---

## 三、上下文监控（context_monitor）

这三个参数控制**写工具调用密度检测**，防止长 session 中 context window 过度膨胀而不自知。

### `ctxmon_warn_at`（数字，默认 `30`）

写工具（Edit/Write/Bash）调用次数达到此值时发出**警告提醒**。

### `ctxmon_checkpoint_at`（数字，默认 `50`）

写工具调用次数达到此值时触发**自动 checkpoint**（写入 `.diwu/recording/checkpoint-*.md`），记录当前进度以便 context 压缩后恢复断点。

### `ctxmon_checkpoint_delay`（数字，默认 `10`）

在 critical 阈值之上额外容忍的调用次数。实际触发 checkpoint = critical + check_interval = **60 次**。

> **通俗理解**：连续编辑/执行 30 次提醒你一下；到 60 次自动存个进度快照。调高则更少打扰，调低则更早保护。

---

## 四、退化信号检测

### `drift_enabled`（布尔值，默认 `true`）

总开关。设为 `false` 关闭所有退化检测。检测 Agent 是否偏离正轨（走神、死循环、越界编辑）。**仅提醒不阻断**，始终 exit 0。

---

## 五、错误追踪

### `error_tracking_enabled`（布尔值，默认 `true`）

**错误追踪开关**。开启后，同一工具连续失败时会启动 **3-Strike 协议**：

| 尝试 | 策略 | 注入内容 |
|------|------|---------|
| 第 1 次 | 诊断并修复根因 | 温和提醒：诊断根因，如有踩坑考虑记录 |
| 第 2 次 | 更换根本不同的方法 | 强烈建议：换工具/换文件/换策略 |
| 第 3+ 次 | 广泛重新思考或升级用户 | 阻止继续：质疑假设，考虑升级用户 |

状态持久化在 `/tmp/diwu_ctx_<pid>_errtrack`，冷却窗口 60 秒。

---

## 六、辅助功能

### `reminder_on_taskdone`（布尔值，默认 `true`）

Session 结束前是否提醒写入 recording 文件。

---

## 快速调整建议

| 场景 | 改什么 | 改成什么 |
|------|--------|---------|
| 任务多怕 context 爆 | `ctxmon_checkpoint_at` | `30`（更早 checkpoint） |
| 不想看退化提醒 | `drift_enabled` | `false` |
| 不需要 3-Strike 重试机制 | `error_tracking_enabled` | `false` |
