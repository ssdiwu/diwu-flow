# Continue Here — PR4 定义已就位

## 当前分支
- `feature/pr4-didea-container`

## 当前唯一目标
- 让下一位 AI 直接在这个分支上落地 **PR4：didea 本体与容器层实现**。

## 本次已完成
- 已基于最新 `main`（PR2 已合并）冻结 PR4 的边界。
- 已确认：PR4 只做 `didea` 本体、`.diwu/ideas/` 容器层、软入口/硬入口与动作门控，不混入 README / `.doc/` / rules 真相源重写。
- 用户当前要求：先把 PR4 Draft PR 建出来，并把定义附到 PR body，供后续 AI 直接在这条主线上继续实现。

## PR4 一句话定义
- **PR4：落地 `didea` 本体（soft entry + hard entry + idea 容器），把“想法挂住”这件事变成稳定入口；不混入 README/.doc 重写，也不承载 drun 双入口、Persistence Policy 或 rules 重组。**

## 先读这些文件
1. `commands/didea.md`（若不存在则准备新建）
2. `skills/didea/SKILL.md`（若不存在则准备新建）
3. `rules/file-layout.md`
4. `.doc/架构规范.md`
5. `skills/dpth/SKILL.md`、`skills/dref/SKILL.md`、`skills/dprd/SKILL.md`（用于定义下游接口）

## In Scope
- 新建 `skills/didea/SKILL.md`
- 新建 `commands/didea.md`
- 明确 `.diwu/ideas/` 的目录结构与 frontmatter 最小字段
- 定义本地优先 + 可选 GitHub issue 同步的容器语义
- 定义自增 ID + 用户语言文件名策略
- 定义软入口：自然识别 + 主动提议
- 定义硬入口：`create/list/show/archive/push/refine`
- 定义动作门控：本地写入确认 + 外部同步二次确认
- 冻结到 `dpth` / `dref` / `dprd` / `dtask` 的下游接口

## Out of Scope
- 不重写 `.doc/架构规范.md`
- 不重写根 `README.md`
- 不做 `skills/README.md` / `commands/README.md`
- 不做 `architect` / `debugger`
- 不做 rules 真相源本体
- 不做 `drun dual-entry`
- 不改 hooks 链路
- 不碰说明层结论性文档（留给 PR5）

## 关键边界
- `didea` 是**入口容器层**，不是产品判断层，也不是执行层。
- `didea` 可以挂住想法，但不替代 `dpth` / `dref` / `dprd` 的判断与收束。
- 自然识别只能**建议进入 didea**，不能自动落盘。
- 任何外部同步（如 GitHub issue）都必须二次确认。
- `commands/didea.md` 必须保持薄壳；方法论在 `skills/didea/SKILL.md`。

## 推荐实施顺序
1. 先定 `.diwu/ideas/` 的最小文件结构和 frontmatter
2. 再写 `skills/didea/SKILL.md` 的能力边界和动作门控
3. 再写 `commands/didea.md` 薄壳入口
4. 再冻结到 `dpth/dref/dprd/dtask` 的下游接口
5. 最后补测试并跑全量 `pytest tests/ -q`

## 最小结构建议
- 目录：`.diwu/ideas/`
- 文件命名：`{id}-{user-language-title}.md`
- frontmatter 最小字段建议：
  - `id`
  - `title`
  - `status`（如 `active|archived`）
  - `source`（如 `manual|suggested|synced`）
  - `created_at`
  - `updated_at`
- 正文最小区块建议：
  - `## Idea`
  - `## Why now`
  - `## Next candidate action`

## 下游接口先冻结到这个粒度
- `push -> dpth`：把模糊想法送去产品诊断
- `push -> dref`：把想法送去收敛成可执行检查清单
- `push -> dprd`：把想法送去扩成 PRD
- `push -> dtask`：仅在已经足够具体时进入任务化

## 落地时优先验证
- 自然识别不会自动写 `.diwu/ideas/`
- `create/list/show/archive/push/refine` 六类硬入口边界清楚
- 外部同步必须二次确认
- `commands/didea.md` 没有承载方法论正文
- 与 `dpth/dref/dprd/dtask` 的出口动作不会混淆

## 已确认的判断
- PR4 可以独立于 PR2 开始，但语义上建议参考 PR3 的下游接口。
- PR4 不要提前写 README / `.doc/` 说明层；那是 PR5 的职责。
- PR4 不要回头改 `rules/file-layout.md` 的规则正文，除非实现确实暴露出新的容器层真相源缺口。

## 给下一位 AI 的注意事项
- 先收口动作模型，再写文件，不要一开始就扩成“大而全想法系统”。
- 先定义本地容器，再讨论 GitHub issue 同步，不要把外部同步当主路径。
- 用户这轮要的是一条可持续推进的 PR4 主线，后续实现会继续堆在这个分支和 PR 上。
