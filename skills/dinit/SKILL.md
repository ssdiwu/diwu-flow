---
name: dinit
description: 项目工作流初始化——脚本使用指南与决策视角
---

# dinit — 项目工作流初始化

> 本文件是 dinit 脚本的使用文档与决策视角。
> 执行入口见 commands/dinit.md。

## 什么时候触发

用户输入 `/dinit` 时调用。

## 核心视角：初始化 vs 刷新

关键检测点：`.claude/rules/task.md` 存在与否。
- 存在 → 刷新模式（增量更新）
- 不存在 → 初始化模式（需收集信息后创建）

**注意**：文件存在 ≠ 配置完整。刷新模式下仍需 validate 确认一致性。

## 初始化模式的判断要点

### 信息收集策略
- scan-repo 结果清晰时（单一框架、明确入口），减少提问
- 结果模糊时（monorepo、多框架），聚焦问"主工作目录"和"启动命令"
- 不要让用户从技术栈列表里选——scan-repo 已推断好了

### 创建配置的陷阱
- 用户已有 `.claude/settings.json` → create-config 不应覆盖已有配置
- 已有 `.gitignore` → 不要追加重复条目
- 已有 `.diwu/dtask.toml` → 检查是否需要合并而非覆盖

## 刷新模式的判断要点

### 增量更新策略
- sync-rules 按 manifest 同步，但**用户手动改过的 rules 文件不应被静默覆盖**
- sync-skills 只创建 symlink，不会破坏已有内容
- 如果 sync-rules 报告大量 UPDATED，向用户确认是否预期行为

## 迁移行为（全自动）

migrate-legacy 由脚本 `cmd_run()` 自动调用。AI 关注点：
- 返回 `warnings` 或 `errors` 时需要处理
- 成功迁移不需要向用户报告细节（用户不想知道 JSON→TOML 发生了）

### 什么算旧版
- `.claude/rules/states.md` 存在且 `.claude/rules/task.md` 不存在 → v0.x 旧版
- `.diwu/` 下存在 `.json` 运行时文件（dtask.json / dtask-state.json / dsettings.json）
- `.claude/` 下存在运行时文件但 `.diwu/` 对应位置缺失
- `archive/task_archive_*.json` 存在（TOML 迁移遗留）

## 验证与收尾

validate 检查清单失败时的处理：
- 单项 FAIL 且非关键（如缺少 decisions.md）→ 记录警告继续
- 多项 FAIL 或关键项 FAIL → 向用户说明原因，建议修复后重新执行
- 权限错误 → 明确告知用户需要什么权限

## 红旗信号

| 信号 | 可能原因 | 建议 |
|------|---------|------|
| scan-repo 返回空目录 | 权限不足或非标准项目 | 先确认 cwd 正确 |
| migrate-legacy 报备份失败 | 磁盘空间或权限 | 暂跳过，记录警告 |
| create-config 报冲突 | 已有配置格式不符 | 让用户选择保留还是覆盖 |
| sync-rules 大量 UPDATED | manifest 与实际不一致 | 可能需要更新 manifest |
| validate 持续 FAIL | 底层模板或脚本 bug | 停止执行，升级问题 |

## 脚本内部命令参考（AI 执行参考，不得向用户展示）

以下为脚本子命令接口，仅供 AI 选择性调用：

| 命令 | 用途 | 调用时机 |
|------|------|---------|
| scan-repo | 扫描项目结构 | 初始化模式第一步 |
| sync-rules | 同步 rules 文件 | 每次 dinit 都执行 |
| sync-skills | 创建 skills symlink | 每次 dinit 都执行 |
| create-config | 创建配置文件 | 仅初始化模式 |
| migrate-legacy | 旧版格式迁移 | cmd_run 自动调用 |
| validate | 验证产出 | 最后一步 |

默认路径：`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dinit.py <命令> --cwd <项目根目录>`
