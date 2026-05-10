import json
import os
import sys

from _shared import setup_sys_path, load_toml_fallback, load_stdin_event  # noqa: E402

setup_sys_path()

from dtask_state import sync_runtime_state  # noqa: E402
from session_scope import atomic_write_session_id  # noqa: E402


event = load_stdin_event()

sid = event.get("session_id") or event.get("sessionId") or ""
result = {}
cwd = event.get("cwd", "")
if sid and cwd:
    atomic_write_session_id(cwd, sid)

if cwd:
    task_data = load_toml_fallback(os.path.join(cwd, ".diwu", "dtask.toml"))
    sync_result = sync_runtime_state(cwd, task_data, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        result["additionalSystemPrompt"] = (
            "dtask-state.toml 无效，当前 session 不会自动恢复 InProgress。"
            f"请先修复 runtime state：{sync_result.reason}"
        )

    env_path = os.path.join(cwd, ".claude", "env")
    if os.path.isfile(env_path):
        env = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        if env:
            result["env"] = env

    # 自动注入项目历史踩坑经验（Layer 2 项目高频误判表）
    pitfalls_path = os.path.join(cwd, ".diwu", "project-pitfalls.md")
    if os.path.isfile(pitfalls_path):
        try:
            with open(pitfalls_path, encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                pass
            else:
                # P1: 判断是否为纯模板（无真实数据行）→ 跳过；保留模板头但填了真实条目 → 正常注入
                # 判定策略：
                #   - 含 <!-- 的文件：检查是否存在"真实数据行"（| 开头 + 不含占位 + 非纯短标签表头）
                #   - 不含 <!-- 的文件：只要有内容就视为真实数据（用户自建文件）
                _placeholder_markers = ("占位", "请替换", "（示例：")
                _is_template_origin = "<!--" in raw
                _lines = raw.split("\n")
                _has_real_data = False
                for _line in _lines:
                    _stripped = _line.strip()
                    # 跳过空行、标题行、注释、纯竖线、分隔行
                    if (not _stripped or _stripped.startswith("#")
                            or _stripped.startswith("<!--") or _stripped == "|"
                            or _stripped.startswith("|--")):
                        continue
                    if _stripped.startswith("|"):
                        # 含占位标记 → 模板占位行，跳过
                        if any(m in _stripped for m in _placeholder_markers):
                            continue
                        # 模板来源的文件：还需排除表头行（短标签如 "| 现象 | 根因 | 正确做法 | 来源 |"）
                        if _is_template_origin:
                            _cells = [c.strip() for c in _stripped.split("|")[1:-1]]
                            # 表头特征：所有非空单元格均为短标签（≤6 字符），且无 session 文件名格式
                            _is_header_like = (
                                _cells
                                and all(len(c) <= 6 for c in _cells if c)
                                and not any("session-" in c or ".md" in c for c in _cells)
                            )
                            if _is_header_like:
                                continue
                        # 通过所有过滤 → 真实数据行
                        _has_real_data = True
                        break
                # 非模板来源的文件：只要走到这里且有内容就视为有真实数据
                if not _is_template_origin and raw:
                    _has_real_data = True
                if not _has_real_data:
                    pass  # 纯模板/占位文件，不注入

                else:
                    # P2: 按类别生成摘要注入——上限 8000 字符
                    MAX_PITFALLS_LEN = 8000
                    # 剥离 HTML 注释行
                    content = "\n".join(
                        l for l in raw.split("\n")
                        if not l.strip().startswith("<!--")
                    ).strip()
                    # 按 ## 类别分段，提取每类现象摘要
                    sections = content.split("\n## ")
                    summary_parts = []
                    for section in sections:
                        sec_lines = section.strip().split("\n")
                        if not sec_lines:
                            continue
                        cat_name = sec_lines[0].strip().lstrip("#").strip()
                        if not cat_name or cat_name.lower().startswith("source:"):
                            continue
                        phenomena = []
                        for line in sec_lines[1:]:
                            stripped = line.strip()
                            if (not stripped.startswith("|")
                                    or stripped.startswith("|--")
                                    or stripped.startswith("|-")):
                                continue
                            cells = [c.strip() for c in stripped.split("|")[1:-1]]
                            if not cells:
                                continue
                            first_cell = cells[0]
                            if len(first_cell) <= 4 and any(
                                kw in first_cell for kw in ("现象", "Pattern", "Symptom")
                            ):
                                continue
                            if first_cell.startswith("**Source:"):
                                continue
                            phenomena.append(first_cell)
                        if phenomena:
                            summary_parts.append((cat_name, phenomena))
                    if summary_parts:
                        summary_lines = []
                        for cat_name, phenomena in summary_parts:
                            summary_lines.append(f"{cat_name}（{len(phenomena)}条）:")
                            for p in phenomena:
                                display = p if len(p) <= 100 else p[:97] + "..."
                                summary_lines.append(f"- {display}")
                            summary_lines.append("")
                        summary_text = "\n".join(summary_lines).strip()
                        if len(summary_text) > MAX_PITFALLS_LEN:
                            # 从最旧的类别开始逐类裁剪，保证保留的类别完整
                            _CROP_MARKER = "[... 已裁剪早期类别 ...]\n\n"
                            while len(summary_text) > MAX_PITFALLS_LEN:
                                # 跳过已有的 crop marker，避免重复命中自身 \n\n
                                search_start = (
                                    len(_CROP_MARKER)
                                    if summary_text.startswith(_CROP_MARKER)
                                    else 0
                                )
                                boundary = summary_text.find("\n\n", search_start)
                                if boundary < 0:
                                    # 只剩一个类别仍超长，保留该类别开头 + 标注
                                    summary_text = (
                                        summary_text[:MAX_PITFALLS_LEN - 50]
                                        + "\n[...]"
                                    )
                                    break
                                summary_text = (
                                    _CROP_MARKER + summary_text[boundary + 2:]
                                )
                        existing = result.get("additionalSystemPrompt", "")
                        pitfalls_section = (
                            "\n\n## 项目历史踩坑经验"
                            "（project-pitfalls.md 自动注入，摘要模式）\n"
                            "以下为本项目积累的误判模式摘要，"
                            "执行任务时优先对照检查：\n\n"
                            + summary_text
                            + "\n\n详细条目见 .diwu/project-pitfalls.md"
                        )
                        result["additionalSystemPrompt"] = existing + pitfalls_section
        except OSError:
            pass

if result:
    print(json.dumps(result))
