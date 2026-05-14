#!/usr/bin/env python3
"""diwu-flow dfeat_remote: dfeat 远程镜像业务编排层。

7 个子命令：create-issue / sync-labels / comment / close-issue / associate-pr / status / check。
所有操作 graceful skip：enabled=false 或 gh 不可用时返回 {ok:true, status:"skipped"}。

CLI: python3 scripts/dfeat_remote.py <command> --slug <slug> [--cwd <proj>] [--json]
     python3 scripts/dfeat_remote.py check [--cwd <proj>]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import load_toml_or_empty, save_toml, ensure_dir  # noqa: E402
from dfeat_crud import _find_feat_file, _load_feat, _save_feat  # noqa: E402
from github_client import GitHubClient, STAGE_LABEL_MAP  # noqa: E402

DFEAT_DIR = Path(".diwu") / "dfeat"
DCONFIG_PATH = Path(".diwu") / "dconfig.toml"

# ── 配置加载 ───────────────────────────────────────


def _load_github_config(cwd: Path) -> dict:
    """加载 [github] 配置，缺省值兜底。"""
    data = load_toml_or_empty(cwd / DCONFIG_PATH)
    gh = data.get("github", {})
    return {
        "enabled": gh.get("enabled", False),
        "repo": gh.get("repo", "") or _detect_repo(cwd),
        "issue_auto_create": gh.get("issue_auto_create", True),
        "label_prefix": gh.get("label_prefix", "df/"),
        "label_sync_on_transition": gh.get("label_sync_on_transition", True),
        "comment_on_closeout": gh.get("comment_on_closeout", True),
        "comment_on_gap": gh.get("comment_on_gap", True),
        "close_issue_on_done": gh.get("close_issue_on_done", True),
        "associate_pr_on_release": gh.get("associate_pr_on_release", True),
        "timeout": gh.get("timeout", 30),
    }


def _detect_repo(cwd: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(cwd), capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            url = r.stdout.strip()
            for prefix in ("git@github.com:", "https://github.com/", "git://github.com/"):
                if url.startswith(prefix):
                    return url[len(prefix):].removesuffix(".git")
    except Exception:
        pass
    return ""


def _get_client(cwd: Path) -> GitHubClient | None:
    """获取 GitHubClient；不可用时返回 None（调用方 skip）。"""
    cfg = _load_github_config(cwd)
    if not cfg["enabled"]:
        return None
    client = GitHubClient(repo=cfg["repo"], timeout=cfg["timeout"])
    if not client.available:
        return None
    return client


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result(ok: bool, status: str, **extra) -> dict:
    p = {"ok": ok, "status": status}
    p.update(extra)
    return p


def _remote_section(data: dict) -> dict:
    """获取 remote 段（确保存在）。"""
    r = data.get("remote")
    if not isinstance(r, dict):
        r = {}
        data["remote"] = r
    return r


def _set_remote_field(data: dict, key: str, value) -> None:
    """设置 remote 字段并同步 labels 子段。"""
    rem = _remote_section(data)
    rem[key] = value
    rem["last_synced_at"] = _now()


# ── 子命令 ─────────────────────────────────────────


def cmd_create_issue(slug: str, cwd: Path) -> dict:
    """为 dfeat 创建 GitHub Issue。"""
    path, _ = _find_feat_file(cwd, slug)
    if path is None:
        return _result(False, "not_found", message=f"未找到 '{slug}'")

    data = _load_feat(path)
    rem = _remote_section(data)

    if rem.get("issue_number", 0) > 0:
        return _result(True, "already_exists",
                        issue_number=rem["issue_number"],
                        issue_url=rem.get("issue_url", ""))

    client = _get_client(cwd)
    if client is None:
        return _result(True, "skipped", reason="gh 不可用或 [github] enabled=false")

    id_sec = data.get("id", {})
    bg = data.get("background", {})
    acc = data.get("acceptance", {})

    title = f"[{slug}] {id_sec.get('title', slug)}"
    body_lines = [
        f"## 摘要",
        f"",
        f"{bg.get('why', '')}",
        f"",
        f"**本轮目标**: {bg.get('this_round_goal', '')}",
        f"**类型**: {id_sec.get('type', '?')}",
        f"**阶段**: {data.get('current_state', {}).get('stage', 'InDraft')}",
        f"",
        f"## Acceptance",
    ]
    for i, c in enumerate(acc.get("criteria", []), 1):
        body_lines.append(f"{i}. {c}")
    body_lines += ["", "---", "*由 diwu-flow dfeat 自动创建*"]
    body = "\n".join(body_lines)

    stage = data.get("current_state", {}).get("stage", "InDraft")
    label = STAGE_LABEL_MAP.get(stage, "df/in-draft")

    result = client.create_issue(title, body, labels=[label])
    if result is None:
        return _result(False, "create_failed", message="gh issue create 失败")

    rem["issue_number"] = result["number"]
    rem["issue_url"] = result["url"]
    rem["issue_created_at"] = _now()
    rem["sync_status"] = "created"
    rem["last_synced_at"] = _now()
    rem.setdefault("labels", {})["current"] = label
    rem["labels"].setdefault("history", []).append(
        [label, _now(), stage]
    )

    _save_feat(data, path)
    return _result(True, "created", issue_number=result["number"],
                    issue_url=result["url"])


def cmd_sync_labels(slug: str, cwd: Path) -> dict:
    """根据当前 stage 同步 Issue label。"""
    path, _ = _find_feat_file(cwd, slug)
    if path is None:
        return _result(False, "not_found", message=f"未找到 '{slug}'")

    data = _load_feat(path)
    rem = _remote_section(data)
    issue_num = rem.get("issue_number", 0)

    if issue_num == 0:
        return _result(True, "no_issue", reason="尚未创建远程 Issue")

    client = _get_client(cwd)
    if client is None:
        return _result(True, "skipped")

    stage = data.get("current_state", {}).get("stage", "")
    new_label = STAGE_LABEL_MAP.get(stage)
    if not new_label:
        return _result(True, "no_mapping", message=f"无 label 映射: {stage}")

    old_label = rem.get("labels", {}).get("current", "")

    # 收集所有 df/ labels（保留非 df/ 的）
    all_labels = list(STAGE_LABEL_MAP.values())
    # 用新 label 替换旧 df/ label
    result = client.set_labels(issue_num, [new_label])
    if result is None:
        return _result(False, "sync_failed", message="gh label 设置失败")

    rem["labels"]["current"] = new_label
    rem["labels"].setdefault("history", []).append(
        [new_label, _now(), stage]
    )
    rem["sync_status"] = "labels_synced"
    rem["last_synced_at"] = _now()

    _save_feat(data, path)
    return _result(True, "labels_synced", old=old_label or "(none)",
                    new=new_label)


def cmd_comment(slug: str, cwd: Path, body: str = "",
                body_file: str = "") -> dict:
    """给 dfeat 对应的 Issue 添加评论。"""
    path, _ = _find_feat_file(cwd, slug)
    if path is None:
        return _result(False, "not_found", message=f"未找到 '{slug}'")

    data = _load_feat(path)
    rem = _remote_section(data)

    # 空 body 校验优先（调用方错误，与远程状态无关）
    if not body and not body_file:
        return _result(False, "empty_body", message="评论内容为空")

    if body_file:
        bf = Path(body_file)
        if bf.exists():
            body = bf.read_text(encoding="utf-8")
        else:
            return _result(False, "file_not_found", message=f"文件不存在: {body_file}")

    if not body:
        return _result(False, "empty_body", message="评论内容为空")

    issue_num = rem.get("issue_number", 0)
    if issue_num == 0:
        return _result(True, "no_issue")

    client = _get_client(cwd)
    if client is None:
        return _result(True, "skipped")

    result = client.add_comment(issue_num, body)
    if result is None:
        return _result(False, "comment_failed")

    rem["sync_status"] = "commented"
    rem["last_synced_at"] = _now()
    _save_feat(data, path)
    return _result(True, "commented", issue_url=result.get("url", ""))


def cmd_close_issue(slug: str, cwd: Path, reason: str = "") -> dict:
    """关闭 dfeat 对应的 Issue（Done 时触发）。"""
    path, _ = _find_feat_file(cwd, slug)
    if path is None:
        return _result(False, "not_found", message=f"未找到 '{slug}'")

    data = _load_feat(path)
    rem = _remote_section(data)
    issue_num = rem.get("issue_number", 0)

    if issue_num == 0:
        return _result(True, "no_issue")

    client = _get_client(cwd)
    if client is None:
        return _result(True, "skipped")

    comment_body = reason or f"已关闭 — dfeat [{slug}] 进入终态"
    result = client.close_issue(issue_num, comment=comment_body)
    if result is None:
        return _result(False, "close_failed")

    rem["sync_status"] = "closed"
    rem["last_synced_at"] = _now()
    _save_feat(data, path)
    return _result(True, "closed", issue_number=issue_num)


def cmd_associate_pr(slug: str, cwd: Path, commit_sha: str = "") -> dict:
    """关联 PR 到 dfeat remote 字段。"""
    path, _ = _find_feat_file(cwd, slug)
    if path is None:
        return _result(False, "not_found", message=f"未找到 '{slug}'")

    data = _load_feat(path)
    rem = _remote_section(data)
    issue_num = rem.get("issue_number", 0)

    if issue_num == 0:
        return _result(True, "no_issue")

    if not commit_sha:
        # 尝试从 HEAD 获取
        try:
            r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(cwd), capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                commit_sha = r.stdout.strip()
        except Exception:
            pass

    if not commit_sha:
        return _result(False, "no_commit", message="无法获取 commit SHA")

    client = _get_client(cwd)
    if client is None:
        return _result(True, "skipped")

    pr = client.find_pr_for_commit(commit_sha)
    if pr is None:
        return _result(True, "no_pr", sha=commit_sha[:8])

    rem["pr_number"] = pr["number"]
    rem["pr_url"] = pr["url"]
    rem["last_synced_at"] = _now()

    _save_feat(data, path)
    return _result(True, "pr_associated", pr_number=pr["number"],
                    pr_url=pr["url"], pr_title=pr.get("title", ""))


def cmd_status(slug: str, cwd: Path) -> dict:
    """显示 dfeat 远程镜像状态。"""
    path, _ = _find_feat_file(cwd, slug)
    if path is None:
        return _result(False, "not_found", message=f"未找到 '{slug}'")

    data = _load_feat(path)
    rem = data.get("remote", {})
    cfg = _load_github_config(cwd)

    info = {
        "ok": True,
        "status": "loaded",
        "slug": slug,
        "github_enabled": cfg["enabled"],
        "repo": cfg["repo"] or "(未配置)",
        "issue_number": rem.get("issue_number", 0),
        "issue_url": rem.get("issue_url", ""),
        "pr_number": rem.get("pr_number", 0),
        "pr_url": rem.get("pr_url", ""),
        "sync_status": rem.get("sync_status", "none"),
        "last_synced_at": rem.get("last_synced_at", ""),
        "doc_scope": rem.get("doc_scope", []),
        "trigger": rem.get("trigger", "manual"),
        "labels": rem.get("labels", {}),
    }
    return info


def cmd_check(cwd: Path) -> dict:
    """批量检查所有 dfeat 的远程状态。"""
    ddir = cwd / DFEAT_DIR
    if not ddir.is_dir():
        return {"ok": True, "status": "no_dfeat_dir", "items": []}

    cfg = _load_github_config(cwd)
    items = []
    has_enabled = False

    for f in sorted(ddir.iterdir()):
        if not f.is_file() or f.suffix != ".toml":
            continue
        if not (f.name.startswith("active_") or f.name.startswith("hold_")):
            continue
        slug = f.name.split("_", 1)[1].replace(".toml", "") if "_" in f.name else f.name.replace(".toml", "")
        try:
            st = cmd_status(slug, cwd)
            items.append(st)
            if st.get("issue_number", 0) > 0:
                has_enabled = True
        except Exception:
            items.append({"ok": False, "slug": slug, "error": "检查失败"})

    return {
        "ok": True,
        "status": "listed",
        "github_enabled": cfg["enabled"],
        "repo": cfg["repo"] or "(未配置)",
        "has_remote_issues": has_enabled,
        "items": items,
    }


# ── CLI 入口 ─────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="dfeat 远程镜像管理")
    sub = parser.add_subparsers(dest="command", required=True)

    def _add_common(p):
        p.add_argument("--cwd", type=str, default=".")
        p.add_argument("--json", action="store_true")

    p_ci = sub.add_parser("create-issue", help="为 dfeat 创建 GitHub Issue")
    _add_common(p_ci)
    p_ci.add_argument("--slug", required=True)

    p_sl = sub.add_parser("sync-labels", help="同步 stage → Issue label")
    _add_common(p_sl)
    p_sl.add_argument("--slug", required=True)

    p_cm = sub.add_parser("comment", help="给 Issue 添加评论")
    _add_common(p_cm)
    p_cm.add_argument("--slug", required=True)
    p_cm.add_argument("--body", default="", help="评论正文")
    p_cm.add_argument("--body-file", default="", help="从文件读取正文")

    p_cl = sub.add_parser("close-issue", help="关闭对应 Issue")
    _add_common(p_cl)
    p_cl.add_argument("--slug", required=True)
    p_cl.add_argument("--reason", default="", help="关闭原因")

    p_ap = sub.add_parser("associate-pr", help="关联 PR 到 dfeat")
    _add_common(p_ap)
    p_ap.add_argument("--slug", required=True)
    p_ap.add_argument("--commit", default="", dest="commit_sha", help="commit SHA")

    p_st = sub.add_parser("status", help="显示单个 dfeat 远程状态")
    _add_common(p_st)
    p_st.add_argument("--slug", required=True)

    p_ck = sub.add_parser("check", help="批量检查所有 dfeat 远程状态")
    _add_common(p_ck)

    args = parser.parse_args()
    cwd = Path(args.cwd).resolve()

    dispatch = {
        "create-issue": lambda: cmd_create_issue(args.slug, cwd),
        "sync-labels": lambda: cmd_sync_labels(args.slug, cwd),
        "comment": lambda: cmd_comment(args.slug, cwd, args.body, args.body_file),
        "close-issue": lambda: cmd_close_issue(args.slug, cwd, args.reason),
        "associate-pr": lambda: cmd_associate_pr(args.slug, cwd, args.commit_sha),
        "status": lambda: cmd_status(args.slug, cwd),
        "check": lambda: cmd_check(cwd),
    }

    payload = dispatch[args.command]()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(0 if payload.get("ok") else 1)


if __name__ == "__main__":
    main()
