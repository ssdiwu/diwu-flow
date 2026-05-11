# diwu-flow

**插件版本：0.1.2** | Claude Code Plugin 项目

**读者**：改 diwu-flow 源码的 AI。目标项目的 AI 读 `rules/`，不读此文件。

---

## 必读 — 每次改动都遵守

### 文件操作

- **先读后写**：修改已有文件前必须 Read；整文件重写必须先读完整文件；全新创建且确认不存在时可跳过
- **JSON 格式**：indent=2, ensure_ascii=False（禁止单行压缩）
- **原子替换优先**：优先 Edit 精确匹配；仅整文件重写用 Write
- **Skill 验证**：修改 Skill 后验证 frontmatter YAML 合法性

### 变更传播

| 变更 | 动作 |
|------|------|
| 修改 `rules/` | 必须同步 `.claude/rules/` + `assets/dinit/assets/rules/` 两处模板 |
| 版本号变更 | 以 `.claude-plugin/plugin.json` 为真值源，同步 `marketplace.json` + `install.sh` |
| 功能性变更完成 | 立即追加到 `CHANGELOG.md` 当前未发布版本条目下 |
| Session 结束 | 写入 `.diwu/recording/`；时间戳必须 `date '+%Y-%m-%d %H:%M:%S'` 获取 |
| `.diwu/` 提交 | origin/main 持续追踪 `.diwu/`（含 `.claude/`）；公开仓库由 `drelease.sh` worktree 隔离 |

### 质量门控

- Push 前：`pytest tests/` 全量回归通过
- 修改 rules/ 后额外检查：三副本 diff 一致 + `test_doc_consistency` 通过

### GitHub 操作

- **Issue 标签必须先查后用**：`gh issue edit --add-label` 前必须先执行 `gh label list --repo <repo>` 查看已有标签，从中选择或复用。禁止直接 `gh label create` 创建可能重复的标签。仓库当前标签清单见 `gh label list --repo ssdiwu/diwu-flow-dev`

---

## 按需参考 — 碰到对应场景时回来查

> 以下内容按**操作目标**组织。正在改哪个目录，就看哪一节。

### 改 skills/ 时

