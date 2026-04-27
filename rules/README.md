# 规则文件速查索引

> 本目录包含 diwu-workflow 的核心工作流规则。规则按职责分离，每个文件 < 200 行符合有界同时性原则。
> **渐进式披露**：核心内容已迁移为按需加载的 Skill（见下方「对应 Skill」列），本目录保留作为参考（Read on demand）。

## 文件列表

| 文件 | 用途 | 对应 Skill | 何时查阅 |
|------|------|-----------|---------|
| **mindset.md** | 上位心智层：三唯一框架、五问开工检查、不确定性门控 | *核心层内嵌* | Session 启动、开工检查时 |
| **judgments.md** | 所有判断锚点集中管理（四段式：启动/实施/验收/纠偏） | djudge | 需要做判断决策时 |
| **task.md** | 任务状态机、acceptance 格式、dtask 结构、blocked_by 规范 | dtask | 写任务、改状态、处理依赖时 |
| **workflow.md** | 任务规划、任务实施、验证要求（Session 见 session.md） | dtask | 规划任务、实施任务、验证时 |
| **session.md** | Session 生命周期管理（启动/结束/continuous_mode/checkpoint） | dsess + drecord | Session 开始、结束时 |
| **verification.md** | 证据优先级体系（L1-L5）、Done 判定门槛、无法验证处理 | dverify | 选择证据等级、判定完成标准时 |
| **correction.md** | 纠偏体系：退化信号检测、四行重写、止损序列 | dcorr | 检测到退化信号、需要纠偏时 |
| **pitfalls.md** | 误判防护：Layer 1 泛化模式 / Layer 2 项目高频 / Layer 3 接口预留 | dcorr | Preflight 误判表预加载、归档聚合时 |
| **exceptions.md** | 异常处理与 BLOCKED 判定、阻塞恢复流程 | *参考文件* | 遇到阻塞、需要人工介入时 |
| **templates.md** | 格式模板与可调参数（BLOCKED/REVIEW/DECISION TRACE 等） | drecord | 输出标准格式、查配置参数时 |
| **file-layout.md** | .claude/ 目录结构、归档规则、查找历史 | *参考文件* | 了解文件组织、归档、查历史时 |
| **constraints.md** | 架构约束（五维约束设计） | *参考文件* | 设计新功能、定义约束时 |

## 阅读顺序建议

**首次使用**：
1. README.md（本文件）→ 了解整体结构
2. mindset.md → 理解上位心智层
3. task.md → 理解任务状态机
4. session.md + workflow.md → 掌握完整工作流
5. judgments.md → 学习判断决策方法

**日常使用**：
- 遇到具体问题时，根据上表"何时查阅"列快速定位
- 需要做判断时，优先查 judgments.md 找锚点
- 需要输出标准格式时，查 templates.md

## 规则约束级别

- **默认**：必须遵守的约束
- **[建议]**：推荐但不强制的约束
