# Commands 导航

> diwu-flow 的 13 个用户命令入口，每个 Command 是对应 Skill 的**薄壳封装**。
> 完整列表以 `.claude-plugin/plugin.json` 为真值来源。

## Command 总览（13）

| Command | 对应 Skill | 一句话定位 | 无独立 Skill？ |
|---------|-----------|-----------|---------------|
| `/didea` | didea | 想法捕获容器——挂住灵感并连接下游 | — |
| `/dpth` | dpth | 产品思维协作——方向判断与立场结论 | — |
| `/dref` | dref | 需求细化清单——洞察性反问→可执行检查清单 | — |
| `/dprd` | dprd | 产品需求分析——灵魂三问门控+PRD 产出 | — |
| `/ddoc` | ddoc | 产品文档——正向/逆向/ADR 三种模式 | — |
| `/dtask` | dtask | 任务规划——生成/管理 dtask.json 任务列表 | — |
| `/drun` | drun | 单任务执行——Preflight → 实施 → 验证 → 记录 | — |
| `/dloop` | dloop | 连续循环——while(未停止){ /drun } | — |
| `/dstop` | dloop | 停止连续循环 | **是** |
| `/dinit` | （内嵌脚本） | 项目初始化或刷新骨架 | **是** |
| `/drec` | drec | Session 记录写入与归档 | — |
| `/dcorr` | dcorr | 纠偏恢复协议——退化检测+四行重写 | — |
| `/dstat` | dstat | 项目状态只读聚合——任务/Session/决策/Git | — |

## 薄壳原则

每个 Command：
- **不含**任何方法论逻辑（方法论在对应 Skill 中）
- 负责：参数透传 + 交互增强 + 指向 SKILL.md
- 总行数 ≤ 40 行（含 frontmatter）
- 底部固定指向 `skills/{name}/SKILL.md` 的完整规范链接

## Command-only 特例

两个 Command 没有**对应的独立 SKILL.md**：

| Command | 原因 |
|---------|------|
| `/dstop` | 逻辑内嵌于 `scripts/dloop.py stop` 和 `skills/dloop/SKILL.md` |
| `/dinit` | 逻辑内嵌于 `scripts/dinit.py`，是环境初始化脚本而非方法论 |

> 无 Command 机制的平台可直调 Skills。
