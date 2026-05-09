# diwu-flow

**插件版本：0.1.0** | Claude Code Plugin 项目

## 系统分层地图

| 目录 | 定位 | 承载 | 不承载 |
|------|------|------|--------|
| `.doc/` | 设计文档真相源 | 架构解释、设计原理、源码仓结构规范 | 不重复规则内容 |
| `rules/` | 运行规则真相源（宪法级） | 必须遵守的协议、状态流转、handoff/verification/testing/task 规范 | 不承载设计解释 |
| `README.md` | 说明/导航文档 | 快速索引、何时看哪个文件 | 不新增规则、不覆盖真相源、不替代 `.doc/` |

### rules/ 通用性铁律

**rules/ 通过 /dinit 同步到任意目标项目，必须写成项目无关的宪法**。每句话都应适用于任何使用 diwu-flow 的项目，而非仅适用于 diwu-flow 插件自身开发。

| 禁止（diwu-flow 专属） | 替换为（通用表述） |
|------------------------|-------------------|
| 引用 `.claude-plugin/plugin.json` 作为版本号真值源 | 按项目类型的版本号真值源（package.json/pom.xml 等） |
| 描述三副本同步机制（`rules/`→`.claude/rules/`→`assets/`） | 此内容归 `.doc/` 或 `CLAUDE.md` |
| 写死具体 skill/command/agent 名称作为规则主语 | 用抽象角色名（任务编排者/执行引擎/验收方） |
| 引用 hooks/scripts/ 下具体 `.py` 文件名 | 用功能描述替代（"会话启动时自动注入"） |
| 硬编码 `.diwu/` 内部实现细节（dtask-state.json 字段、dloop 元数据结构） | 描述概念层约定，实现细节归 `.doc/` |
| "插件项目特例"章节（如 testing.md §四） | 移入 `.doc/` 或插件内部文档 |
| Command/Skill 命名长度约束（≤5 字符） | 此为 CC 插件设计约束，不属于通用规则 |

> 检查方法：改 rules/ 时自问——"如果目标是一个 Go 后端项目或 React 前端项目，这句话还有意义吗？"

### 六层架构

| 层 | 关键资产 | 回答的核心问题 |
|---|---------|--------------|
| L0 入口容器 | didea | 想法挂住 → 持久化 → 下游衔接 |
| L1 判断收束 | dpth/dref/dprd/ddoc | 值不值得做、怎么想清楚、收束成清单/PRD/文档 |
| L2 下游扩展 | architect/debugger | 技术审稿 gate / 异常诊断优先 |
| L3 协议层 | rules/handoff.md | dtask/drun 主编排边界、回交模型、Handoff Report |
| L4 规则真相源 | rules/ 体系(14文件) | 状态机、blocked_by、acceptance、verification 规范 |
| L5 表层能力 | Commands/Skills | drun 双入口、持久化策略、新增删减溶解标准 |
| 横切增强 | rules/testing.md | 测试策略跨越多层、幅度→验证方式映射 |

> 架构原则：Skills 为底（方法论），Commands 为壳（薄封装）；Skill frontmatter 零平台耦合（无 context/agent/model/hooks）；agents/ 和 skills/ 均为扁平单层目录，默认路径自动发现，plugin.json 不声明 agents 字段。

## 上位心智层

**少即是多，克制且清晰；具体胜于抽象；引导顺序即优先级。**

**三唯一框架**：进入任务前确认唯一主线目录、唯一运行入口、canonical。

**P-J-A 骨架**：现象（事实）→ 判断（依据）→ 动作（下一步）。违反此链的规则是空壳。

**不确定性门控**：直接做（改动小可预期）/ 先写最小规格（结果不清需交接）/ 先探索验证（依赖多落点不清）

**证据优先级**：L1 运行态 > L2 调用链 > L3 自动化断言 > L4 表面观察 > L5 间接推断。默认 L1-3 主判。

## 资产速查

### Skills (11)

