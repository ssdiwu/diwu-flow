---
description: 将功能描述转化为 dtask 任务列表，支持澄清问题、质量检查、三视角审查
argument-hint: [功能描述（可选）]
allowed-tools: Read, Write, Edit, Glob
effort: high
---

# /dtask — 任务规划

## Step 1：接收功能描述

若用户在命令参数中提供了内容，先做上下文检查：
- 回顾当前对话，AI 是否刚提出了一个待回答的问题？
- 如果是，且参数内容像是对该问题的回答（而非功能描述）：
  - 从当前对话上下文中提取用户真正想规划的功能描述
  - 直接以提取到的功能描述进入 Step 1.5，无需再次确认
- 否则，直接以参数内容进入 Step 1.5

若用户未提供参数，询问：想要实现什么功能？

**示例锚点**：

正例（参数是对话回复 → 从上下文提取功能描述）：
- 上下文：AI 刚问"两个文件一起改，还是分开？"
- 参数："分开，你可以用两个子代理完成任务"
- 结论：提取上下文功能描述（修改 ddemo.md + 修改 dprd.md），直接进入 Step 1.5

反例（参数是功能描述 → 直接进入 Step 1.5）：
- 上下文：无特定待回答问题
- 参数："修改 ddemo.md 和 dprd.md，增加工具链联动"
- 结论：直接以参数内容进入 Step 1.5

边界例（参数既是回答也含功能描述）：
- 上下文：AI 刚问"要不要加示例？"
- 参数："确认。然后还要规划一个任务：没有主动更新 recording/"
- 结论：提取功能描述（规划 recording/ 主动更新任务），直接进入 Step 1.5

## Step 1.5：示范（先看目标产物）

生成任务前，先参考以下完整示例的思维粒度：

```json
{
  "id": 3,
  "title": "实现邮件验证码发送",
  "description": "用户注册后需要验证邮箱。调用 SMTP 服务发送 6 位验证码，验证码有效期 10 分钟，存储在 Redis 中；SMTP 不可用时必须返回明确错误而非静默失败。",
  "acceptance": [
    "Given 新用户完成注册表单提交 When 系统调用 sendVerification(email) Then Redis 中存在 key=verify:{email}，value=6位数字，TTL=600s",
    "Given SMTP 服务不可用 When 调用 sendVerification() Then 抛出 EmailServiceError，不写入 Redis",
    "Given 同一邮箱 10 分钟内重复请求 When 调用 sendVerification() Then 覆盖旧验证码，重置 TTL"
  ],
  "steps": [
    "1. [锁定] 在 /absolute/path/to/project/src/services/email.ts 实现 sendVerification(email: string): Promise<void>，使用 nodemailer 库",
    "2. [建议] 在 /absolute/path/to/project/src/lib/redis.ts 添加 setVerifyCode(email, code, ttl) 方法",
    "3. 凭据见 /absolute/path/to/project/doc/runbook.md §2.1（SMTP 配置）",
    "4. 运行 /absolute/path/to/project/.claude/checks/task_3_verify.sh 验证"
  ],
  "files_modified": [
    "/absolute/path/to/project/src/services/email.ts",
    "/absolute/path/to/project/src/lib/redis.ts"
  ],
  "category": "functional",
  "blocked_by": [2],
  "status": "InDraft"
}
```

说明：`/absolute/path/to/project` 为占位路径，需替换为真实绝对路径。

思维粒度：`title` 一句话、`acceptance` Given 具体路径/函数、Then 可断言、`steps` 真实绝对路径。

## Step 2：澄清问题

提出 3-4 个聚焦问题（每次一个维度）：
- **目标**：解决什么问题？
- **核心操作**：关键操作有哪些？
- **边界**：明确不做什么？
- **成功标准**：怎么算完成？
- **具体例子**：典型操作的完整例子（推导 Given/When/Then）

## Step 2.5：读取文档上下文（如存在）

读取以下 README（不存在则跳过），提取相关信息用于生成 acceptance：

