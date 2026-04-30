---
description: 记录架构决策（ADR），输出到 .doc/adr/ 目录
argument-hint: [决策描述（可选）]
allowed-tools: Read, Write, Glob, Bash
effort: medium
---

# /dadr — 架构决策记录

> 脚本：`python3 scripts/dadr.py <子命令> --cwd <项目根目录>`

## 子命令

| 命令 | 说明 |
|------|------|
| `next-number` | 获取下一个 ADR 编号（扫描现有 ADR-*.md 取 max+1） |
| `create --title <标题> [--number N] [--status S]` | 创建 ADR 骨架文件 + 更新 README 索引。T11: README 缺失时自动重建 |
| `update-status --number N --status <S>` | 更新已有 ADR 的 Status 行 + 同步 README |

## AI 保留步骤

脚本只处理机械操作（编号分配、文件骨架、索引维护）。以下步骤仍由 AI 执行：

1. **Step 1-2**：接收决策描述 → 澄清问题（备选方案、约束、取舍）
2. **Step 4 内容撰写**：Context 具体数据化 / Options 技术风险量化 / Decision 决策理由 / Consequences 触发条件

> **文件操作安全（R1）**：修改已有文件前先 Read 当前内容；整文件重写先 Read 完整文件；新建确认不存在后再 Write。

## 边界情况

更新已有 ADR 状态（如 Proposed → Accepted）：用 `update-status` 子命令。
