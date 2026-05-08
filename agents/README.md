# Agents 速查表

> diwu-flow 内置五个 Agent，按默认路径自动发现（plugin.json 不声明 agents 字段）。
> 本文件仅提供快速定位，不承载 handoff 协议正文（见 `rules/handoff.md`）。

## Agent 总览

| Agent | 所在域 | 回交给谁 | 不做什么 |
|-------|--------|---------|---------|
| **explorer** | 只读调查 | drun（主代理）/ implementer（直修小 bug） | 不修改任何文件、不创建文件、不运行写操作命令 |
| **implementer** | 代码修改 | drun（主代理）/ verifier（S3 流水线） | 不做架构决策、不改 task 定义、不自审 Done |
| **verifier** | 独立验收 | drun（主代理） | 不信任实现者自述、不读 recording/ 推测事实、遇不确定输出 HUMAN_NEEDED |
| **architect** | 技术审稿（dtask 定义域） | dtask（主代理） | 不改代码、不做产品判断（不替 dprd）、不替 ddoc、不进入 drun 主循环 |
| **debugger** | 异常调查（drun 执行域） | implementer → verifier（诊断后回交修复链） | 不直接修代码、不替 dcorr 做方法论纠偏、不自审 Done |

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

遇到异常排查场景？（bug/工具失败3-Strike/行为不符）
└── 是 → debugger（诊断报告 + 根因假设）→ implementer → verifier
```

## 默认参数

| 参数 | explorer | implementer | verifier | architect | debugger |
|------|----------|-------------|----------|-----------|----------|
| model | haiku | sonnet | （继承主代理） | sonnet | sonnet |
| tools | Read, Grep, Glob, LSP, WebSearch, WebFetch | Read, Grep, Glob, Edit, Write, Bash, LSP | Read, Grep, Glob, Bash | Read, Grep, Glob, LSP, WebSearch, WebFetch | Read, Grep, Glob, Bash, LSP |
| maxTurns | 50 | 100 | 50 | 50 | 50 |
| memory | true | true | true | true | true |
| 修改文件 | 禁止 | 自动接受 | 禁止 | 禁止 | 禁止 |

## 退化安全

任何 agent 失败时的退化路径：

```
verifier 失败 → 主代理自审（S1/S2）或人工 REVIEW
implementer 失败 → 诊断重试（3-Strike）或退化回 explorer 重分析
explorer 失败 → 主代理直接接手调查
debugger 失败 → 退化回 explorer 重分析或升级人工
architect 失败 → 退回 InDraft 重新设计或跳过审稿（小幅度变更）
```

> 完整交接协议见 `rules/handoff.md` §二~§四。
