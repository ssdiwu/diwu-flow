# diwu-flow

**插件版本**：0.0.1

## 核心原则

- Skills 为底，Commands 为壳：所有方法论在 Skills 中，Commands 是薄封装
- 零平台耦合：Skill frontmatter 无平台专属字段（无 context/agent/model/allowed-tools/hooks）
- 扁平结构：agents/ 和 skills/ 均为单层目录，最大化平台兼容性
- 少即是多，克制且清晰：偏好简洁的设计和输出，排斥冗余
- 具体胜于抽象：示例是规则的执行锚点，抽象描述只是参考；规则与示例冲突时以示例为准
- 引导顺序即优先级：元规则和解释框架必须在被解释内容之前出现

## 上位心智层（核心不变量）

### 三唯一框架

进入任务前必须确认三件事：唯一主线目录、唯一运行入口、canonical（规范真相源）。未确认前不要默认当前目录/旧脚本就是主线。

### 现象→判断→动作骨架

所有规则都是这条链的具体实例。违反此链的规则是空壳。

```
现象：- 看到了什么（事实）
判断：- 得出什么结论（依据）
动作：- 下一步具体做什么
```

### 不确定性门控

| 路径 | 条件（满足任一） |
|------|------------------|
| **直接做** | 改动小 + 结果可预期 + 差异一句话说清 |
| **先写最小规格** | 结果不能说清 / 依赖外部 / 需稳定格式 / 需交接 |
| **先探索验证** | 外部依赖多 / 落点不清 / 回滚成本高 |

### 证据优先级摘要

L1 运行态 > L2 调用链 > L3 自动化断言 > L4 表面观察 > L5 间接推断。默认 L1-3 主判，仅 L5 不可宣称完成。

## Skill 与文件索引（渐进式披露）

按需加载 Skill，参考文件 Read on demand：

| 名称 | 类型 | 触发场景 |
|------|------|---------|
| `dtask` | Skill | 创建任务、管理 dtask、规划分解、提交规范 |
| `drun` | Skill | Session 启动/结束、任务选择、continuous_mode |
| `dcorr` | Skill | 退化信号检测、纠偏恢复、误判排查、四行重写 |
| `dvfy` | Skill | InReview/Done 判定、证据等级选择、验证充分性 |
| `djug` | Skill | 阶段边界决策、幅度判定、并行vs串行、超前实施 |
| `drec` | Skill | 写 session 记录、踩坑经验记录、时间戳规则 |
| `darc` | Skill | Task/Recording 归档、触发检测、验证清单 |
| `rules/exceptions.md` | 参考 | 异常处理与 BLOCKED 判定 |
| `rules/templates.md` | 参考 | BLOCKED/REVIEW/DECISION TRACE 格式模板 |
| `rules/file-layout.md` | 参考 | 目录结构与归档规则 |
| `rules/constraints.md` | 参考 | 五维约束设计方法论 |

> 插件开发专属约束见 `.claude/plugin-dev-notes.md`

## 项目结构

| 目录 | 说明 |
|------|------|
| `skills/` | 10 个 Skill（唯一真相源） |
| `agents/` | 10 个 Agent（扁平结构） |
| `commands/` | 8 个 Command（含交互指引协议） |
| `hooks/` | CC 专属 Hook 脚本 |
| `.claude-plugin/` | CC 插件声明（plugin.json） |
| `assets/dinit/assets/` | /dinit 模板资源 |
| `rules/` | 规则参考文件 |

## Skill v1.0 Frontmatter 规范

```yaml
---
name: {skill_name}
version: "1.0"
type: rule                             # rule | product
description: "..."
triggers:
  - "触发场景1"
keywords:
  - keyword
depends:
  - {依赖 skill}
effort: low|normal|high
argument-hint: "[参数提示]"
---
```

禁止在 Skill frontmatter 中添加：context、agent、model、allowed-tools、hooks。

## Command 规范

Command = Skill 触发器 + 交互封装。
- dinit/dadr：CC 专属厚命令（含完整编排逻辑）
- ddoc/dprd/dtask/ddemo/dcorr/drun：含交互指引协议的分步引导命令
- 所有 Command 正文包含判断锚点和正反边界例

## 行为铁律

**Push 前必跑**：`pytest tests/` 全量回归通过后才可 commit & push。
  覆盖：版本号同步、README 一致性、CLAUDE.md 格式（≤120行/无 @rules/）、skills/ 命令数匹配、JSON 合法性、py_compile、禁止推送目录。

**Rules 同步**：修改 `rules/` 下任何文件后，必须运行同步脚本将变更同步到 `assets/dinit/assets/rules/` 模板。

**时间戳规则**：写入 Session 标题前必须先运行 `date '+%Y-%m-%d %H:%M:%S'` 获取真实时间戳，禁止手写日期。

**recording 更新**：每次 session 结束前必须主动写入 `.diwu/recording/`，无论是否有 InProgress 任务。

- 修改 Skill 后必须验证 frontmatter YAML 合法性
- plugin.json 不声明 agents 字段（使用默认路径自动发现）
- CC 专属内容仅限 hooks/、.claude-plugin/、assets/
