from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WorktreeChanges:
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    diu_dirty: list[str] = field(default_factory=list)

    @property
    def has_code_changes(self) -> bool:
        return any(not p.startswith(".diwu/") for p in self.modified + self.untracked)

    @property
    def code_paths(self) -> list[str]:
        return [p for p in self.modified + self.untracked if p and not p.startswith(".diwu/")]

    @property
    def all_changed_files(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for p in self.modified + self.untracked:
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out

    @property
    def is_clean(self) -> bool:
        return not (self.modified or self.untracked)


@dataclass(frozen=True)
class GitMetadata:
    branch: str | None = None
    head_hash: str | None = None
    head_hash_full: str | None = None
    recent_commits: list[dict] = field(default_factory=list)
    is_git_repo: bool = True
    detached_head: bool = False


@dataclass(frozen=True)
class _IndexEntry:
    path: str
    mtime_ns: int
    size: int


_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".next",
}
_IGNORE_FILES = {
    ".DS_Store",
}
_DIU_PREFIXES = (
    ".diwu/dtask.json",
    ".diwu/dtask-state.json",
    ".diwu/recording/",
)


def _normalize_rel(path: str) -> str:
    return path.replace(os.sep, "/")


def _resolve_git_dir(cwd: str | Path) -> Path | None:
    cwd = Path(cwd)
    dotgit = cwd / ".git"
    if dotgit.is_dir():
        return dotgit
    if dotgit.is_file():
        try:
            content = dotgit.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        prefix = "gitdir:"
        if not content.startswith(prefix):
            return None
        raw = content[len(prefix):].strip()
        git_dir = Path(raw)
        if not git_dir.is_absolute():
            git_dir = (cwd / git_dir).resolve()
        return git_dir if git_dir.is_dir() else None
    return None


def _parse_git_index(index_path: Path) -> dict[str, _IndexEntry]:
    entries: dict[str, _IndexEntry] = {}
    try:
        data = index_path.read_bytes()
    except OSError:
        return entries

    if len(data) < 12 or data[:4] != b"DIRC":
        return entries

    try:
        version = struct.unpack(">I", data[4:8])[0]
        count = struct.unpack(">I", data[8:12])[0]
    except struct.error:
        return entries

    # Only v2/v3 share the fixed-width entry format handled below.
    # v4 uses path compression; degrade safely instead of misclassifying everything.
    if version not in (2, 3):
        return entries

    offset = 12
    for _ in range(count):
        entry_start = offset
        if offset + 62 > len(data):
            break
        try:
            fields = struct.unpack(">LLLLLLLLLL20sH", data[offset:offset + 62])
        except struct.error:
            break

        mtime_sec = fields[2]
        mtime_nsec = fields[3]
        size = fields[9]
        flags = fields[11]
        name_len_hint = flags & 0x0FFF

        name_start = offset + 62
        if name_len_hint < 0x0FFF:
            name_end = name_start + name_len_hint
            if name_end > len(data):
                break
        else:
            nul = data.find(b"\x00", name_start)
            if nul < 0:
                break
            name_end = nul

        try:
            rel = data[name_start:name_end].decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            break

        rel = _normalize_rel(rel)
        entries[rel] = _IndexEntry(
            path=rel,
            mtime_ns=(mtime_sec * 1_000_000_000) + mtime_nsec,
            size=size,
        )

        offset = name_end + 1
        while (offset - entry_start) % 8 != 0:
            offset += 1

    return entries


def _is_entry_modified(entry: _IndexEntry, st: os.stat_result) -> bool:
    if st.st_size != entry.size:
        return True
    return st.st_mtime_ns != entry.mtime_ns


def _mark_diu(rel: str, diu_dirty: list[str]) -> None:
    if any(rel.startswith(prefix) or rel == prefix for prefix in _DIU_PREFIXES):
        diu_dirty.append(rel)