- `.doc/prd/README.md` — 列格式：`| 文件 | 摘要 | demos | 状态(draft|review|approved) |`
  → 了解已有 PRD 的功能背景
- `.doc/demo/README.md` — 列格式：`| 文件 | 摘要 | 通过标准摘要 | 状态(pending|passed|failed) |`
  → 提取相关 Demo 的通过标准，作为 acceptance 量化依据（通过标准格式：`指标 > 阈值`，多条用 `;` 分隔）

## Step 3：确定新任务 ID

写入前必须：
1. 读取 `.diwu/dtask` 中所有任务的最大 `id`
2. 用 glob 匹配读取 `.claude/task_archive*.json` 中所有任务的最大 `id`
3. 取两者最大值 + 1 作为新任务起始 id（严禁 id 复用）

## Step 4：生成并写入任务

根据澄清结果生成任务列表，追加到 `.diwu/dtask`。
每个任务必须包含所有字段，字段粒度参照 Step 1.5 示例。

**files_modified 自动提取**：从 steps 中提取所有绝对路径（以 `/` 开头且包含文件扩展名），写入 files_modified 数组，用于并行冲突检测。

**灰色地带追问**：对每个任务的 steps，逐条判断是否需要标注 [锁定] 或 [建议]：
- **[锁定]**：关键技术选型、架构决策、外部依赖选择（如"使用 PostgreSQL"、"调用 Stripe API"）
- **[建议]**：实现细节、代码组织方式、可替换的工具函数（如"提取 validateEmail 工具函数"、"使用 lodash.debounce"）
- 无标注：中性步骤（如"运行验证脚本"、"凭据见文档"）

边界情况：
- `.diwu/dtask` 不存在：创建 `{"tasks": []}` 再追加
- `.claude/` 目录不存在：先创建目录
- 存在明显技术未知量：先生成 `category: infra` 的 Spike 任务（acceptance 为"输出调研结论文档"），再生成依赖它的实施任务

## Step 5：任务质量检查

逐条检查每个新生成的任务：
- acceptance 是否使用 Given/When/Then 格式（functional/ui/bugfix 类必须）
- acceptance 是否可验证（无"works correctly"等模糊描述）
- steps 是否自包含（外部凭据有来源路径，无隐式上下文依赖）
- 粒度是否合理（预估是否超过 2000 行，如是提示拆分）
- 是否垂直切片（端到端打通，非按技术层横切）
- **标注合理性**：关键技术选型是否标注了 [锁定]，纯实现细节是否标注了 [建议]

**acceptance 坏→好对比**：
- ❌ `Given 用户登录 When 提交表单 Then 登录成功`（Then 无法断言，Given 无具体状态）
- ✓ `Given 新用户完成注册表单提交 When 系统调用 sendVerification(email) Then Redis 中存在 key=verify:{email}，value=6位数字，TTL=600s`

发现问题时：列出具体问题 + 建议修正，等用户确认后继续。

## Step 6：三视角审查（仅对复杂任务触发）

触发条件：category 为 functional/ui 且 acceptance 超过 3 条，或存在多个 blocked_by。

从三个视角审查，按子代理策略（见 workflow.md）派发并行审查：
- 子代理 A：**开发视角** — 步骤是否清晰可执行？有无技术风险？
- 子代理 B：**QA 视角** — acceptance 是否覆盖边界条件和异常路径？
- 子代理 C：**业务视角** — 这个任务交付后，用户能感知到价值吗？

三个子代理完成后，主代理汇总冲突点，输出补充建议，用户确认后更新 acceptance/steps。

## Step 7：写入后提示

1. 列出已写入的任务（id + title）
2. 若存在 blocked_by 引用，提示：前置任务也是 InDraft，需人工先将其确认为 InSpec，依赖关系才生效
3. 提示用户：确认需求后，告知 Agent 将任务状态改为 InSpec 即可开始实施

## 不做的事

- 不生成中间 PRD markdown 文件
- 不自动将任务改为 InSpec
