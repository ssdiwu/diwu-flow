---
name: darc
version: "1.0"
type: rule
description: "归档管理——Task 归档与 Recording 物理归档的双轨机制、触发条件、手动步骤、验证清单"
triggers:
  - "终态任务数超阈值"
  - "session 文件数超阈值"
  - "用户说 归档、archive、清理"
keywords:
  - "归档"
  - "archive"
  - "Task归档"
  - "Recording归档"
  - "双轨机制"
  - "踩坑聚合"
effort: low
argument-hint: "[归档类型]"
---

# darc — 归档管理

> 双轨机制：Task 轨道（Done/Cancelled → archive）+ Recording 轨道（旧 session → archive）。纯检测不自动执行。

## 归档双轨总览

| 轨道 | 触发条件 | 阈值（dsettings.json） | 产物位置 |
|------|---------|----------------------|----------|
| Task 归档 | Done/Cancelled 数 >= threshold | `task_archive_threshold`（默认 20） | `.diwu/archive/task_archive_YYYY-MM.json` |
| Recording 归档 | 文件数 >= threshold **或** 文件年龄 > days | `recording_archive_threshold`（默认 50）<br>`recording_retention_days`（默认 30） | `.diwu/archive/recording_YYYY-MM-DD.md` |

## 触发条件详解

### Task 归档

- **条件**：`.diwu/dtask` 中 `status` 为 `Done` 或 `Cancelled` 的任务数量 >= `task_archive_threshold`
- **检测方**：归档检测脚本 -> `check_task_archive()`
- **动作**：输出 `[ARCHIVE_CHECK]` 提示 + 手动指引

### Recording 归档（双条件 OR）

- **条件 A**：`.diwu/recording/` 下 session 文件数 >= `recording_archive_threshold`
- **条件 B**：任一 session 文件修改时间距现在 > `recording_retention_days` 天
- **满足任一即触发**
- **检测方**：归档检测脚本 -> `check_recording_archive()`
- **动作**：输出 `[ARCHIVE_CHECK]` 提示 + 手动指引

## 手动执行步骤

```
0. 创建归档标记（guard 放行）：
   touch .diwu/.archiving-in-progress
   → 通知 task_entry_guard.py：后续对 dtask.json 的写入是合法归档操作，不触发 exit(2) 硬阻止

1. 判断：查看 [ARCHIVE_CHECK] 消息
2. Task 归档：
   a. 读取 .diwu/dtask，筛选 status=Done/Cancelled 的任务
   b. 写入 .diwu/archive/task_archive_YYYY-MM.json（当月归档文件）

> **（R1+R2）**：写入 archive JSON（task_archive_*.json / .last_archive_summary.json）前 **Read 确认当前文件状态**；JSON 必须 **indent=2, ensure_ascii=False**。

   c. 从 dtask 中移除已归档任务（保留活跃任务）
3. Recording 归档：
   a. 列出 .diwu/recording/ 所有 session 文件
   b. 按时间排序，将最旧的 N-threshold 个文件内容追加到 .diwu/archive/recording_YYYY-MM-DD.md
   c. 删除已归档的源文件（保留最新 threshold 个）
4. 踩坑聚合（必做）：
   a. 扫描本次归档的 recording + 剩余 recording 中所有 ### 本次踩坑/经验 段落
   b. 归档文件内按 ## Source: session-xxx.md 分隔符追踪每条踩坑所属的具体 session
   c. 按 Layer 2 类别标签聚类（验证误读/分层未拆清/环境漂移/路由护栏契约等）
   d. 追加写入 .diwu/project-pitfalls.md（不覆盖已有条目，追加新条目）
   e. **来源列必须写具体 session 文件名**（如 session-2026-04-18-213522.md），禁止写占位符如"聚合来源"
   f. 如无踩坑数据则跳过，在 summary 中标注 "0 new pitfalls"
4.5 删除归档标记（guard 恢复正常拦截）：
   rm -f .diwu/.archiving-in-progress
   → 归档完成，guard 恢复对 dtask.json 写入的正常检查
5. 验证清单：
   [ ] dtask 中无残留的 Done/Cancelled 任务（超出保留阈值的部分）
   [ ] recording/ 文件数 < threshold
   [ ] archive/ 目录下产物可读且 JSON/MD 合法
   [ ] .last_archive_summary.json 已更新（含归档时间、数量、文件列表）
   [ ] project-pitfalls.md 已更新（如有踩坑数据）或确认无新踩坑
```

## 归档产物格式

### task_archive_YYYY-MM.json

```json
{
  "archived_at": "2026-04-19T10:30:00Z",
  "source": ".diwu/dtask",
  "tasks": [
    { "id": 1, "title": "...", "status": "Done", "completed_at": "..." },
    { "id": 2, "title": "...", "status": "Cancelled", "reason": "..." }
  ],
  "count": 2
}
```

### recording_YYYY-MM-DD.md

```markdown
# Recording Archive: 2026-04-19

Archived from: .diwu/recording/
Session count: 5
Date range: 2026-03-01 ~ 2026-03-31

---

## Session 2026-03-01 09:00:00
（原 session 内容）

## Session 2026-03-05 14:22:33
（原 session 内容）
```

### .last_archive_summary.json

```json
{
  "last_archive_time": "2026-04-19T10:30:00Z",
  "task_archived_count": 15,
  "recording_archived_count": 5,
  "archive_files": ["task_archive_2026-04.json", "recording_2026-04-19.md"]
}
```

## 归档检测说明

归档检测脚本是**纯检测脚本**，不执行物理归档：

| 函数 | 功能 | 返回值 |
|------|------|--------|
| `check_task_archive(settings, tasks)` | Done/Cancelled 数 vs 阈值 | `(needs_archive, count, threshold, message)` |
| `check_recording_archive(settings)` | 文件数/年龄 vs 双条件 OR | `(needs_archive, total, to_archive, thresh_days, message)` |
| `check(settings, tasks)` | 主入口，聚合两个检查 | `[(level, message)]` 结果列表 |

输出格式：
```
[ARCHIVE_CHECK] Task 归档预警: 25 个终态任务 (阈值 20)。执行归档开始。
[ARCHIVE_CHECK] Recording 归档预警: 62 个 session 文件 (阈值 50)。执行归档开始。
```

## 不做的事

- **不自动删除**任何文件（归档是显式操作，手动触发）
- **不压缩**归档产物（保持原始格式可读）
- **不归档活跃任务**（InProgress/InSpec/InReview/InDraft 保留在 dtask）
- **不修改任务 ID**（归档后 ID 不复用，dtask 新任务继续递增）
- **不自动聚合踩坑**（检测脚本只做完整性检查；踩坑聚合由手动步骤第 4 步执行）
