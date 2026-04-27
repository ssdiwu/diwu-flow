# 文件布局

> **规则约束级别说明**：本文件定义文件组织的核心规则。除非特别标注 `[建议]`，否则都是必须遵守的约束。

## .diwu/ 目录结构

```
.diu/
├── CLAUDE.md                      # 全局 Agent 配置入口
├── dsettings.json                  # 可调参数配置
├── dtask                      # 当前任务列表
├── recording/                     # Session 进度记录目录
│   └── session-YYYY-MM-DD-HHMMSS.md
├── decisions.md                   # 设计决策记录（可选）
├── archive/                       # 归档目录
│   ├── task_archive_YYYY-MM.json
│   ├── recording_YYYY-MM-DD.md
│   └── .last_archive_summary.json
├── checks/                        # 验证脚本目录
│   ├── smoke.sh
│   └── task_<id>_verify.sh
├── init.sh                        # 环境初始化脚本（可选）
└── rules/                         # 工作流规则（13 文件）
    ├── README.md                  # 规则速查索引
    ├── mindset.md                 # 上位心智层（独立注入，非自动加载）
    ├── judgments.md               # 判断锚点（四段式：启动/实施/验收/纠偏）
    ├── task.md                    # 任务状态机、acceptance、dtask 结构
    ├── workflow.md                # 任务规划、实施、验证（Session 见 session.md）
    ├── session.md                 # Session 生命周期管理
    ├── verification.md            # 证据优先级体系（L1-L5）
    ├── correction.md              # 纠偏体系（退化信号→止损动作）
    ├── pitfalls.md                # 误判防护（三层：泛化/项目/接口）
    ├── exceptions.md              # 异常处理与 BLOCKED 判定
    ├── templates.md               # 格式模板与可调参数
    ├── file-layout.md             # 本文件：目录结构与归档规则
    └── constraints.md             # 架构约束（五维约束设计）
```

> 规则文件由插件 UserPromptSubmit hook 注入。**mindset.md 为独立注入**（由 UserPromptSubmit hook 单独读取注入，不随 rules/ 目录批量加载）。

## .doc/ 目录结构（SDD 规范产物）

```
.doc/
├── [domain 或分层文件]   # 见 /diwu-doc
└── adr/                  # 架构决策记录，见 /diwu-adr
    └── ADR-NNN-kebab-case-title.md
```

## 规则文件说明

| 路径 | 用途 | 读写方 |
|------|------|--------|
| `rules/mindset.md` | 上位心智层：三唯一框架、五问开工、不确定性门控、三层工程论 | Agent 读（hook 独立注入） |
| `rules/judgments.md` | 全部判断锚点：按阶段索引（启动/实施/验收/纠偏）+ 入口门控 | Agent 读 |
| `rules/task.md` | 任务状态机、GWT acceptance 格式、dtask 结构、blocked_by 规范 | Agent 读写 |
| `rules/workflow.md` | 任务规划、任务实施、验证要求（不含 Session 生命周期） | Agent 读 |
| `rules/session.md` | Session 启动（Step 1-5）、任务选择、continuous_mode、Session 结束 | Agent 读 |
| `rules/verification.md` | L1-L5 证据优先级、Done 判定门槛、无法验证处理规范 | Agent 读 |
| `rules/correction.md` | 纠偏体系：退化信号检测、四行重写、止损序列、与 BLOCKED 边界 | Agent 读 |
| `rules/pitfalls.md` | 误判防护：Layer 1 泛化模式 / Layer 2 项目高频 / Layer 3 接口预留 | Agent 读 |
| `rules/exceptions.md` | 异常处理、BLOCKED 判定锚点、阻塞恢复流程 | Agent 读 |
| `rules/templates.md` | BLOCKED/REVIEW/DECISION TRACE 格式、最小规格模板、可调参数 | Agent 读 |
| `rules/constraints.md` | 架构约束（五维）、版本号语义化、Degradation Paths | Agent 读 |
| `rules/README.md` | 规则速查索引、阅读顺序建议 | Agent 读 |

## 运行时文件说明

| 路径 | 用途 | 读写方 |
|------|------|--------|
| `.diwu/CLAUDE.md` | 全局配置、个人偏好、规则索引 | 共同维护 |
| `.diwu/dsettings.json` | 可调参数配置 | 人工设置，Agent 读取 |
| `.diwu/dtask.json` | 当前所有任务的状态和内容 | Agent 读写 |
| `.diwu/recording/` | Session 进度记录，每个 session 一个文件 | Agent 写 |
| `.diwu/decisions.md` | 重大设计决策记录（影响范围 ≥2 模块） | Agent 写 |
| `.diwu/archive/` | 归档目录（tasks + recordings + summary） | Agent 写 |
| `.diwu/checks/smoke.sh` | 基线环境验证 | Agent 提供，人工确认 |
| `.diwu/checks/task_<id>_verify.sh` | 任务专属验证脚本 | Agent 创建执行 |
| `.diwu/init.sh` | 开发环境初始化 | 讨论后 Agent 实施 |

## 归档触发条件

| 归档目标 | 触发条件 | 阈值来源 |
|---------|---------|---------|
| task_archive_YYYY-MM.json | Done/Cancelled 任务数超阈值 | dsettings.json `task_archive_threshold`（默认 20）|
| recording_YYYY-MM-DD.md | session 文件数超阈值 | dsettings.json `recording_archive_threshold`（默认 50）|

## 数据所有权

| 数据 | Source of Truth | 说明 |
|------|----------------|------|
| 插件元数据 | `.claude-plugin/plugin.json` | 版本、命令列表 |
| 规则文件列表 | `assets/dinit/assets/rules-manifest.json` | `/dinit` 按 `rules` 字段复制 |
| 模板文件 | `assets/dinit/assets/*.template` | `/dinit` 复制到用户项目 |
