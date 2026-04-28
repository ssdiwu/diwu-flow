# diwu-flow

多平台方法论体系——Skills 为底，Commands 为壳。

## 定位

diwu-flow 是一套完整的 AI 辅助开发方法论，覆盖任务管理、验证证据、判断锚点、纠偏恢复、需求分析等 10 个核心 Skill。设计目标是在 **Claude Code**、**Codex CLI**、**OpenCode** 等多个 AI 编程工具平台上均可使用。

## 架构

```
┌─────────────────────────────────────────────┐
│  用户交互层（Commands）                       │
│  /drun  /dtask  /dinit  /dprd  ...          │  ← CC / OpenCode
├─────────────────────────────────────────────┤
│  方法论层（Skills）—— 唯一真相源              │
│  drun  dtask  dvfy  djug  dcorr             │  ← 所有平台可用
│  dprd  drec  darc  ddoc  ddemo              │
├─────────────────────────────────────────────┤
│  执行层（Agents）                            │
│  explorer  implementer  verifier             │
│  backend-arch  frontend-arch  ...           │
├─────────────────────────────────────────────┤
│  平台增强层（CC 专属）                        │
│  hooks/  plugin.json  assets/               │  ← 仅 CC
└─────────────────────────────────────────────┘
```

## 核心原则

- **Skills 为底**：所有方法论内容在 Skills 中，任何平台可直接调用
- **Commands 为壳**：薄封装层，仅在有 Command 机制的平台提供增强交互
- **零平台耦合**：Skill frontmatter 无平台专属字段，可在任何工具中加载

## 快速开始

### Claude Code（推荐）

本项目即标准 CC 插件。安装后 10 个 Skill、10 个 Agent、8 个 Command 自动可用。

### Codex CLI

```bash
./install.sh --platform codex
```

Skills 通过 symlink 映射到 `~/.codex/skills/`，Agent 映射到 `~/.codex/agents/`。

### OpenCode

```bash
./install.sh --platform opencode
```

创建 `.opencode/plugins/diwu-flow.ts` 插件入口 + Skills/Agents symlink。

### 全平台安装

```bash
./install.sh --platform all
```

## 10 个 Skills

| Skill | 名称 | 类型 | 说明 |
|-------|------|------|------|
| drun | 自动执行引擎 | rule | Preflight → 选任务 → 实施 → 验证 → 循环 |
| dtask | 任务管理 | rule | 状态机、GWT 验收、task.json、规划分解 |
| dvfy | 验证证据 | rule | L1-L5 五级证据、Done 判定门槛矩阵 |
| djug | 判断锚点 | rule | 四段式判断（启动/实施/验收/纠偏） |
| dcorr | 纠偏恢复 | rule | 退化信号检测、四行重写 |
| dprd | 需求分析 | product | 竞品分析、迭代层次、方案对比、约束发现 |
| drec | 记录写入 | rule | Session 记录、踩坑经验格式 |
| darc | 归档管理 | rule | Task/Recording 归档触发与执行 |
| ddoc | 文档生成 | rule | 结构化文档输出模板 |
| ddemo | Demo 验证 | rule | 能力不确定性验证与 PoC |

## 8 个 Commands

| Command | 对应 Skill | 说明 |
|---------|-----------|------|
| `/drun` | drun | 自动执行引擎（auto/step 模式） |
| `/dtask` | dtask | 任务规划向导 |
| `/dinit` | — | CC 专属初始化编排器 |
| `/dprd` | dprd | PRD 需求分析 |
| `/dadr` | — | ADR 架构决策记录 |
| `/ddoc` | ddoc | 文档生成器 |
| `/ddemo` | ddemo | Demo 验证 |
| `/dcorr` | dcorr | 纠偏诊断 |

## 10 个 Agents

**核心（3 个）**: explorer / implementer / verifier

**领域专家（7 个）**: backend-architect / frontend-architect / devops-architect / ui-designer / api-tester / performance-optimizer / legal-compliance

## 兼容性

| 能力 | Claude Code | Codex CLI | OpenCode |
|------|------------|-----------|----------|
| 10 Skills（完整方法论） | plugin.json | symlink | symlink + Plugin |
| 10 Agents | plugin.json | symlink | symlink |
| 8 Commands | Slash Commands | ❌ | 声明式索引（Plugin + Command 映射） |
| Hooks | 6 核心 | ❌ | v1 不移植 |

## 版本

v1.0.0 — 初始版本，从 diwu-workflow v0.10.x 迁移重构。

## License

MIT
