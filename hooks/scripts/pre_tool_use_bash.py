"""PreToolUse(Bash): 执行前输出当前 InProgress 任务信息。"""
import json
import os
import sys

TASK_JSON_PATH = ".diwu/dtask.json"


def main():
    task_path = os.path.join(os.getcwd(), TASK_JSON_PATH)
    if not os.path.exists(task_path):
        return
    with open(task_path, encoding="utf-8") as f:
        data = json.load(f)
    tasks = data.get("tasks", [])
    inprogress = [t for t in tasks if t.get("status") == "InProgress"]
    if inprogress:
        t = inprogress[0]
        print(f"Task#{t['id']}: {t['title']}")


if __name__ == "__main__":
    main()