- **启发式 > SOP**：SKILL.md 是能力描述 + 视角启发，不是执行 SOP。AI 读完后应知道"这个视角看什么、问什么"
- **章节量级**：每个模式/章节理想 20-50 行；>80 行应拆分或外移
- **细节分层归属**：
  - SKILL.md → 为什么用 + 关键提问 + 红旗信号 + 模式间关系（启发层）
  - agents/*.md → 公共协议 + 执行流程 + 输出格式（结构化层）
  - 运行时注入 → 完整 prompt 细节由 Main AI 从上述来源组装，不预写在 SKILL.md
- **反模式**：在 SKILL.md 写完整流程图 + 步骤编号 + 分支判断 + 注入 prompt 全文

### 改 rules/ 时

> rules/ 同步到任意目标项目，必须写成**项目无关**。自问："如果目标是 Go 后端或 React 前端，这句还有意义？"

**纳入判断框架**（三条全通过才写入 rules/）：

| # | 问题 | 通过条件 |
|---|------|---------|
| Q1 | 消费者是谁？ | 使用 diwu-flow 的**任意目标项目**中的 AI |
| Q2 | 消费场景是什么？ | AI 在**执行任务前/中/后**需要参考的行为约束（非一次性设计决策） |
| Q3 | 脱离插件源码是否仍有意义？ | 换成 Go 后端或 React 前端，文字含义不变（只换术语） |

**归类参考**：

| 归类为 rules/ | 不归为 rules/ |
|---------------|--------------|
| "什么时候该调哪个 skill" | "skill SKILL.md 的内部方法论细节" |
| "任务状态怎么转移" | "为什么选择三值 type 而非五值" |
| "子代理交接协议" | "hooks 脚本的具体实现逻辑" |
| "验收证据优先级" | "某个 hook 的 stderr 格式" |

> **Q3 关键**：dpth/dref/dtask.json 等 diwu-flow 术语是方法论词汇（如同"P-J-A"、"GWT"），不算插件专属。判断标准——这条规则是在**教 AI 怎么用这套方法**，还是**描述方法是怎么实现的**。

### 改 agents/ 时

- **负面清单优先**：每个 agent 必须明确"不做什么"；没有负面清单的 agent 必然越界
- **故障隔离铁律**：任何非核心 agent 失败时，必须能退化回 explorer→implementer→verifier 闭环
- **能力驱动**：先识别能力需求→有对应 agent 就派发→无则标记能力缺口；不强塞职责

### 改 .doc/ 时

详见 issue [ssdiwu/diwu-flow-dev#24](https://github.com/ssdiwu/diwu-flow-dev/issues/24)。

- **两层分离**：
  - 文件结构层（按主题分文件）+ 索引导航层（`.doc/README.md` 按读者意图组织路径）
  - Diátaxis 解决"文档内部怎么写"，不作为文件分类依据
- **每份文件必须有边界**：明确的"回答什么 / 不回答什么"

---

## 系统分层地图

| 层 | 关键资产 | 职责 |
|---|---------|------|
| L0 入口容器 | didea | 想法挂住、本地持久化、下游衔接 |
| L1 判断收束 | dpth / dref / dprd / ddoc | 方向判断、需求细化、PRD 论证、产品文档 |
| L2 下游扩展 | architect / debugger | 技术审稿 gate、异常诊断与回交 |
| L3 协议层 | rules/handoff.md | dtask/drun 主编排边界、回交模型、Handoff Report 协议 |
| L4 规则真相源 | rules/ | 状态机契约、blocked_by、acceptance、verification 规范 |
| L5 表层能力 | Commands / Skills | drun 双入口、持久化策略、新增/删减/溶解标准 |
| 横切增强 | rules/testing.md | 测试分层策略、幅度→验证方式映射 |

> 架构原则：Skills 为底，Commands 为壳。Skill frontmatter 零平台耦合。agents/ 和 skills/ 扁平单层，默认路径自动发现，plugin.json 不声明 agents。

## 资产速查

| 类型 | 数量 | 详情 |
|------|------|------|
| Skills | 11 | 入口容器(didea) / 思考收束(dpth,dref,dprd,ddoc) / 任务闭环(dtask,drun) / 连续执行(dloop) / 观察纠偏(dstat,dcorr,drec) |
| Agents | 5 | explorer(只读) / implementer(唯一写权限) / verifier(不信自述) / architect(审dtask域) / debugger(诊断回交) |
| Commands | 13 | drun dtask dinit dprd ddoc drec dref dcorr dstat dloop dstop didea dpth （dstop/dinit 无对应 Skill） |
| 目录 | commands/ skills/ agents/ scripts/ hooks/scripts/ rules/ assets/ tests/ .doc/ | 见下方 |

| 目录 | 内容 |
|------|------|
| `commands/` | 13 个薄壳命令 |
| `skills/` | 11 个方法论 Skill（唯一真相源） |
| `agents/` | 5 个执行 Agent |
| `scripts/` | 共享脚本（common.py / dtask_transition / dloop / dstat / ...） |
| `hooks/scripts/` | 10 业务脚本 + 1 wrapper（run_hook.py）；导航见 `hooks/README.md`；设计原则见 `.doc/架构规范.md` Part C |
| `rules/` | 14 个规则文件 |
| `assets/` | /dinit 初始化模板 |
| `tests/` | 三级测试（L1 配置 / L2 脚本 / L3 一致性） |
| `.doc/` | 设计文档真相源 |

---

## 发版流程

| # | 检查项 | 方法 |
|---|--------|------|
| 1 | `pytest tests/` 全量通过 | `python3 -m pytest tests/ -q` |
| 2 | CHANGELOG.md 条目完整 | 最终确认（日常已持续追加） |
| 3 | 版本号已同步三处 | plugin.json → marketplace.json + install.sh |
| 4 | dloop runtime 已清空 | `python3 -c "import json; s=json.load(open('.diwu/dtask-state.json')); assert s.get('dloop') is None"` |

```bash
./drelease.sh v{version} --push-public
```
