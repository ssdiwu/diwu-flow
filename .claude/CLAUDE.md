# diwu-flow

**插件版本**：0.0.4

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

## 文件索引

| 名称 | 类型 | 触发场景 |
|------|------|---------|
| `dtask` `drun` `dcorr` `dvfy` `djug` `drec` `darc` | rule | 任务/执行/纠偏/验证/判断/记录/归档 |
| `dprd` `ddoc` `ddemo` `dstat` | product/tool | PRD/文档/Demo/状态 |
| `rules/*` | 参考 | exceptions/templates/file-layout/constraints |

## 行为铁律

**Push 前必跑**：`pytest tests/` 全量回归通过后才可 commit & push。

**Rules 同步**：修改 `rules/` 后必须同步到 `assets/dinit/assets/rules/` 模板。

**时间戳规则**：写入 Session 标题前必须先运行 `date '+%Y-%m-%d %H:%M:%S'`，禁止手写日期。

**recording 更新**：每次 session 结束前必须写入 `.diwu/recording/`。

**`.diwu/` 提交规则**：私有仓库阶段 `.diwu/` 全部提交。公开发行时由 `drelease.sh` 自动排除敏感文件推送到公开仓库。

- 修改 Skill 后验证 frontmatter YAML 合法性
- plugin.json 不声明 agents 字段（默认路径自动发现）
- CC 专属内容仅限 hooks/、.claude-plugin/、assets/

## 公开版本发布流程

> 私有仓库 → 公开仓库，只需配置一次 remote：

```bash
# 前置配置（只需一次）
git remote add public git@github.com:ssdiwu/diwu-flow.git

# 每次发布（确保 main 干净后）
./drelease.sh v{version} --push-public
# → 创建 release 分支 → 排除 .diwu/ 等敏感文件 → 打 tag → 推送私有+公开仓库 → 切回 main
```

## 项目结构

- `commands/` — 用户命令封装（drun, dtask, dinit, dprd, dadr, ddoc, ddemo, dcorr, dstat）
- `skills/` — 技能文件（dtask, drun, dcorr, dvfy, djug, drec, darc, dprd, ddoc, ddemo, dstat）
- `rules/` — 方法论规则文件
- `agents/` — 核心执行 Agent（explorer/implementer/verifier，默认路径自动发现）
- `assets/` — 模板资产
- `tests/` — 测试用例
- `hooks/` — 钩子脚本
- `drelease.sh` — 公开版本发布脚本
