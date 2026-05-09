# 规则导航页

> 本文件是 `rules/` 的导航入口。按问题找到答案，再深入对应文件。
> **渐进式披露**：核心内容已迁移为按需加载的 Skill（见下方「对应 Skill」列），本目录保留作为参考（Read on demand）。

## 全局地图

```
                    ┌─ mindset.md (上位心智层)
                    │  三唯一 / P-J-A / 不确定性门控
                    │
    ┌── workflow.md   ├─ handoff.md (交接协议)
    │  阶段流转       │  启动仪式/回交模型/Agent约束/Plan→Dtask
    │                 │
    │                 ├─ testing.md (测试分层)
    │                 │  幅度→验证方式/补测试触发
    │                 │
    ├─ task.md         ├─ verification.md (证据体系)
    │  Persistent Task     │  L1-L5/Done判定/无法验证处理
    │                  │
    ├─ judgments.md     └─ templates.md (格式模板)
    │  判断锚点            BLOCKED/REVIEW/DECISION TRACE/Session/Handoff Report
    │
    ├─ session.md        ├─ pitfalls.md
    │  Session 结束       │  项目高频误判表
    │                  ├─ exceptions.md
    │                  └─ constraints.md
    ├─ file-layout.md      架构约束+命名约束
    └─ README.md          本导航页（你在这里）
```

## 按场景导航

| 你想做什么 | 去哪 | 关键章节 |
|-----------|------|---------|
| 开始新任务，确认三唯一 | `mindset.md` §三唯一框架 | 先确认主线目录、运行入口、canonical |
| 判断该直做还是先规划 | `mindset.md` §不确定性门控 | 三条件检查 |
| 写任务 acceptance | `task.md` §acceptance 格式规范 | GWT 格式 + Then 自检 |
| 派发子代理 / 接收回交 | `handoff.md` | 注入清单 + 回交报告模板 |
| 选择验证方式 / 补测试 | `testing.md` | 幅度→方式映射 + 豁免规则 |
| 判定 Done 需要什么证据 | `verification.md` | L1-L5 表格 + Done 矩阵 |
| 遇到阻塞 / 需人工介入 | `exceptions.md` | BLOCKED 判定 + 恢复流程 |
| 记录踩坑 / 识别误判 | `pitfalls.md` | Layer 2 高频表机制 |
| 输出标准格式 | `templates.md` | 按需选用对应模板 |
| 做判断决策 | `judgments.md` | 五阶段锚点索引 |
| 管理 Session 生命周期 | `session.md` | 时间戳铁律 / 3-Strike / Checkpoint |
| 了解文件放置 / 归档规则 | `file-layout.md` | .diwu/ / .doc/ / tests/ 结构 |
| 检查架构约束 | `constraints.md` | 六维约束 + 命名约束 |

## 完整文件列表

| 文件 | 行为 | 对应 Skill | 何时查阅 |
|------|------|-----------|---------|
| **mindset.md** | 上位心智层：三唯一框架、五问开工检查、不确定性门控 | *核心层内嵌* | Session 启动、开工检查时 |
| **handoff.md** | 子代理交接协议：启动仪式、回交模型、Agent 设计约束、Plan→Dtask 门控 | *新增* | 派发/接收子代理时 |
| **testing.md** | 测试分层策略：幅度→验证方式、补测试触发、测试-证据映射 | *新增* | 选验证方式、判是否需补测试 |
| **judgments.md** | 判断锚点索引（五阶段：启动/实施/验收/纠偏/handoff） | djudge | 需做判断决策时 |
| **task.md** | 任务状态机、acceptance 格式、dtask 结构、blocked_by、提交规范 | dtask | 写任务、改状态、处理依赖时 |
| **workflow.md** | 阶段流转：层级路线图、入口门控、跨阶段回退 | dtask | 规划任务、选推进方式时 |
| **session.md** | Session 结束规范：时间戳+踩坑+Stop hook 正则、3-Strike、Checkpoint | dsess + drecord | Session 开始、结束时 |
| **verification.md** | 证据优先级体系：L1-L5、Done 判定门槛、无法验证处理 | dtask + drun + dcorr | 选择证据等级、判定完成标准时 |
| **pitfalls.md** | 误判防护：Layer 2 项目高频表机制 / Layer 3 接口预留 | dcorr | SessionStart 自动注入（已实现）、归档聚合时 |
| **exceptions.md** | 异常处理与 BLOCKED 判定、阻塞恢复流程 | *参考文件* | 遇到阻塞、需要人工介入时 |
| **templates.md** | 格式模板：BLOCKED/REVIEW/DECISION TRACE/Session/Checkpoint/Handoff Report | drecord | 输出标准格式时 |
| **constraints.md** | 架构约束：六维约束设计 + 命名约束 + 规则回写约束 | *参考文件* | 设计新功能、定义约束时 |
| **file-layout.md** | 目标项目文件放置规则：.diwu/ / .doc/ / tests/ / rules/ | *参考文件* | 了解文件组织、归档、查历史 |

## 阅读顺序建议

### 首次使用

1. `mindset.md` → 理解上位心智层
2. `task.md` + `judgments.md` → 掌握任务语言和判断方法
3. `workflow.md` → 理解阶段流转和入口门控
4. `verification.md` + `templates.md` → 掌握验收标准

### 日常使用

- 遇到具体问题 → 按上表"按场景导航"直达目标文件
- 实施中遇到判断困境 → `judgments.md` 对应阶段查找锚点
- 需要输出标准格式 → `templates.md` 选用模板

## 规则约束级别

- **默认**：必须遵守的约束
- **[建议]**：推荐但不强制的约束
