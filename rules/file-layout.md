# 文件布局

> **规则约束级别说明**：本文件定义文件组织的核心规则。除非特别标注 `[建议]`，否则都是必须遵守的约束。
> **定位**：回答"目标项目里什么东西该放哪里"。不描述 diwu-flow 插件源码仓内部结构。

## .diwu/ 目录结构

```
.diwu/
├── CLAUDE.md                      # 全局 Agent 配置入口
├── dsettings.toml                 # 可调参数配置
├── dtask.toml                     # 当前任务列表（status 真相源）
├── dtask-state.toml               # runtime owner / dloop 元数据真相源
├── recording/                     # Session 进度记录目录
│   └── session-YYYY-MM-DD-HHMMSS.md
├── decisions.md                   # 设计决策记录（可选）
├── ideas/                        # 想法容器
├── archive/                       # 归档目录
│   ├── task_archive_YYYY-MM.json
│   ├── recording_YYYY-MM-DD.md
│   └── .last_archive_summary.json
├── checks/                        # 验证脚本目录
│   ├── smoke.sh
│   └── task_<id>_verify.sh
├── init.sh                        # 环境初始化脚本（可选）
└── rules/                         # 工作流规则（由初始化命令同步而来，详见 rules/README.md）
```

> 规则文件通过项目配置的注入机制加载到 Agent 上下文。具体注入方式因项目而异。

## tests/ 目录结构（测试资产）

```
tests/
├── level1/                  # 基础 smoke / 快照测试
├── level2/                  # 集成测试 / 脚本测试
├── level2_scripts/          # 脚本级集成测试（dloop/dstop/dstat 等）
├── level3/                  # 一致性 / 文档合规性测试
└── conftest.py              # pytest 入口
```

> repo-level 基线测试默认进入 `tests/`，项目基线检查脚本（如 smoke.sh）作为补充手段。

## 规则文件说明

完整规则清单与导航见 `rules/README.md`。

## 运行时文件说明

| 路径 | 用途 | 读写方 |
|------|------|--------|
| `.diwu/CLAUDE.md` | 全局配置、个人偏好、规则索引 | 共同维护 |
| `.diwu/dsettings.toml` | 可调参数配置 | 人工设置，Agent 读取 |
| `.diwu/dtask.toml` | 任务定义与 `status` 的真相源 | Agent 读写 |
| `.diwu/dtask-state.toml` | runtime owner / dloop 元数据真相源；不重复保存 task status | Agent 读写 |
| `.diwu/recording/` | Session 进度记录，每个 session 一个文件 | Agent 写 |
| `.diwu/decisions.md` | 重大设计决策记录（影响范围 ≥2 模块） | Agent 写 |
| `.diwu/archive/` | 归档目录（tasks + recordings + summary） | Agent 写 |

## 归档触发条件

| 归档目标 | 触发条件 | 阈值来源 |
|---------|---------|---------|
| task_archive_YYYY-MM.json | Done/Cancelled 任务数超阈值 | dsettings.toml `task_archive_limit`（默认 20）|
| recording_YYYY-MM-DD.md | session 文件数超阈值 | dsettings.toml `recording_file_limit`（默认 30）|

## 数据所有权

| 数据 | Source of Truth | 说明 |
|------|----------------|------|
| 任务定义与状态 | `.diwu/dtask.toml` | `title/description/acceptance/steps/status` 真相源 |
| runtime owner / dloop | `.diwu/dtask-state.toml` | 运行时元数据，不重复保存 task status |
| 模板文件 | 项目模板目录（因项目而异） | 初始化时复制到用户项目 |
