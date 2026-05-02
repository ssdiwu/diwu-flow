import json
import os
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SHARED_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS_DIR)

from dtask_state import sync_runtime_state  # noqa: E402


def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


event = {}
try:
    event = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    event = {}

sid = event.get("session_id") or event.get("sessionId") or ""
if sid:
    open("/tmp/.claude_main_session", "w").write(sid)

result = {}
cwd = event.get("cwd", "")
if cwd:
    task_data = _load_json(os.path.join(cwd, ".diwu", "dtask.json"))
    sync_result = sync_runtime_state(cwd, task_data, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        result["additionalSystemPrompt"] = (
            "dtask-state.json 无效，当前 session 不会自动恢复 InProgress。"
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
                    # P2: 长度裁剪——硬上限 4000 字符，保留最近内容
                    MAX_PITFALLS_LEN = 4000
                    content = raw
                    # 剥离 HTML 注释行（模板头残留），避免 prompt 噪音
                    content = "\n".join(
                        l for l in content.split("\n")
                        if not l.strip().startswith("<!--")
                    ).strip()
                    _TRUNCATE_MARKER = "\n[...]"
                    if len(content) > MAX_PITFALLS_LEN:
                        # 从后往前找最近的 ## 段落标题作为截断点
                        search_start = max(0, len(content) - MAX_PITFALLS_LEN)
                        cut_pos = content.rfind("\n## ", 0, search_start)
                        if cut_pos > 0:
                            content = "[... 已裁剪早期条目 ...]\n\n" + content[cut_pos + 1:]
                        else:
                            content = content[:MAX_PITFALLS_LEN - len(_TRUNCATE_MARKER)] + _TRUNCATE_MARKER
                        # 硬兜底：确保不超上限（含标记开销）
                        if len(content) > MAX_PITFALLS_LEN:
                            content = content[:MAX_PITFALLS_LEN - len(_TRUNCATE_MARKER)] + _TRUNCATE_MARKER
                    existing = result.get("additionalSystemPrompt", "")
                    pitfalls_section = (
                        "\n\n## 项目历史踩坑经验（project-pitfalls.md 自动注入）\n"
                        "以下为本项目积累的误判模式，执行任务时优先对照检查：\n\n"
                        + content
                    )
                    result["additionalSystemPrompt"] = existing + pitfalls_section
        except OSError:
            pass

if result:
    print(json.dumps(result))
