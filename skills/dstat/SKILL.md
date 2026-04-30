---
name: dstat
version: "1.0"
type: tool
description: "项目状态只读聚合——一键展示任务进度、最近 Session、近期决策、Git 状态。触发场景：用户说 /dstat、看看项目状态、项目概况、当前进展"
triggers:
  - "/dstat"
  - "看看项目状态"
  - "项目概况"
  - "当前进展"
keywords:
  - "状态"
  - "概览"
  - "progress"
  - "dstat"
depends: []
effort: low
argument-hint: "[--deep]"
---

# dstat

项目全局状态只读聚合命令。不修改任何文件，不改变任何状态，不触发 drun 执行循环。

---

## 输出规格

### 标准模式（默认）

```
## 项目状态概览

### 任务进度
┌──────────┬────────┬────────┬────────┬────────┐
│ 总数     │ InSpec │ InProg │ Review │ Done   │
│ N        │ N      │ N      │ N      │ N      │
└──────────┴────────┴────────┴────────┴────────┘

Blocked: N | Cancelled: N

### 最近 Session
- **session-YYYY-MM-DD-HHMMSS** (N 分钟/小时/天前)
  - 处理: Task#X → [status], Task#Y → [status]
  - 下一步: [从 session 摘要提取]

### 近期决策
1. [时间] [决策标题] — [一句话摘要]
2. [时间] [决策标题] — [一句话摘要]
3. [时间] [决策标题] — [一句话摘要]

### Git 状态
- 分支: [branch]
- 工作区: [clean / dirty (N files)]
- 最近提交: [hash] [message]

### 归档状态
- 上次归档: [日期 或 "从未"]
- 待归档任务: N | 待归档 Session: N
```

### Deep 模式（--deep）

在标准模式基础上追加：

**活跃任务详情**：列出每个 InProgress/InSpec 任务的 title + status + blocked_by

**Git 详细信息**：
- `git log --oneline -10`
- `git diff --stat`（如有未提交变更）

---

## 数据源与读取顺序

| 序号 | 数据源 | 读取方式 | 容错 |
|------|--------|---------|------|
| 1 | `.diwu/dtask.json` | JSON 解析 | 不存在则输出"无任务数据" |
| 2a | `.diwu/recording/` | 列目录取最新 1-2 个 .md（用于「最近 Session」展示） | 不存在则输出"无 session 记录" |
| 2b | `.diwu/recording/` | 统计全部 .md 文件数（用于「归档状态」计数） | 同上 |
| 3 | `.diwu/decisions.md` | 读最后 20 行 | 不存在则跳过 |
| 4 | `date '+%Y-%m-%d %H:%M:%S'` | Bash 执行（用于计算相对时间差） | 始终执行 |
| 5 | `git status --short` | Bash 执行 | 始终执行 |
| 6 | `git log --oneline -5` | Bash 执行 | 始终执行 |
| 7 | `.diwu/archive/` | 统计文件数 | 不存在则跳过 |

---

## 约束

- **纯读取**：不创建/修改/删除任何文件
- **快速**：目标 <2 秒完成全部聚合
- **不触发执行**：这是状态查看，不是启动 drun 循环
- **优雅降级**：任何数据源缺失时输出该模块为"不可用"而非报错退出
- **精确时间**：涉及相对时间的输出必须先执行 `date` 获取当前时间再与文件名/commit 时间戳做差值计算，**禁止凭记忆或目测估算**。格式规则：< 60min 显示「N 分钟前」；< 24h 显示「N 小时前」；≥ 24h 显示「N 天前」
