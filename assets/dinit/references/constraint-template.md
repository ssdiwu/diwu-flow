# 架构约束示范（用于 `.claude/rules/constraints.md`）

先看一份已填充样例，再替换成你的项目信息。目标是让 Agent 先学到分析粒度，再填你自己的内容。

## 已填充样例（消息通知模块）

````markdown
# Message Notification Architecture Constraints

## Constraints

| Dimension | Constraint | Verification |
|-----------|------------|--------------|
| Business | 同一 message_id 最多成功投递一次（幂等） | 重试同一 message_id 不会产生第二条成功投递记录 |
| Temporal | 消息仅允许 `pending -> delivered` 或 `pending -> expired`，禁止回退 | 状态机转移表无 `delivered -> pending` |
| Cross-platform | Web/iOS/Android 对消息状态枚举值完全一致 | 三端 SDK 枚举值集合与后端 schema 比对一致 |
| Concurrency | 同一用户多端并发确认已读时，最终状态一致 | 并发写入后 DB 只保留一个最终状态 |
| Perception | 通知到达延迟 P95 < 500ms，未读列表查询 P95 < 200ms | APM 监控面板满足阈值 |

## State Machines

| Current State | Event | New State |
|---------------|-------|-----------|
| pending | push_ok | delivered |
| pending | timeout_24h | expired |
| delivered | any | delivered (ignore) |
| expired | any | expired (ignore) |

## Boundaries

| Type | Internal | External | Crossing Method |
|------|----------|----------|-----------------|
| Domain | MessageService, DeliveryPolicy | NotificationAPI | REST / domain events |
| Platform | PushAdapter 接口 | APNs / FCM | Adapter 实现 |
| Time | Message 表（事实） | UnreadBadge 投影 | Projection function + cache refresh |

## Degradation Paths

| Dependency | Failure | Fallback | User Perception |
|------------|---------|----------|-----------------|
| Push Provider | APNs/FCM 不可用 | 写入消息中心未读列表，用户下次打开可见 | 可能无即时提醒，但消息不丢失 |
| Redis Cache | 缓存不可用 | 直接查询 DB 返回未读列表 | 首屏可能变慢，功能可用 |
| Profile Service | 用户画像超时 | 使用默认通知策略（全量推送） | 精准度下降，不影响可达性 |

## Data Ownership

Source of Truth: PostgreSQL `messages`
Projection chain: `messages` -> `unread_counts` -> client local badge
Conflict strategy: Server-wins
````

## 替换指引（把样例改成你的模块）

1. 把模块名替换成你的真实模块（如 Billing、Auth、Search）。
2. 每个维度至少写 1 条可验证约束，不要写“合理处理”这类模糊词。
3. 状态机必须写出非法转移如何处理（通常是 ignore 或 reject）。
4. 降级路径必须写“依赖失败后用户会看到什么”。
5. Data Ownership 必须明确 Source of Truth 和冲突策略。

## 快速检查清单

```text
约束:
  □ 五个维度都有可验证描述（不是口号）
  □ 每条约束都能映射到代码或监控

状态机:
  □ 只有合法状态和合法转移
  □ 非法转移有明确策略（ignore/reject）

边界:
  □ 领域、平台、时间边界已区分
  □ 事实和投影没有混写

降级:
  □ 每个关键依赖都有 fallback
  □ fallback 的用户感知已写明
```
