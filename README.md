# diwu-flow

[![GitHub Stars](https://img.shields.io/github/stars/ssdiwu/diwu-flow?style=flat-square)](https://github.com/ssdiwu/diwu-flow)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-blue)](https://github.com/ssdiwu/diwu-flow)

多平台 AI 辅助开发方法论体系——**Skills 为底，Commands 为壳**。覆盖任务管理、判断锚点、纠偏恢复、需求分析、需求细化、归档聚合、想法捕获、产品思维等 **11 个核心 Skill** + **5 个执行 Agent**。六层架构：入口容器 → 判断收束 → 下游扩展 → 协议层 → 规则真相源 → 表层能力模型。（v0.1.0）

---

## v0.1.0 亮点

本轮完成了 5 个 PR 的六层架构全局落地：

- **L0 入口容器** — `/didea` 想法捕获，本地持久化，可选 GitHub issue 同步，下游衔接 dpth/dref/dprd/dtask
- **L1 判断收束** — `/dpth` 三模式产品思维判断（诊断/创始人/构建者），`/dref` 需求细化清单，`/dprd` 产品论证
- **L2 下游扩展** — architect（技术审稿 gate）和 debugger（异常诊断优先）接入执行链
- **L3 协议层** — `rules/handoff.md` 定义主编排边界、回交模型、Handoff Report 协议
- **L4 规则真相源** — 14 个 rules 文件重组，边界清晰，三副本同步
- **L5 表层能力** — `drun` 双入口模型（dtask 来源 + direct request），持久化四策略，`dloop` session/cron 双模式

> 全量测试 428 passed。完整变更见 [CHANGELOG.md](CHANGELOG.md)。

---

## 能力地图

### 六层架构总览

```
L0 入口容器    didea          想法挂住 → 持久化 → 下游衔接
L1 判断收束    dpth dref      值不值得做 → 怎么想清楚 → 收束成清单/PRD/文档
              dprd ddoc       
L2 下游扩展    architect      技术审稿 gate / 异常诊断与回交
              debugger        
L3 协议层      handoff.md     dtask↔drun 主编排边界、回交模型、Handoff Report
L4 规则真相源  rules/(14文件)  状态机契约、blocked_by、acceptance、verification 规范
L5 表层能力    Commands/Skills drun 双入口、持久化策略、新增/删减/溶解标准
横切增强      testing.md     测试分层策略、幅度→验证方式映射
```

### Skills（11）与 Commands（13）

所有方法论在 Skills 中，Commands 是薄封装。Skill frontmatter 零平台耦合（无 context/agent/model/hooks），可在任何工具链中独立加载。

| 分组 | Skill | Command | 一句话 |
|------|-------|---------|--------|
| 入口容器 | `didea` | `/didea` | 想法捕获——6 个动作（create/list/show/refine/archive/push）+ 下游衔接 |
| 思考收束 | `dpth` | `/dpth` | 产品思维——三模式路由（诊断/创始人/构建者），灵魂三问门控 |
| | `dref` | `/dref` | 需求细化——四维判断 + 场景收敛 → 可执行检查清单 |
| | `dprd` | `/dprd` | 产品论证——门控 + 框架内化 → PRD 文档 |
| | `ddoc` | `/ddoc` | 产品文档——正向(需求→文档) / 逆向(代码→文档) |
| 任务闭环 | `dtask` | `/dtask` | 任务管理——GWT 验收、状态机、blocked_by 依赖图 |
| | `drun` | `/drun` | 单任务执行器——Preflight 5 步 → 实施 → 验证 → 记录 |
| 连续执行 | `dloop` | `/dloop` `/dstop` | session/cron 双模式循环 |
| 观察纠偏 | `dstat` | `/dstat` | 项目状态只读快照 |
| | `dcorr` | `/dcorr` | 纠偏恢复——退化信号检测 + 四行重写 |
| | `drec` | `/drec` | Session 记录——踩坑四段式 + 原子 commit |

> `dstop` 和 `dinit` 为仅有的两个 command-only 特例（无对应 Skill）。完整 Skill 详情见 `skills/README.md`，完整 Command 列表见 `commands/README.md`。

### Agents（5）

Skills 派发的执行单元，默认路径自动发现。故障时退化回 explorer→implementer→verifier 闭环。

| Agent | 核心约束 |
|-------|---------|
| explorer | 只读，不修改文件 |
| implementer | 先读后写，JSON indent=2，唯一写权限角色 |
| verifier | 不允许 Edit/Write，不信任 implementer 自述 |
| architect | 不改代码，只审 dtask 定义域（≥3 步/API 变更/新增模块时介入） |
| debugger | 不直接修代码，诊断后回交修复链（acceptance 不符/3-Strike 失败时介入） |

### Hooks（6 事件键 / 10 业务脚本 + 1 wrapper）

所有 hook 经 `run_hook.py` 包装执行，区分 `strict`（阻断）和 `tolerant`（告警）模式。

| 事件 | 行为 |
|------|------|
| SessionStart | 写 scoped session ID + 注入 pitfalls |
| TaskCreated | 校验 dtask.json 合法性 |
| PreToolUse | Bash: 漂移检测 + 上下文监控 / ExitPlanMode: Plan→Dtask 门控 / Edit\|Write: 实施入口守卫 |
| TaskCompleted | 清 owner + dloop 追踪 |
| Stop | 续跑判定 + 归档检查 + recording 门控 |
| PreCompact | 压缩前 checkpoint 写入 |

---

## 快速开始

### 新项目

```bash
# 1. 安装
claude plugin add /path/to/diwu-flow

# 2. 初始化项目骨架
/dinit

# 3. 有想法？先挂住
/didea create --title "我的想法"

# 4. 做产品判断
/dpth                    # 方向判断：值不值得做
# 或 /dref               # 需求细化：具体要什么
# 或 /dprd               # 写完整 PRD

# 5. 规划与执行
/dtask "实现用户登录"      # 任务拆解（含 GWT acceptance）
/drun                     # 单任务执行
# 或
/dloop --max-tasks 5      # 连续执行多个任务

# 6. 查看状态
/dstat
```

> 最短路径：`/didea` 挂住 → `/dpth` 判断 → `/dtask` 拆任务 → `/dloop` 开始循环 → `/drec` 记录。

### 接手老项目

```bash
claude plugin add /path/to/diwu-flow
/dinit refresh             # 刷新规则，不破坏 .diwu/ 数据
/dstat                     # 查看当前状态
/drun                      # 自动恢复 InProgress 任务
```

### 安装说明

| 平台 | 命令 | 产物 |
|------|------|------|
| Claude Code | `claude plugin add <path>` | 11 Skill + 5 Agent + 13 Command + 6 Hook 事件 |
| Codex CLI | `./install.sh --platform codex` | Skills + Agents symlink 到 `~/.codex/` |
| OpenCode | `./install.sh --platform opencode` | Plugin + symlink 到 `.opencode/` |
| 卸载 | `./install.sh --uninstall [--dry-run]` | 清理 symlink（dry-run 仅预览） |

---

## 工作流核心

### 最短执行路径

`/didea` 捕获想法 → `/dpth` 方向判断 → `/dtask` 规划任务 → `/drun` 执行 → `/drec` 记录归档。

如果不需要方向和产品论证环节，可以 `/dtask` 直接规划后 `/drun` 执行。需要连续执行多个任务时，用 `/dloop` 代替 `/drun`。

### drun 双入口模型

`drun` 作为 **Task Contract Runner**，接受两种来源：

| 维度 | dtask 来源 | direct request 来源 |
|------|-----------|-------------------|
| 触发 | `/drun`（从 InSpec 任务池 claim） | 用户直接描述任务 |
| 流程 | 完整 Preflight → S1-S4 → closeout | 简化：快速判断 → 实施 → 验证 |
| 收尾 | release → Done/InReview + /drec | /drec（或命中 architect 条件时升级回 dtask） |

> 硬规则：一旦命中 architect 审查条件（API/字段契约变更 / >2000 行 / 新增模块），必须升级回 dtask 路径。

### 持久化四策略

| 策略 | 适用场景 |
|------|---------|
| `none` — 纯对话收口 | 一次性问答、简单确认 |
| `drec` — 只写 recording + commit | direct run 常规收尾 |
| `dtask` — 纳入任务体系 | 复杂任务、跨 session 继续 |
| `dtask + drec` — 最完整 | 重要功能、长期追踪 |

### 任务状态机

```
InDraft → InSpec → InProgress → InReview → Done
                 ↑ 遇阻塞回退   ↑ 失败返工
```

InDraft 任务 Agent 不会主动执行，必须人工确认为 InSpec。acceptance 用 GWT 格式（Given/When/Then）。完整状态转移规则见 `rules/task.md`。

---

## 配置与调优

运行时配置：`.diwu/dsettings.json`，修改后立即生效。完整说明见 [`.diwu/dsettings-guide.md`](.diwu/dsettings-guide.md)。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `continuous_mode` | `true` | 任务完成后是否自动续跑 |
| `review_limit` | `5` | 最大超前实施任务数 |
| `context_monitor_critical` | `50` | 工具调用数达此值自动存 checkpoint |
| `drift_detection.enabled` | `true` | 退化信号检测（走神/死循环/越界编辑） |
| `error_tracking.enabled` | `true` | 3-Strike 重试机制 |
| `subagent_concurrency` | `3` | 并行子代理最大数量 |
| `task_archive_threshold` | `20` | Done/Cancelled 任务数触发归档 |
| `recording_archive_threshold` | `30` | session 文件数触发归档 |

---

## 设计理念

AI 擅长执行，不擅长决策。**人负责决策，AI 负责操作**。基于 BDD（GWT 验收格式）、TDD（L1-L5 证据优先级体系）、SDD（dtask.json 结构化任务定义）和 DDD（dprd/ddoc 分域文档）四个实践，用强约束状态机控制流转——任意时刻只能处于一个明确状态，转移条件由规则定义，不依赖 AI 自我约束。

核心思维框架是**现象→判断→动作**：看到什么事实 → 得出什么结论 → 具体做什么。违反此链的规则是空壳，缺少此链的工作是空转。

---

## 仓库结构

```
diwu-flow/
├── .claude-plugin/
│   ├── plugin.json              # 插件声明（11 Skill + 13 Command，v0.1.0）
│   └── marketplace.json         # 发布市场元数据
├── skills/                      # 11 个方法论 Skill（唯一真相源）
├── commands/                    # 13 个薄壳 Command
├── agents/                      # 5 个执行 Agent（默认路径自动发现）
├── hooks/
│   ├── hooks.json               # 6 事件 / 10 业务脚本 + 1 wrapper 注册表
│   └── scripts/                 # Python hook 实现
├── scripts/                     # 共享脚本库
├── rules/                       # 14 个运行规则文件（/dinit 同步到目标项目）
├── assets/dinit/                # /dinit 初始化模板
├── tests/                       # 三级测试（428 passed）
├── .doc/                        # 设计文档真相源
├── install.sh                   # 多平台安装脚本
├── drelease.sh                  # 公开版本发布脚本
└── README.md                    # 本文件
```

---

## 多平台兼容性

| 能力 | Claude Code | Codex CLI | OpenCode |
|------|------------|-----------|----------|
| 11 Skills | plugin.json 声明 | symlink SKILL.md | symlink SKILL.md |
| 5 Agents | 默认路径自动发现 | symlink .md | symlink .md |
| 13 Commands | Slash Commands | 不支持 | 声明式索引(.md) |
| 6 Hook 事件 | hooks.json | 不支持 | v1 不移植 |
| Python 脚本 | `CLAUDE_PLUGIN_ROOT` | 不支持 | 不支持 |

---

## Version

v0.1.0 — 六层架构全局落地：rules 真相源重构 → architect/debugger 接入 → dpth/dref/dprd 产品思维层 → didea 入口容器 → 说明层重写 + dloop cron 模式。428 tests passed。详见 [CHANGELOG.md](CHANGELOG.md)。

## License

[MIT](LICENSE)

## 贡献者

| 贡献 | 贡献者 |
|------|--------|
| 核心架构 / 全部 Skills & Commands & Agents | [ssdiwu](https://github.com/ssdiwu) |
| dref Skill（需求细化清单方法论） | [RexYoung00](https://github.com/RexYoung00) |
