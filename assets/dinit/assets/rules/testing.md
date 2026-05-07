# 测试分层策略

> **规则约束级别说明**：本文件定义测试分层的核心规则。除非特别标注 `[建议]`，否则都是必须遵守的约束。
> 定义修改幅度到验证方式的映射、分层执行顺序、插件项目特殊说明。
> 与 `verification.md`（证据等级）配合使用：本文件管"该写什么测试 / 选哪种验证方式"，verification 管"什么证据算完成"。
> `dtask` 消费 testing（补测试触发条件），`drun` 消费 verification（选证据等级判定 Done）。

## 一、测试分层模型

| 层级 | 名称 | 职责 | 典型位置 |
|------|------|------|---------|
| L1 | 单元测试 | 函数/方法级正确性 | `tests/` |
| L2 | 集成测试 | 模块间协作正确性 | `tests/` |
| L3 | E2E 测试 | 端到端流程正确性 | `tests/` 或手动 |
| L4 | repo-level 基线 | smoke.sh / 全量回归 | `.diwu/checks/smoke.sh` |

## 二、幅度→验证方式映射

| 修改幅度 | 判定标准 | 验证方式 | 最低证据等级 |
|---------|---------|---------|------------|
| **大幅度** | API/字段契约变更，或单任务 >2000 行 | 浏览器工具端到端验证 + REVIEW 请求 | L1-L2 运行态/调用链 |
| **小幅度** | 其余所有修改 | lint / build / 单元测试 / verify.sh | L3+ 自动化断言 |

## 三、补测试触发条件

以下情况**必须补测试**：

| 触发条件 | 测试类型 | 说明 |
|---------|---------|------|
| 新增 public 函数/类 | 单元测试 | 含正常路径 + 边界值 |
| 修改状态机转移逻辑 | 单元测试 | 覆盖每条合法转移 + 非法输入 |
| 修改 hooks 脚本 | 集成测试 | mock hook 触发条件，验证回调行为 |
| 修改 JSON schema / 数据结构 | 单元测试 | 合法+非法输入 |

以下情况**可豁免**：

| 场景 | 原因 |
|------|------|
| 纯文案修正（typo/措辞） | 无行为变化 |
| rules/ 文件重构（内容迁移，语义不变） | 由 test_doc_consistency 覆盖结构检查 |
| comments / README 更新 | 文档层，无运行态影响 |

## 四、插件项目特例

diwu-flow 自身作为插件项目，测试重点：

| 验证对象 | 方法 | 证据等级 |
|---------|------|---------|
| hooks 是否被触发 | mock UserPromptSubmit / PreToolUse / PostToolUse / Stop | L2 调用链 |
| 产物是否生成且正确 | 运行脚本后检查输出文件 | L1 运行态 |
| JSON 合法性 | python3 -m json.tool / jsonschema validate | L3 断言 |
| state 一致性 | dtask.json ↔ dtask-state.json 联动校验 | L3 断言 |
| rules 三副本同步 | diff rules/ vs .claude/rules/ vs assets/ | L3 断言 |

## 五、测试与证据映射

| testing 选择 | verification 对应 | Done 判定 |
|-------------|-----------------|----------|
| 写了单元测试 + 全绿 | L3 自动化断言 | 小幅度：自审 Done |
| E2E 通过 + 截图 | L1 运行态 + L4 表面观察 | 大幅度：REVIEW 后 Done |
| 仅 lint/build 通过 | L3 部分 | 不足，补充测试或标记 InReview |
| smoke.sh 通过 | L3 基线 | 前提条件，不单独作为 Done 依据 |

## 六、引用导航

| 想了解 | 去哪 |
|--------|------|
| 什么证据算完成 | `rules/verification.md` |
| 怎么组织测试文件 | `rules/file-layout.md` §测试资产 |
| Done 判定的完整门槛 | `rules/task.md` §InReview→Done 判定锚点 |
| 插件项目的 hooks 验证细节 | `.doc/架构规范.md` §Hooks 实现链 |