def get_worktree_changes(cwd: str | Path = ".") -> WorktreeChanges:
    cwd = Path(cwd)
    git_dir = _resolve_git_dir(cwd)
    index_entries = _parse_git_index(git_dir / "index") if git_dir else {}

    modified: list[str] = []
    untracked: list[str] = []
    diu_dirty: list[str] = []
    seen: set[str] = set()

    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]

        for fname in files:
            if fname in _IGNORE_FILES:
                continue
            fpath = Path(root) / fname
            rel = _normalize_rel(os.path.relpath(fpath, cwd))
            seen.add(rel)

            entry = index_entries.get(rel)
            try:
                st = fpath.stat()
            except OSError:
                continue

            if entry is None:
                if rel.startswith(".diwu/"):
                    _mark_diu(rel, diu_dirty)
                else:
                    untracked.append(rel)
                continue

            if _is_entry_modified(entry, st):
                if rel.startswith(".diwu/"):
                    _mark_diu(rel, diu_dirty)
                else:
                    modified.append(rel)

    for rel in index_entries:
        if rel in seen:
            continue
        if rel.startswith(".diwu/"):
            _mark_diu(rel, diu_dirty)
        else:
            modified.append(rel)

    return WorktreeChanges(
        modified=sorted(set(modified)),
        untracked=sorted(set(untracked)),
        diu_dirty=sorted(set(diu_dirty)),
    )


def _find_packed_ref(git_dir: Path, ref_path: str) -> str | None:
    packed = git_dir / "packed-refs"
    if not packed.exists():
        return None
    try:
        for line in packed.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[1].strip() == ref_path:
                return parts[0].strip()
    except OSError:
        pass
    return None


def _read_git_object(git_dir: Path, obj_hash: str) -> bytes | None:
    if len(obj_hash) < 2:
        return None
    obj_path = git_dir / "objects" / obj_hash[:2] / obj_hash[2:]
    if not obj_path.exists():
        return None
    try:
        return zlib.decompress(obj_path.read_bytes())
    except (OSError, zlib.error):
        return None


def _read_commit_subject(git_dir: Path, obj_hash: str) -> str | None:
    raw = _read_git_object(git_dir, obj_hash)
    if raw is None:
        return None
    nul = raw.find(b"\x00")
    if nul < 0:
        return None
    body = raw[nul + 1:]
    try:
        text = body.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        return None
    sep = text.find("\n\n")
    if sep < 0:
        return None
    message = text[sep + 2:].split("\n", 1)[0].strip()
    return message or None


def _read_recent_hashes(git_dir: Path, head_hash: str | None, max_count: int = 10) -> list[str]:
    hashes: list[str] = []
    if head_hash:
        hashes.append(head_hash)

    head_log = git_dir / "logs" / "HEAD"
    if head_log.exists():
        try:
            for line in reversed(head_log.read_text(encoding="utf-8", errors="replace").splitlines()):
                parts = line.split(" ", 2)
                if len(parts) >= 2:
                    new_hash = parts[1].strip()
                    if len(new_hash) == 40 and new_hash not in hashes:
                        hashes.append(new_hash)
                    if len(hashes) >= max_count:
                        break
        except OSError:
            pass
    return hashes[:max_count]


def get_git_metadata(cwd: str | Path = ".") -> GitMetadata:
    cwd = Path(cwd)
    git_dir = _resolve_git_dir(cwd)
    if git_dir is None:
        return GitMetadata(is_git_repo=False)

    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return GitMetadata(is_git_repo=False)

    try:
        head_content = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return GitMetadata(is_git_repo=False)

    branch: str | None = None
    head_hash: str | None = None
    detached = False

    if head_content.startswith("ref: "):
        ref_path = head_content[5:].strip()
        if ref_path.startswith("refs/heads/"):
            branch = ref_path[len("refs/heads/"):]
        ref_file = git_dir / ref_path
        if ref_file.exists():
            try:
                head_hash = ref_file.read_text(encoding="utf-8").strip()
            except OSError:
                head_hash = None
        else:
            head_hash = _find_packed_ref(git_dir, ref_path)
    else:
        detached = True
        head_hash = head_content or None

    if not head_hash:
        return GitMetadata(branch=branch, is_git_repo=True, detached_head=detached)

    recent_commits: list[dict] = []
    for commit_hash in _read_recent_hashes(git_dir, head_hash, max_count=10):
        subject = _read_commit_subject(git_dir, commit_hash) or "(message unavailable)"
        recent_commits.append({
            "hash": commit_hash[:8],
            "subject": subject,
        })

    return GitMetadata(
        branch=branch,
        head_hash=head_hash[:8],
        head_hash_full=head_hash,
        recent_commits=recent_commits,
        is_git_repo=True,
        detached_head=detached,
    )


def get_project_snapshot(cwd: str | Path = ".") -> tuple[WorktreeChanges, GitMetadata]:
    return get_worktree_changes(cwd), get_git_metadata(cwd)
