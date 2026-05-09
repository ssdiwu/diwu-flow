# diwu-flow

**插件版本：0.1.0** | Claude Code Plugin 项目

## 文档三边界

| 目录 | 定位 | 读它的人 |
|------|------|---------|
| `rules/` | 运行规则（通用宪法） | 使用 diwu-flow 的**任意项目** — 通过 /dinit 同步 |
| `.doc/` | 设计原理（为什么这么设计） | 改 diwu-flow 源码时需理解设计决策 |
| `CLAUDE.md` | 操作手册（怎么开发/维护本插件） | 改 diwu-flow 源码的 AI |

> **rules/ 通用性铁律**：rules/ 同步到任意目标项目，必须写成项目无关。改 rules/ 时自问——"如果目标是 Go 后端或 React 前端，这句还有意义吗？" 插件专属实现细节不进 rules/。

## 系统分层地图

| 层 | 关键资产 | 职责 |
|---|---------|------|
| L0 入口容器 | didea | 想法挂住、本地持久化、下游衔接 |
| L1 判断收束 | dpth/dref/dprd/ddoc | 方向判断、需求细化、PRD 论证、产品文档 |
| L2 下游扩展 | architect/debugger | 技术审稿 gate、异常诊断与回交 |
| L3 协议层 | rules/handoff.md | dtask/drun 主编排边界、回交模型、Handoff Report 协议 |
| L4 规则真相源 | rules/ | 状态机契约、blocked_by、acceptance、verification 规范 |
| L5 表层能力 | Commands/Skills | drun 双入口、持久化策略、新增/删减/溶解标准 |
| 横切增强 | rules/testing.md | 测试分层策略、幅度→验证方式映射 |

> 架构原则：Skills 为底，Commands 为壳。Skill frontmatter 零平台耦合。agents/ 和 skills/ 扁平单层，默认路径自动发现，plugin.json 不声明 agents。

## 资产速查

### Skills (11)

| 分组 | Skill |
|------|-------|
| 入口容器 | `didea` |
| 思考收束 | `dpth` `dref` `dprd` `ddoc` |
| 任务闭环 | `dtask` `drun` |
| 连续执行 | `dloop` |
| 观察纠偏 | `dstat` `dcorr` `drec` |

### Agents (5)

| Agent | 核心约束 |
|-------|---------|
| explorer | 只读，不修改文件 |
| implementer | 先读后写，JSON indent=2，唯一写权限角色 |
| verifier | 不允许 Edit/Write，不信任 implementer 自述 |
| architect | 不改代码，只审 dtask 定义域 |
| debugger | 不直接修代码，诊断后回交修复链 |

> 故障隔离：任何非核心 agent 失败时退化回 explorer→implementer→verifier 闭环。

### Commands (13)

`drun dtask dinit dprd ddoc drec dref dcorr dstat dloop dstop didea dpth`

（dstop 和 dinit 为仅有的两个 command-only 特例，无对应 Skill。）

### 关键目录

| 目录 | 内容 |
|------|------|
| `commands/` | 13 个薄壳命令 |
| `skills/` | 11 个方法论 Skill（唯一真相源） |
| `agents/` | 5 个执行 Agent |
| `scripts/` | 共享脚本（common.py/dtask_transition/dloop/dstat/...） |
| `hooks/scripts/` | 10 业务脚本 + 1 wrapper（run_hook.py） |
| `rules/` | 14 个规则文件 |
| `assets/` | /dinit 初始化模板 |
| `tests/` | 三级测试（L1 配置 / L2 脚本 / L3 一致性） |
| `.doc/` | 设计文档真相源 |

## 开发铁律

### 文件操作

- **先读后写**：修改已有文件前必须 Read；整文件重写必须先读完整文件；全新创建且确认不存在时可跳过
- **JSON 格式**：indent=2, ensure_ascii=False（禁止单行压缩）
- **原子替换优先**：优先 Edit 精确匹配；仅整文件重写用 Write
- **Skill 验证**：修改 Skill 后验证 frontmatter YAML 合法性

### 变更传播

- **Rules 同步**：修改 `rules/` 后必须同步 `.claude/rules/` 和 `assets/dinit/assets/rules/` 两处模板
- **版本号同步**：以 `.claude-plugin/plugin.json` 为真值源；变更时同步 `marketplace.json` + `install.sh`
- **CHANGELOG 追加**：功能性变更（非 typo/格式修正）完成后立即追加到 `CHANGELOG.md` 当前未发布版本条目下；发版时只需最终确认无遗漏
- **recording 更新**：每次 session 结束前写入 `.diwu/recording/`
- **时间戳**：写 Session 标题前先跑 `date '+%Y-%m-%d %H:%M:%S'`，禁止手写
- **`.diwu/` 提交**：origin/main 持续追踪 `.diwu/`（含 `.claude/`）；公开仓库由 `drelease.sh` worktree 隔离发布 clean 版

### 质量门控

- **Push 前必跑**：`pytest tests/` 全量回归通过后才可 commit & push
- **修改 rules/ 后**：三副本 diff 一致 + `test_doc_consistency` 通过

## 发版流程

**检查清单**：

| # | 检查项 | 方法 |
|---|--------|------|
| 1 | `pytest tests/` 全量通过 | `python3 -m pytest tests/ -q` |
| 2 | CHANGELOG.md 条目完整无遗漏 | 最终确认（日常已持续追加） |
| 3 | 版本号已同步到三处 | plugin.json、marketplace.json、install.sh |
| 4 | dloop runtime 已清空 | `python3 -c "import json; s=json.load(open('.diwu/dtask-state.json')); assert s.get('dloop') is None"` |

```bash
# 前置配置（只需一次）
git remote add public git@github.com:ssdiwu/diwu-flow.git

# 每次发布
./drelease.sh v{version} --push-public
```
