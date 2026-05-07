# Agents 速查表

> diwu-flow 内置三个核心 Agent，按默认路径自动发现（plugin.json 不声明 agents 字段）。
> 本文件仅提供快速定位，不承载 handoff 协议正文（见 `rules/handoff.md`）。

## Agent 总览

| Agent | 所在域 | 回交给谁 | 不做什么 |
|-------|--------|---------|---------|
| **explorer** | 只读调查 | drun（主代理）/ implementer（直修小 bug） | 不修改任何文件、不创建文件、不运行写操作命令 |
| **implementer** | 代码修改 | drun（主代理）/ verifier（S3 流水线） | 不做架构决策、不改 task 定义、不自审 Done |
| **verifier** | 独立验收 | drun（主代理） | 不信任实现者自述、不读 recording/ 推测事实、遇不确定输出 HUMAN_NEEDED |

## 派发决策速查

```
首次接触代码库？
├── 是 → explorer（调查报告 + 建议）
│
明确实现路径？
├── 是 → implementer（交接报告 + Acceptance 结果）
│
实施完成需验收？
└── 是 → verifier（验证报告 + PASS/FAIL）
```

## 默认参数

| 参数 | explorer | implementer | verifier |
|------|----------|-------------|----------|
| model | haiku | sonnet | （继承主代理） |
| tools | Read, Grep, Glob, LSP, WebSearch, WebFetch | Read, Grep, Glob, Edit, Write, Bash, LSP | Read, Grep, Glob, Bash |
| maxTurns | 50 | 100 | 50 |
| memory | true | true | true |
| 修改文件 | 禁止 | 自动接受 | 禁止 |

## 退化安全

任何 agent 失败时的退化路径：

```
verifier 失败 → 主代理自审（S1/S2）或人工 REVIEW
implementer 失败 → 诊断重试（3-Strike）或退化回 explorer 重分析
explorer 失败 → 主代理直接接手调查
```

> 完整交接协议见 `rules/handoff.md` §二~§四。
