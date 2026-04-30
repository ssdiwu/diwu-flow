#!/usr/bin/env python3
"""diwu-flow dend: 取消 dloop 循环。

T3: cancel 职责归 dend.py 唯一入口，dloop.py 不设 cancel 子命令。
T5/T19: 所有路径 exit code 0；无状态文件返回 no_loop(ok:true)。
T19 固定语义：{ok, status, message, formatted_text}。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dtask_state import clear_loop_state, loop_state, save_runtime_state, sync_runtime_state  # noqa: E402


def cancel(cwd: Path) -> dict:
    """读取 dtask-state.json.dloop → 摘要 → 删除 → 返回结果。"""
    sync_result = sync_runtime_state(cwd, persist=True, ensure_exists=False)
    if sync_result.is_invalid:
        return {
            "ok": False,
            "status": "invalid_state_file",
            "message": f"dtask-state.json 损坏或无效：{sync_result.reason}",
            "formatted_text": "❌ dtask-state.json 无效，无法取消 dloop",
        }

    dloop = loop_state(sync_result.state)
    if dloop is None:
        return {
            "ok": True,
            "status": "no_loop",
            "message": "无活跃的 dloop 循环",
            "formatted_text": "✅ 无活跃的 dloop 循环",
        }

    completed = dloop.get("completed_task_ids", [])
    iteration = dloop.get("current_iteration", 0)
    completed_count = len(completed)

    clear_loop_state(sync_result.state)
    save_runtime_state(cwd, sync_result.state, remove_legacy=True)

    return {
        "ok": True,
        "status": "cancelled",
        "completed_count": completed_count,
        "iteration": iteration,
        "message": f"dloop 已取消（已完成 {completed_count} 个任务，第 {iteration} 轮）",
        "formatted_text": (
            f"✅ dloop 已取消\n"
            f"   已完成任务数: {completed_count}\n"
            f"   当前轮次: {iteration}"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="diwu-flow 取消 dloop 循环")
    parser.add_argument("--cwd", type=str, default=".", help="项目根目录")
    args = parser.parse_args()

    result = cancel(Path(args.cwd).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
