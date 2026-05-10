#!/usr/bin/env python3
"""diwu-flow dloop: 启动、状态查询和停止（CRUD 全集）。

start/status/stop：循环生命周期管理（三件套）。
T2: 停止判断真相源仍在 stop_decision.py（hook 层自动终止）；
    本脚本的 stop 子命令仅处理「用户主动清除」路径。
T17: start 的可执行任务检查只判断 InProgress 或未阻塞 InSpec 是否存在。
T19: 固定语义 {ok, status, data?}；所有路径 exit 0。
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DIWU_DIR, DTASK_JSON, DSETTINGS_TOML, load_toml_or_empty, load_json_or_empty, save_json  # noqa: E402
from dloop_state import classify, cleanup_state, get_active_tasks, get_done_ids, get_executable_tasks  # noqa: E402
from dtask_state import clear_loop_state, loop_state, runtime_state_path, save_runtime_state, set_loop_state, sync_runtime_state  # noqa: E402


def _task_payload(cwd: Path) -> dict:
    """Load dtask payload once for start/status decisions."""
    data = load_json_or_empty(cwd / DTASK_JSON)
    return data if isinstance(data, dict) else {}


def _invalid_state_result(reason: str) -> dict:
    return {
        "ok": False,
        "status": "invalid_state_file",
        "message": f"dtask-state.json 损坏或无效：{reason}。请用 /dstop 清理或人工检查。",
        "formatted_text": "❌ dtask-state.json 无效，无法安全操作",
    }


def cmd_start(cwd: Path, max_tasks: int = None, interval: str = None,
               cron_job_id: str = None) -> dict:
    """启动 dloop 循环（cron 模式）。"""
    diwu_dir = cwd / DIWU_DIR
    state_path = runtime_state_path(cwd)
    dtask_payload = _task_payload(cwd)
    tasks = [task for task in dtask_payload.get("tasks", []) if isinstance(task, dict)]
    settings = load_toml_or_empty(cwd / DSETTINGS_TOML)

    # Stale-state 兜底（#23）：检查已有 state 文件是否为 terminal_stale
    stale_cleanup_reason = None
    classification = classify(cwd, dtask_data=dtask_payload, settings=settings)
    if classification.is_stale:
        stale_cleanup_reason = classification.reason or "terminal_stale"
        cleanup_state(cwd)
    elif classification.is_invalid:
        return _invalid_state_result(classification.reason)

    runtime_sync = sync_runtime_state(cwd, dtask_payload, persist=True, ensure_exists=True)
    if runtime_sync.is_invalid:
        return _invalid_state_result(runtime_sync.reason)
    existing_loop = loop_state(runtime_sync.state)
    if existing_loop and existing_loop.get("active"):
        return {
            "ok": False,
            "status": "already_running",
            "message": "dloop 已在运行中。请先执行 /dstop 停止当前循环。",
            "formatted_text": "⚠️ dloop 已在运行中。请先执行 /dstop 停止当前循环。",
        }

    # Cron 模式必须提供 interval
    if not interval:
        return {
            "ok": False,
            "status": "missing_interval",
            "message": "需要 --interval 参数（如 3m, 5m）",
            "formatted_text": "❌ 缺少 --interval 参数",
        }

    # 任务可用性检查（T17）
    executable = get_executable_tasks(tasks)

    if not executable:
        return {
            "ok": False,
            "status": "no_executable_tasks",
            "message": "无可执行的任务（需要 InSpec 或 InProgress 状态的任务）。",
            "formatted_text": "❌ 无可执行任务。请先 /dtask 规划任务并确认为 InSpec/InProgress。",
        }

    active_count = len(get_active_tasks(tasks))
    if max_tasks is not None and max_tasks >= 0:
        effective_max = max_tasks  # 显式值（0=无限, N>0=限制N）
    else:
        effective_max = active_count  # 自动快照

    # 创建状态文件
    state = {
        "active": True,
        "mode": "cron",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_task_ids": [],
        "initial_done_ids": list(get_done_ids(tasks)),  # 启动快照：排除历史 Done 对 max_tasks 的干扰
        "current_iteration": 0,
        "max_tasks": effective_max,
        "stopped_at": None,
        "stop_reason": None,
    }
    if cron_job_id:
        state["cron_job_id"] = cron_job_id
    set_loop_state(runtime_sync.state, state)
    save_runtime_state(cwd, runtime_sync.state, remove_legacy=True)

    first_task = executable[0]
    # 构建清理提示（如有）
    cleanup_note = ""
    if stale_cleanup_reason:
        cleanup_note = f"\n🧹 已清理残留 state（{stale_cleanup_reason}）\n"

    # 构建返回数据
    start_data = {"state_file": str(state_path), "mode": "cron", "interval": interval}
    if cron_job_id:
        start_data["cron_job_id"] = cron_job_id
    else:
        start_data["cron_action"] = "create"  # 调用方需执行 CronCreate

    # 构建返回消息
    msg_body = (
        f"模式: cron | 间隔: {interval}\n"
        f"   活跃任务数: {active_count}\n"
        f"   最大任务数: {'∞(无限)' if effective_max == 0 else effective_max}\n"
        + (f"   CronJob ID: {cron_job_id}\n" if cron_job_id else
           "   ⚠️ 需调用方执行 CronCreate(cron={interval}, prompt=\"/drun --max-tasks 1\") 并注册 job_id\n")
        + f"{cleanup_note}"
    )
    message = (
        f"dloop cron 模式已配置 (interval: {interval}, max_tasks: {'∞' if effective_max == 0 else effective_max})\n"
        + (f"CronJob ID: {cron_job_id}" if cron_job_id else "需调用方创建 CronJob 并注册 job_id")
        + f"\n{cleanup_note}"
    )
    formatted = f"🔄 dloop cron 模式已配置\n{msg_body}"

    return {
        "ok": True,
        "status": "started",
        "data": start_data,
        "message": message,
        "formatted_text": formatted,
    }


def cmd_status(cwd: Path) -> dict:
    """查询 dloop 状态。T19: 固定语义，始终 exit 0。"""
    diwu_dir = cwd / DIWU_DIR

    # Stale-state 兜底（#23）：与 cmd_start 相同的三分类判定
    dtask_for_classify = _task_payload(cwd)
    settings = load_toml_or_empty(cwd / DSETTINGS_TOML)
    classification = classify(cwd, dtask_data=dtask_for_classify, settings=settings)
    if classification.is_stale:
        reason = classification.reason or "terminal_stale"
        cleanup_state(cwd)
        return {
            "ok": True,
            "status": "stale_cleaned",
            "data": {"cleanup_reason": reason},
            "message": f"已清理残留 state，原因：{reason}",
            "formatted_text": f"🧹 已清理残留 dloop state（{reason}）",
        }
    if classification.is_invalid:
        return _invalid_state_result(classification.reason)

    runtime_sync = sync_runtime_state(cwd, dtask_for_classify, persist=True)
    if runtime_sync.is_invalid:
        return _invalid_state_result(runtime_sync.reason)

    data = loop_state(runtime_sync.state)
    if data is None:
        return {
            "ok": True,
            "status": "no_loop",
            "formatted_text": "✅ 无活跃的 dloop 循环",
        }
    if not data.get("active"):
        return {
            "ok": True,
            "status": "inactive",
            "formatted_text": "⏸️ dloop 状态文件存在但非活跃状态",
        }

    completed = data.get("completed_task_ids", [])
    iteration = data.get("current_iteration", 0)
    max_t = data.get("max_tasks", 0)
    started = data.get("started_at", "?")

    return {
        "ok": True,
        "status": "running",
        "data": {
            "current_iteration": iteration,
            "completed_task_ids": completed,
            "max_tasks": max_t,
            "started_at": started,
            "mode": data.get("mode", "cron"),
            "cron_job_id": data.get("cron_job_id"),
        },
        "formatted_text": (
            f"🔄 dloop 运行中 [cron 模式]\n"
            f"   当前轮次: {iteration}\n"
            f"   已完成: {len(completed)} 个任务\n"
            f"   最大任务数: {max_t}\n"
            f"   启动时间: {started}"
            + (f"\n   CronJob ID: {data.get('cron_job_id')}" if data.get('cron_job_id') else "")
        ),
    }


def cmd_stop(cwd: Path) -> dict:
    """停止 dloop 循环。读取 dtask-state.json.dloop → 摘要 → 清除 → 持久化。
    cron 模式下额外调用 CronDelete 清理调度资源（P1）。"""
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
    loop_mode = dloop.get("mode", "cron")
    cron_job_id = dloop.get("cron_job_id")

    clear_loop_state(sync_result.state)
    save_runtime_state(cwd, sync_result.state, remove_legacy=True)

    stop_data = {
        "completed_count": completed_count,
        "iteration": iteration,
        "mode": loop_mode,
    }
    if loop_mode == "cron" and cron_job_id:
        stop_data["cron_job_id"] = cron_job_id
        stop_data["cron_action"] = "delete"  # 调用方需执行 CronDelete

    message = f"dloop 已取消（{loop_mode} 模式，已完成 {completed_count} 个任务，第 {iteration} 轮）"
    formatted = (
        f"✅ dloop 已取消 [{loop_mode} 模式]\n"
        f"   已完成任务数: {completed_count}\n"
        f"   当前轮次: {iteration}"
    )
    if loop_mode == "cron" and cron_job_id:
        message += f"，需调用方执行 CronDelete(id={cron_job_id})"
        formatted += f"\n   ⚠️ 需调用方执行 CronDelete(id={cron_job_id})"

    return {
        "ok": True,
        "status": "cancelled",
        **stop_data,
        "message": message,
        "formatted_text": formatted,
    }


def main():
    parser = argparse.ArgumentParser(description="diwu-loop 启动、状态查询与停止")
    sub = parser.add_subparsers(dest="command")

    # start 子命令
    p_start = sub.add_parser("start", help="启动 dloop 循环")
    p_start.add_argument("--cwd", type=str, default=".", help="项目根目录")
    p_start.add_argument("--max-tasks", type=int, default=None, help="最大任务数（省略=自动取活跃任务数，0=无限）")
    p_start.add_argument("--interval", type=str, default=None, help="Cron 触发间隔（如 3m, 5m）")
    p_start.add_argument("--cron-job-id", type=str, default=None, help="CronCreate 返回的 job_id（由调用方传入）")

    # status 子命令
    p_status = sub.add_parser("status", help="查询 dloop 状态")
    p_status.add_argument("--cwd", type=str, default=".", help="项目根目录")

    # stop 子命令
    p_stop = sub.add_parser("stop", help="停止 dloop 循环")
    p_stop.add_argument("--cwd", type=str, default=".", help="项目根目录")

    args = parser.parse_args()

    if args.command == "start":
        result = cmd_start(
            Path(args.cwd).resolve(),
            max_tasks=args.max_tasks,
            interval=args.interval,
            cron_job_id=args.cron_job_id,
        )
    elif args.command == "status":
        result = cmd_status(Path(args.cwd).resolve())
    elif args.command == "stop":
        result = cmd_stop(Path(args.cwd).resolve())
    else:
        parser.print_help()
        result = {"ok": True, "status": "help"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