| 分组 | Skill | 一句话 |
|------|-------|--------|
| 入口容器 | `didea` | 想法捕获与下游衔接 |
| 思考收束 | `dpth` `dref` `dprd` `ddoc` | 方向判断 / 需求细化 / PRD / 文档 |
| 任务闭环 | `dtask` `drun` | 任务定义 → 单任务执行 |
| 连续执行 | `dloop` | drun 薄壳循环（session/cron 双模式） |
| 观察纠偏 | `dstat` `dcorr` `drec` | 状态快照 / 纠偏恢复 / Session 记录 |

### Agents (5)

| Agent | 定位 | 核心约束 |
|-------|------|---------|
| explorer | 只读探索 | 不修改文件 |
| implementer | 代码实施 | 先读后写；JSON indent=2 |
| verifier | 独立验收 | 不允许 Edit/Write；不信任 implementer 自述 |
| architect | 技术审稿 | 不改代码；只审 dtask 定义域 |
| debugger | 异常调查 | 不直接修代码；诊断后回交修复链 |

> 故障隔离：任何非核心 agent 失败时退化回 explorer→implementer→verifier 闭环。

### Commands (13)

drun, dtask, dinit, dprd, ddoc, drec, dref, dcorr, dstat, dloop, dstop, didea, dpth

（dstop 和 dinit 为仅有的两个 command-only 特例，无对应 Skill。）

### 关键目录

| 目录 | 内容 |
|------|------|
| `commands/` | 13 个薄壳命令 |
| `skills/` | 11 个方法论 Skill（唯一真相源） |
| `agents/` | 5 个执行 Agent（默认路径自动发现） |
| `scripts/` | 共享脚本（common.py/dtask_transition/dloop/dstat/...） |
| `hooks/` | Hook 脚本（6 事件 / 10 业务脚本 + 1 wrapper） |
| `rules/` | 14 个参考规则文件 |
| `assets/` | /dinit 初始化模板 |
| `tests/` | 三级测试（L1 配置 / L2 脚本 / L3 一致性） |

## 行为铁律

### 实施类

- **Push 前必跑**：`pytest tests/` 全量回归通过后才可 commit & push
- **Rules 同步**：修改 `rules/` 后必须同步 `.claude/rules/` 和 `assets/dinit/assets/rules/` 两处模板
- **recording 更新**：每次 session 结束前必须写入 `.diwu/recording/`
- **时间戳**：写入 Session 标题前先跑 `date '+%Y-%m-%d %H:%M:%S'`，禁止手写
- **`.diwu/` 提交**：origin/main 持续追踪 `.diwu/`（含 `.claude/`）；公开仓库由 `drelease.sh` worktree 隔离发布 clean 版
- **CC 专属**：hooks/、`.claude-plugin/`、`assets/` 为 CC 专属内容

### 版本号

- 真相源：`.claude-plugin/plugin.json` 的 `version` 字段
- 变更时同步：`marketplace.json` + `install.sh` OpenCode stub

### 文件操作

- **先读后写**：修改已有文件前必须 Read；整文件重写必须先读完整文件；全新创建且确认不存在时可跳过
- **JSON 格式**：indent=2, ensure_ascii=False（禁止单行压缩）
- **原子替换优先**：优先 Edit 精确匹配；仅整文件重写用 Write
- **敏感目录谨慎**：`.diwu/` 和 `.claude/` 下修改需确认不破坏现有结构或丢失数据
- **Skill 验证**：修改 Skill 后验证 frontmatter YAML 合法性

## 公开版本发布流程

**发版前检查清单**：

| # | 检查项 | 方法 |
|---|--------|------|
| 1 | `pytest tests/` 全量通过 | `python3 -m pytest tests/ -q` |
| 2 | CHANGELOG.md 已追加新版本条目 | 人工确认 |
| 3 | 版本号已同步到三处 | plugin.json、marketplace.json、install.sh OpenCode stub |
| 4 | dloop runtime 已清空 | `python3 -c "import json; s=json.load(open('.diwu/dtask-state.json')); assert s.get('dloop') is None"` |

```bash
# 前置配置（只需一次）
git remote add public git@github.com:ssdiwu/diwu-flow.git

# 每次发布（确保 main 干净后）
./drelease.sh v{version} --push-public
# → 先推 origin/main（含 .diwu/）→ 创建临时 worktree 清理敏感文件 → 推送 clean 版到 public/main
```
