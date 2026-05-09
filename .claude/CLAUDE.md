# diwu-flow

**插件版本：0.1.0**

**当前项目是一个 Claude Code Plugin（插件）项目**

## 核心原则

- Skills 为底，Commands 为壳：所有方法论在 Skills 中，Commands 是薄封装
- 零平台耦合：Skill frontmatter 无平台专属字段（无 context/agent/model/allowed-tools/hooks）
- 扁平结构：agents/（默认路径自动发现，plugin.json 不声明）和 skills/ 均为单层目录，最大化平台兼容性
- 少即是多，克制且清晰；具体胜于抽象；引导顺序即优先级

## 上位心智层

**三唯一框架**：进入任务前确认唯一主线目录、唯一运行入口、canonical。

**P-J-A 骨架**：现象（事实）→ 判断（依据）→ 动作（下一步）。违反此链的规则是空壳。

**不确定性门控**：直接做（改动小可预期）/ 先写最小规格（结果不清需交接）/ 先探索验证（依赖多落点不清）

**证据优先级**：L1 运行态 > L2 调用链 > L3 自动化断言 > L4 表面观察 > L5 间接推断。默认 L1-3 主判。

## Skill 索引

| 名称 | 类型 | 触发场景 |
|------|------|---------|
| `dtask` `drun` `dcorr` `drec` | rule | 任务/执行/纠偏/记录 |
| `dprd` `dpth` `ddoc` `dref` `dstat` `didea` | product/tool | 产品论证/产品思维/文档/需求细化/状态/想法捕获 |
| `dloop` `dstop` | command | 连续循环/停止循环 |
| `rules/*` | 参考 | exceptions/templates/file-layout/constraints |

## 行为铁律

**Push 前必跑**：`pytest tests/` 全量回归通过后才可 commit & push。

**Rules 同步**：修改 `rules/` 后必须同步到 `.claude/rules/` 和 `assets/dinit/assets/rules/` 两处模板。

**时间戳规则**：写入 Session 标题前必须先运行 `date '+%Y-%m-%d %H:%M:%S'`，禁止手写日期。

**recording 更新**：每次 session 结束前必须写入 `.diwu/recording/`。

**`.diwu/` 提交规则**：origin/main 持续追踪 `.diwu/`（含 `.claude/`）。公开仓库通过 `drelease.sh` worktree 隔离模式发布 clean 版（自动排除 `.diwu/`、`.claude/` 等敏感文件）。

**版本号同步**：插件版本以 `.claude-plugin/plugin.json` 为真值来源；变更版本号时必须同步更新 `.claude-plugin/marketplace.json` 和 `install.sh` 中的 OpenCode stub 版本。

**文件操作安全铁律**：
- **先读后写（分层）**：修改已有文件前必须先读取将被修改的当前内容；整文件重写必须先读取完整文件；全新创建且确认不存在时可跳过读取。
- **JSON 格式化**：写入 .json 文件时必须 indent=2, ensure_ascii=False（禁止单行压缩）。
- **原子替换优先**：修改已有内容优先用 Edit 精确匹配替换；仅整文件重写时用 Write（须满足先读后写）。
- **敏感目录谨慎**：.diwu/ 和 .claude/ 下配置文件修改需确认不破坏现有结构或丢失数据。

- 修改 Skill 后验证 frontmatter YAML 合法性
- plugin.json 不声明 agents 字段（默认路径自动发现）
- CC 专属内容仅限 hooks/、.claude-plugin/、assets/

## 公开版本发布流程

> 私有仓库 → 公开仓库，只需配置一次 remote：

**发版前检查清单**：

| # | 检查项 | 方法 |
|---|--------|------|
| 1 | `pytest tests/` 全量通过 | `python3 -m pytest tests/ -q` |
| 2 | CHANGELOG.md 已追加新版本条目 | 人工确认 |
| 3 | 版本号已同步到三处 | plugin.json、marketplace.json、install.sh OpenCode stub |
| 4 | dloop runtime 已清空 | `python3 -c "import json; s=json.load(open('.diwu/dtask-state.json')); assert s.get('dloop') is None"` |

```bash
# 前置配置（只需一次）
git remote add public git@github.com:ssdiwu/diwu-flow.git

# 每次发布（确保 main 干净后）
./drelease.sh v{version} --push-public
# → 先推 origin/main（含 .diwu/）→ 创建临时 worktree 清理敏感文件 → 推送 clean 版到 public/main
```

## 项目结构

- `commands/` — 用户命令封装（drun, dtask, dinit, dprd, ddoc, drec, dref, dcorr, dstat, dloop, dstop, didea）
- `skills/` — 技能文件（dtask, drun, dcorr, drec, dprd, ddoc, dref, dstat, dloop, didea）
- `scripts/` — 共享脚本工具库（common.py 含 plugin_root/load_json/save_json/max_task_id 等函数），新增 script-backed 执行通道
- `rules/` — 方法论规则文件
- `agents/` — 核心执行 Agent（explorer/implementer/verifier，默认路径自动发现）
- `assets/` — 模板资产
- `tests/` — 测试用例
- `hooks/` — 钩子脚本
- `drelease.sh` — 公开版本发布脚本
