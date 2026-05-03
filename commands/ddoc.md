---
description: 产品文档工具（正向/逆向/ADR 三种模式）
argument-hint: "[模式: forward|reverse|adr（可选）]"
allowed-tools: Read, Write, Edit, Glob, Bash
effort: high
---

# /ddoc — 产品文档

## Step 0：参数检测

检查用户输入是否包含模式关键词，自动设置模式：
- 包含 `adr`、`架构决策`、`决策记录`、`ADR` → 自动设为 **ADR 模式**
- 包含 `reverse`、`逆向`、`还原文档`、`从代码` → 自动设为**逆向模式**
- 包含 `forward`、`正向`、`写文档`、`从需求` → 自动设为**正向模式**
- 均未匹配 → 进入 Step 1 询问

## Step 1：确认模式与范围

### 正向 / 逆向 模式

询问用户（上下文已明确的跳过，Step 0 已确定的跳过）：
1. **模式**：正向（有需求，要写文档）还是逆向（有代码，要还原文档）？
2. **范围**：整个产品 / 特定模块 / 特定功能？
3. **输入**：代码库路径（逆向）或需求描述（正向）
4. **输出结构**：领域驱动（推荐，有 3 个以上业务域时）还是分层（工具类产品或小项目）？

### ADR 模式

按 skills/ddoc/SKILL.md 中 ADR 模式章节执行。脚本调用：

```bash
# 获取下一个编号
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ddoc_adr.py next-number --cwd <项目根目录>

# 创建骨架
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ddoc_adr.py create --title "决策标题" --cwd <项目根目录>

# 更新状态
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ddoc_adr.py update-status --number N --status Accepted --cwd <项目根目录>
```

> **文件操作安全（R1）**：写入 `.doc/` 输出文档前必须先 Read 目标文件当前状态，确认不会意外覆盖。写入后同步更新 `.doc/README.md` 索引（列格式见 `.doc/schema.md` §Doc）。

## ADR 子命令表

| 子命令 | 用途 | 参数 |
|--------|------|------|
| `next-number` | 获取下一个 ADR 编号 | `--cwd` |
| `create` | 创建 ADR 骨架文件 | `--title` `--number`(可选) `--status`(可选) `--cwd` |
| `update-status` | 更新 ADR 状态 | `--number` `--status` `--cwd` |

## ADR 子模式约束

| 维度 | 约束 |
|------|------|
| **业务边界** | 同一决策只有一个 ADR（更新不新建）；Context 必须有具体数字；Consequences 的 ⚠️ 必须有触发条件和解决路径 |
| **时序约束** | 先读 README 判断新建/更新 → 写文件 → 更新 README；不可先写文件再判断 |
| **跨命令关系** | ADR README 是 `/dprd` Q5 的输入；ADR 编号格式 `ADR-NNN` 是 `/dtask` steps 引用的依据 |
| **感知信号** | 备选方案的缺点必须是具体技术风险和触发条件，不允许「复杂度高」等模糊描述 |

## Step 2：执行

正向/逆向模式按 skills/ddoc/SKILL.md 中对应模式执行。四层示范、输出结构决策树、五约束维度、两层完整性检查、AI prompt 模板均在其中。
