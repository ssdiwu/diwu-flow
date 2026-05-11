---
description: Session 记录写入操作手册——脚本驱动 closeout
argument-hint: "[session内容摘要]"
allowed-tools: Read, Write, Edit, Bash
effort: normal
---

# /drec — 记录与归档

> Session 结束后的必做步骤：写入 recording → 脚本 closeout → 解析结果。

## 执行步骤

1. 整理 session 内容（任务状态、实施内容、验收证据、下一步计划、踩坑经验）
2. 执行 `date '+%Y-%m-%d %H:%M:%S'` 获取真实时间戳（**禁止手写**）
3. 将正文直接写入 `.diwu/recording/session-{timestamp}.md`：
   - 文件名必须包含 `date` 命令返回的时间戳
   - 正文必须包含 `## Session YYYY-MM-DD HH:MM:SS` 标题行
   - 格式模板见 `rules/templates.md` §Session 文件格式 + `rules/session.md` §本次踩坑/经验
4. 执行 closeout 脚本：

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/drec_write.py run --cwd <项目根目录>
   ```

5. 解析 stdout JSON 结果：

   | status | 含义 | 你的动作 |
   |--------|------|---------|
   | `committed` | 新建 commit 成功 | 返回 commit hash 给调用方 |
   | `amended` | 追加到上一 recording commit | 返回 hash 给调用方 |
   | `no_changes` | 工作区无变更 | 正常完成 |
   | `partial_success` | recording 已存在但 commit 失败 | 按 recovery_hint 处理后重试 |
   | `failed` | recording 不存在或检测失败 | 检查 recording 文件后重试 |

## Amend 模式

当 `dtask-state.toml` 中存在 `pending_recording` 标记且 ≤600s 时，脚本**自动尝试 amend**。amend 失败时自动 fallback 到普通 commit。无需 AI 手动判定。

## 完整规范

原子 commit、标记清除语义、失败恢复、归档策略等详见 **`skills/drec/SKILL.md`**。格式规则见 **`rules/session.md`** 和 **`rules/templates.md`**。
