"""TaskCreated: validate new task fields, GWT format, and blocked_by cycle detection.

GWT check supports both English (Given/When/Then) and Chinese (给定/当/则).
Cycle detection uses DFS with visited set.
"""
import json
import os
import sys

TASK_JSON_PATH = ".diwu/dtask.json"
REQUIRED_FIELDS = ["id", "title", "description", "acceptance", "steps", "category", "status"]
GWT_CATEGORIES = ["functional", "ui", "bugfix"]


def _load(p):
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    return {}


def _has_gwt_keywords(text):
    pairs = [("Given", "给定"), ("When", "当"), ("Then", "则")]
    return sum(1 for en, zh in pairs if en in text or zh in text) >= 2


def validate_required_fields(task):
    missing = [f for f in REQUIRED_FIELDS if not task.get(f)]
    if missing:
        print(f"[diwu] Task#{task.get('id')} 必填字段缺失: {missing}", file=sys.stderr)
    return not missing


def validate_gwt_format(task):
    if task.get("category", "") not in GWT_CATEGORIES:
        return True
    for i, item in enumerate(task.get("acceptance", [])):
        if isinstance(item, str) and not _has_gwt_keywords(item):
            print(f"[diwu] Task#{task.get('id')} acceptance[{i}] 缺少 Given/When/Then（或中文 给定/当/则）关键词", file=sys.stderr)
            return False
    return True


def validate_blocked_by_cycle(task):
    tid = task.get("id", 0)
    new_deps = task.get("blocked_by", [])
    if not new_deps:
        return True
    all_deps = {t["id"]: t.get("blocked_by", []) for t in _load(TASK_JSON_PATH).get("tasks", [])}
    all_deps[tid] = new_deps
    if _dfs_cycle(tid, all_deps, set(), []):
        print(f"[diwu] Task#{tid} blocked_by 循环依赖检测失败", file=sys.stderr)
        return False
    return True


def _dfs_cycle(tid, deps, visited, stack):
    if tid in stack:
        return True
    if tid in visited:
        return False
    visited.add(tid)
    stack.append(tid)
    for dep in deps.get(tid, []):
        if _dfs_cycle(dep, deps, visited, stack):
            return True
        stack.pop()
    return False


def main():
    data = json.load(sys.stdin)
    task = data.get("task", {})
    if not task:
        print("[diwu] 缺少 task 对象", file=sys.stderr)
        sys.exit(1)
    if validate_required_fields(task) and validate_gwt_format(task) and validate_blocked_by_cycle(task):
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
