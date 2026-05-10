#!/usr/bin/env python3
"""diwu-flow 共享工具函数库

T4: plugin_root() 从 __file__ 推导项目根目录
T5: load_json_* 系列不存在返回默认值，损坏时 error_exit
T6: error_exit() 输出 stderr JSON + exit(1)
T7: save_json() 原子写入（write tmp + os.replace）
T8: CLI 输出约定 stdout JSON {ok, status, data?}
T12: 损坏 JSON 自动检测 → error_exit

CLI 入口：python3 scripts/common.py --max-task-id --cwd <proj>
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None
try:
    import tomli_w
except ImportError:
    tomli_w = None

# ── 路径常量（集中管理，消除跨文件硬编码） ──
DIWU_DIR = ".diwu"
DTASK_JSON = ".diwu/dtask.json"
DTASK_STATE_JSON = ".diwu/dtask-state.json"
DSETTINGS_TOML = ".diwu/dsettings.toml"
# 向后兼容别名（一阶段过渡期）
DSETTINGS_JSON = DSETTINGS_TOML
RECORDING_DIR = ".diwu/recording"
ARCHIVE_DIR = ".diwu/archive"
DECISIONS_FILE = ".diwu/decisions.md"
PITFALLS_FILE = ".diwu/project-pitfalls.md"


def plugin_root() -> Path:
    """T4: 从本文件位置推导 diwu-flow 项目根目录（scripts/ 的父目录）。"""
    return Path(__file__).resolve().parent.parent


def _read_json(path: Path):
    """读取 JSON 文件。返回 (data, error_msg)。

    T5/T12: 不存在返回 (None, None) 供调用方决定默认值；
    损坏返回 (None, error_msg) 供调用方 error_exit。
    """
    if not path.exists():
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except (json.JSONDecodeError, OSError) as e:
        return None, f"JSON 解析失败: {e}"


def load_json_optional(path: Path, default=None):
    """T5: 加载可选 JSON。文件不存在返回 default；损坏则 error_exit 终止。"""
    data, err = _read_json(Path(path))
    if err:
        error_exit(err)
    return data if data is not None else default


def load_json_or_empty(path: Path):
    """T5: 加载 JSON。文件不存在返回 {}；损坏则 error_exit 终止。"""
    return load_json_optional(path, default={})


def save_json(data, path: Path):
    """T7: 原子写入 JSON（indent=2, ensure_ascii=False）。

    先写临时文件再 os.replace，保证写入原子性。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, str(path))
    except BaseException:
        os.unlink(tmp)
        raise


def ensure_dir(path: Path):
    """确保目录存在（含父目录）。"""
    Path(path).mkdir(parents=True, exist_ok=True)


# ─── TOML 读写工具 ─────────────────────────────────────

def load_toml_optional(path: Path, default=None):
    """加载可选 TOML 文件。不存在返回 default；损坏则 error_exit。"""
    if tomllib is None:
        error_exit("tomllib 需要 Python 3.11+")
    if not path.exists():
        return default
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        error_exit(f"TOML 解析失败 {path}: {e}")


def load_toml_or_empty(path: Path):
    """加载 TOML。文件不存在返回 {}；损坏则 error_exit。"""
    return load_toml_optional(path, default={})


def save_toml(data, path: Path):
    """原子写入 TOML 文件。"""
    if tomli_w is None:
        error_exit("tomli_w 未安装，请运行 pip install tomli-w")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(data, f)
        os.replace(tmp, str(path))
    except BaseException:
        os.unlink(tmp)
        raise


# ─── Task ID 分配器 ────────────────────────────────────

_NEXT_TASK_ID_FILE = ".diwu/next-task-id"


def _fallback_max_id(cwd: Path) -> int:
    """fallback 扫描 dtask.json 和 archive 取最大 task id。

    next-task-id 文件不存在或损坏时调用。
    连 dtask.json 都不存在时返回 0（从 1 开始分配）。
    """
    result = max_task_id(cwd)
    if result.get("ok"):
        return result["max_id"]
    return 0


