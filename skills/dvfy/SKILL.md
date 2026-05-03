---
name: dvfy
version: "1.0"
type: index
description: "dvfy 已溶解——功能原子分散归入 dtask/drun/dcorr。本文件为历史索引。"
deprecated: true
migrated_to:
  - dtask (Done 判定矩阵)
  - drun (完成前四问 + 运行态验证方法)
  - dcorr (无法验证处理模板)
  - rules/verification.md (L1-L5 证据等级定义，被上述 skill 引用)
---

# dvfy (已溶解)

本 skill 的功能已分解迁移：

| 原功能 | 新位置 |
|--------|--------|
| L1-L5 五级证据表格 | `rules/verification.md` §L1-L5 (保持) |
| Done 判定矩阵 | `skills/dtask/SKILL.md` §Done 判定矩阵 |
| 完成前四问 | `skills/drun/SKILL.md` §Session 结束 |
| 无法验证处理模板 | `skills/dcorr/SKILL.md` §无法验证时的处理 |
| 运行态验证方法 | `skills/drun/SKILL.md` §运行态验证方法 |
| 独立验证 (verifier) | `agents/verifier.md` (已有, dvfy 原仅为引用) |

> 所有功能仍可用，只是不再作为独立 Skill 存在。证据等级定义 (L1-L5) 仍在 `rules/verification.md` 中。
