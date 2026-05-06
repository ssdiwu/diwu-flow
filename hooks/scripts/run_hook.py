#!/usr/bin/env python3
"""Run a hook script with consistent output prefixing and failure policy.

The wrapper preserves machine-readable JSON stdout by prefixing human-facing
message fields inside the JSON instead of prepending text to the raw stream.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


LOG_PATH = ".diwu/logs/hooks.log"
MESSAGE_KEYS = {
    "additionalSystemPrompt",
    "additionalContext",
    "message",
    "reason",
    "suggestion",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="diwu-flow hook runner")
    parser.add_argument("--event", required=True, help="Hook event label")
    parser.add_argument("--script", required=True, help="Script filename under hooks/scripts")
    parser.add_argument(
        "--mode",
        choices=("strict", "tolerant"),
        required=True,
        help="strict preserves child exit code; tolerant downgrades failures to exit 0",
    )
    return parser.parse_args()


def _event_cwd(raw_stdin: str) -> str:
    try:
        event = json.loads(raw_stdin) if raw_stdin.strip() else {}
    except json.JSONDecodeError:
        event = {}
    cwd = event.get("cwd") if isinstance(event, dict) else ""
    return cwd if cwd and os.path.isdir(cwd) else os.getcwd()


def _prefixed_text(text: str, prefix: str) -> str:
    if not text:
        return ""
    result = []
    for line in text.splitlines(keepends=True):
        result.append(f"{prefix}{line}" if line.strip() else line)
    return "".join(result)


def _with_prefix(value: str, prefix: str) -> str:
    return value if value.startswith(prefix) else f"{prefix}{value}"


def _prefix_json_messages(value: Any, prefix: str) -> Any:
    if isinstance(value, dict):
        updated = {}
        for key, item in value.items():
            if key in MESSAGE_KEYS and isinstance(item, str) and item:
                updated[key] = _with_prefix(item, prefix)
            elif key == "messages" and isinstance(item, list):
                updated[key] = [
                    _with_prefix(message, prefix) if isinstance(message, str) and message else message
                    for message in item
                ]
            else:
                updated[key] = _prefix_json_messages(item, prefix)
        return updated
    if isinstance(value, list):
        return [_prefix_json_messages(item, prefix) for item in value]
    return value


def _emit_stdout(stdout: str, prefix: str) -> None:
    if not stdout:
        return
    stripped = stdout.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        sys.stdout.write(_prefixed_text(stdout, prefix))
        return
    sys.stdout.write(json.dumps(_prefix_json_messages(payload, prefix), ensure_ascii=False))
    sys.stdout.write("\n")


def _append_log(cwd: str, text: str) -> None:
    if not text:
        return
    path = os.path.join(cwd, LOG_PATH)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
    except OSError:
        pass


def main() -> int:
    args = _parse_args()
    raw_stdin = sys.stdin.read()
    cwd = _event_cwd(raw_stdin)
    script_dir = Path(__file__).resolve().parent
    script_path = script_dir / args.script
    prefix = f"[{args.event}/{args.script}] "

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        input=raw_stdin,
        text=True,
        cwd=cwd,
        capture_output=True,
    )

    _emit_stdout(completed.stdout, prefix)

    stderr = _prefixed_text(completed.stderr, prefix)
    if completed.returncode != 0:
        stderr += f"{prefix}exited with code {completed.returncode}\n"
    if stderr:
        sys.stderr.write(stderr)
        timestamp = datetime.now().isoformat(timespec="seconds")
        _append_log(cwd, "".join(f"{timestamp} {line}" if line.strip() else line for line in stderr.splitlines(True)))

    if args.mode == "tolerant":
        return 0
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