def allocate_task_id(cwd: Path) -> dict:
    """分配下一个单调递增任务 ID。

    通过 .diwu/next-task-id 纯文本文件实现：
    - 文件不存在时从 dtask.json/archive 最大 id + 1 开始
    - 连 dtask.json 也不存在时从 1 开始
    - 连续调用返回 1,2,3,... 无重复无跳号
    - 使用 os.open + O_EXCL 保证并发安全

    Returns:
        {"ok": true, "task_id": N}
    """
    cwd = Path(cwd)
    id_file = cwd / _NEXT_TASK_ID_FILE
    ensure_dir(id_file.parent)

    # 原子读取当前值
    if id_file.exists():
        try:
            current = int(id_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            current = _fallback_max_id(cwd)
    else:
        # 文件不存在：fallback 扫描 dtask.json 取最大 id
        current = _fallback_max_id(cwd)

    next_id = current + 1

    # 原子写入：O_EXCL 防止并发冲突
    fd = None
    try:
        fd = os.open(str(id_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(next_id))
            f.write("\n")
        fd = None  # 已移交 fdopen
    except FileExistsError:
        # 并发竞争：回退到 read-modify-write 循环
        import time
        for attempt in range(10):
            time.sleep(0.01 * (attempt + 1))
            try:
                current = int(id_file.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                current = 0
            next_id = current + 1
            try:
                # 先写临时文件再 rename（跨平台原子替换）
                tmp_id = id_file.with_suffix(".tmp")
                tmp_id.write_text(f"{next_id}\n", encoding="utf-8")
                os.replace(str(tmp_id), str(id_file))
                break
            except FileNotFoundError:
                continue
        else:
            error_exit("无法分配 task ID：并发写入重试耗尽")

    return {"ok": True, "task_id": next_id}


def rel_time(ts_str: str) -> str:
    """将 ISO 时间戳转为六段相对时间格式。

    返回如 "3 分钟前" / "2 小时前" / "1 天前" / "2026-04-28"。
    """
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = delta.total_seconds()
    except (ValueError, TypeError):
        return ts_str

    if secs < 0:
        return ts_str
    if secs < 60:
        return "刚刚"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins} 分钟前"
    hours = mins // 60
    if hours < 24:
        return f"{hours} 小时前"
    days = hours // 24
    if days < 30:
        return f"{days} 天前"
    # 超过 30 天返回日期
    return dt.strftime("%Y-%m-%d")


def error_exit(message: str):
    """T6: 输出 stderr JSON 并以 exit code 1 终止。

    格式：{"ok": false, "error": "<message>"}
    """
    json.dump({"ok": False, "error": message}, sys.stderr, ensure_ascii=False)
    sys.exit(1)


# ─── CLI 入口 ──────────────────────────────────────────────

def max_task_id(cwd: Path) -> dict:
    """扫描 dtask.json 和 archive/ 返回最大任务 ID。

    T8 输出格式：
    {"ok": true, "max_id": N, "source": "dtask.json|archive|empty"}
    """
    cwd = Path(cwd)
    dtask_path = cwd / ".diwu" / "dtask.json"
    archive_dir = cwd / ".diwu" / "archive"

    max_id = 0
    source = "empty"

    # 1. 读 dtask.json
    data, err = _read_json(dtask_path)
    if err:
        return {"ok": False, "error": f"dtask.json 损坏: {err}"}
    if data and isinstance(data, dict):
        tasks = data.get("tasks", [])
        if tasks:
            ids = [t.get("id", 0) for t in tasks if isinstance(t, dict)]
            if ids:
                max_id = max(max_id, max(ids))
                source = "dtask.json"

    # 2. 扫描归档
    if archive_dir.is_dir():
        for f in archive_dir.glob("task_archive_*.json"):
            adata, aerr = _read_json(f)
            if aerr:
                continue
            if adata and isinstance(adata, dict):
                atasks = adata.get("tasks", [])
            elif adata and isinstance(adata, list):
                atasks = adata
            else:
                atasks = []
            if atasks:
                aids = [t.get("id", 0) for t in atasks if isinstance(t, dict)]
                if aids:
                    archive_max = max(aids)
                    if archive_max > max_id:
                        max_id = archive_max
                        source = f.name

    return {"ok": True, "max_id": max_id, "source": source}


def self_test() -> dict:
    """--self-test: 输出自身路径和可访问性诊断信息。"""
    self_path = Path(__file__).resolve()
    plugin = plugin_root()
    return {
        "ok": True,
        "self_path": str(self_path),
        "plugin_root": str(plugin),
        "exists": self_path.exists(),
        "readable": os.access(self_path, os.R_OK),
        "claude_plugin_root_env": os.environ.get("CLAUDE_PLUGIN_ROOT", "(not set)"),
    }


def main():
    parser = argparse.ArgumentParser(description="diwu-flow common utilities")
    parser.add_argument("--max-task-id", action="store_true", help="输出最大任务 ID")
    parser.add_argument("--allocate-task-id", action="store_true", help="分配下一个任务 ID")
    parser.add_argument("--self-test", action="store_true", help="输出自身路径和可访问性信息")
    parser.add_argument("--cwd", type=str, default=".", help="工作目录")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()

    if args.self_test:
        result = self_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.max_task_id:
        result = max_task_id(cwd)
        # T8: stdout JSON
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result.get("ok") else 1)

    if args.allocate_task_id:
        result = allocate_task_id(cwd)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result.get("ok") else 1)

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
