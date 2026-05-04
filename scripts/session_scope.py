from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

_SESSION_FILE_PREFIX = ".claude_main_session"
_MIN_SESSION_ID_LEN = 5


def repo_hash(cwd: str | os.PathLike[str]) -> str:
    """Return a stable short fingerprint for a repository/worktree path."""
    resolved = Path(cwd).expanduser().resolve()
    return hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16]


def scoped_session_file(cwd: str | os.PathLike[str]) -> Path:
    return Path("/tmp") / f"{_SESSION_FILE_PREFIX}_{repo_hash(cwd)}"


def _valid_session_id(session_id: str) -> bool:
    return bool(session_id and len(session_id) >= _MIN_SESSION_ID_LEN)


def atomic_write_session_id(cwd: str | os.PathLike[str], session_id: str) -> Path | None:
    """Atomically persist the current Claude session id for this cwd scope."""
    if not cwd or not _valid_session_id(session_id):
        return None

    target = scoped_session_file(cwd)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(target.parent),
            prefix=f".{target.name}.",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(session_id.strip() + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, target)
        try:
            target.chmod(0o600)
        except OSError:
            pass
        return target
    except OSError:
        if tmp_path:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return None


def read_scoped_session_id(cwd: str | os.PathLike[str]) -> str:
    if not cwd:
        return ""
    try:
        content = scoped_session_file(cwd).read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return content if _valid_session_id(content) else ""
