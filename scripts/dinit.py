#!/usr/bin/env python3
"""diwu-flow dinit: 项目初始化多子命令脚本。

6 个子命令：scan-repo / sync-rules / sync-skills / create-config / migrate-legacy / validate。
AI 保留：Step 0(模式检测) / Step 1(信息收集) / Step 5(架构约束) / Step 6(git)。
T13: create-config 用 --*-file 传路径；T19: 固定语义 {ok, status, data?}；所有路径 exit 0。
"""

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from common import ensure_dir, load_json_or_empty, plugin_root, load_toml_or_empty, load_toml_optional, save_json, save_toml  # noqa: E402

PLUGIN_ROOT = plugin_root()
ASSETS_DIR = PLUGIN_ROOT / "assets" / "dinit" / "assets"
RULES_SRC = ASSETS_DIR / "rules"
MANIFEST_PATH = ASSETS_DIR / "rules-manifest.json"


def _load_json(path: Path):
    """加载 JSON，不存在返回 None，损坏抛异常。"""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _copy_file(src: Path, dst: Path) -> str:
    """复制文件，返回状态字符串（NEW/SAME/UPDATED）。"""
    if not src.exists():
        return "ERROR_SRC_MISSING"
    if dst.exists():
        if src.read_text(encoding="utf-8") == dst.read_text(encoding="utf-8"):
            return "SAME"
        shutil.copy2(str(src), str(dst))
        return "UPDATED"
    ensure_dir(dst.parent)
    shutil.copy2(str(src), str(dst))
    return "NEW"


def cmd_scan_repo(cwd: Path) -> dict:
    """扫描项目目录结构、技术栈、关键文件。"""
    result = {
        "directories": [],
        "tech_stack": {},
        "key_files": {},
    }

    # 目录结构扫描（1-2 层）
    dirs = []
    for p in sorted(cwd.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            try:
                file_count = len(list(p.rglob("*"))) if p.is_dir() else 0
                # 封顶到 9999，保持整数类型
                file_count = min(file_count, 9999)
                dirs.append({"name": f"{p.name}/", "purpose": "", "file_count_estimate": file_count})
            except OSError:
                dirs.append({"name": f"{p.name}/", "purpose": "(权限限制)", "file_count_estimate": 0})
    result["directories"] = dirs

    # 技术栈检测
    tech = {}
    pkg_files = {
        "package.json": ("node", "npm"),
        "requirements.txt": ("python", "pip"),
        "pyproject.toml": ("python", "pip/poetry"),
        "go.mod": ("go", "go modules"),
        "Cargo.toml": ("rust", "cargo"),
        "pom.xml": ("java", "maven"),
        "build.gradle": ("java/gradle", "gradle"),
        "Gemfile": ("ruby", "bundler"),
        "composer.json": ("php", "composer"),
    }
    for fname, (lang, mgr) in pkg_files.items():
        f = cwd / fname
        if f.exists():
            tech["language"] = lang
            tech["package_manager"] = mgr
            # 尝试提取更多信息
            if fname == "package.json":
                data = load_json_or_empty(f)
                if data:
                    deps = list(data.get("dependencies", {}).keys())[:5]
                    if deps:
                        tech["framework_deps_sample"] = deps
            break

    # 检测测试框架
    test_indicators = [
        ("__tests__", "jest/vitest"), ("test", "pytest/jest"), ("spec", "rspec/jest"),
        ("*.test.ts", "vitest/jest"), ("*_test.py", "pytest"), ("*_test.go", "go testing"),
    ]
    for pattern, fw in test_indicators:
        matches = list(cwd.glob(pattern))
        if matches:
            tech["test_framework_hint"] = fw
            break

    result["tech_stack"] = tech

    # 关键文件识别
    key_files = {}
    for candidate in ["README.md", "README.rst", "README", ".gitignore",
                      "Makefile", "Dockerfile", "docker-compose.yml",
                      "jenkinsfile", ".github/workflows"]:
        f = cwd / candidate
        if f.exists():
            key_files[candidate] = str(f.relative_to(cwd))

    # 入口文件猜测
    entry_patterns = ["main.ts", "main.js", "index.ts", "index.js",
                     "main.go", "lib.rs", "__init__.py", "app.py"]
    entry_files = []
    for ep in entry_patterns:
        found = list(cwd.glob(f"**/{ep}"))
        if found:
            entry_files.append(str(found[0].relative_to(cwd)))
    if entry_files:
        key_files["entry_files"] = entry_files[:5]

    result["key_files"] = key_files

    return {
        "ok": True,
        "status": "scanned",
        "data": result,
        "formatted_text": (
            f"📂 扫描完成\n"
            f"   目录数: {len(dirs)}\n"
            f"   语言: {tech.get('language', '未知')}\n"
            f"   包管理: {tech.get('package_manager', '未知')}\n"
            f"   关键文件: {len(key_files)} 个"
        ),
    }


def cmd_sync_rules(cwd: Path) -> dict:
    """按 rules-manifest.json 同步 rules 到 .claude/rules/。"""
    target_dir = cwd / ".claude" / "rules"

    # 读 manifest，缺失时降级为全目录复制
    if not MANIFEST_PATH.exists():
        print("⚠️  rules-manifest.json 缺失，降级为全目录复制", file=sys.stderr)
        rule_names = sorted(p.name for p in RULES_SRC.glob("*.md") if p.is_file())
    else:
        manifest = load_json_or_empty(MANIFEST_PATH)
        rule_names = manifest.get("rules", [])
        if not isinstance(rule_names, list):
            rule_names = []

    files_report = []
    counts = {"total": len(rule_names), "new": 0, "same": 0, "updated": 0}

    for name in rule_names:
        src = RULES_SRC / name
        dst = target_dir / name
        status = _copy_file(src, dst)
        files_report.append({"name": name, "status": status})
        if status == "NEW":
            counts["new"] += 1
        elif status == "SAME":
            counts["same"] += 1
        elif status == "UPDATED":
            counts["updated"] += 1

    return {
        "ok": True,
        "status": "synced",
        "data": {"files": files_report, "summary": counts},
        "formatted_text": (
            f"📋 Rules 同步完成\n"
            f"   总计: {counts['total']} | 新增: {counts['new']} | "
            f"跳过: {counts['same']} | 更新: {counts['updated']}"
        ),
    }


def _find_skills_dir() -> Path | None:
    """探测 CC 实际使用的 skills 目录。

    优先级：
    1. CLAUDE_PLUGIN_ROOT 环境变量所在插件的 skills/
    2. .claude/plugins/marketplaces/ 下匹配插件的 skills/（CC 安装后的标准位置）
    3. PLUGIN_ROOT/skills/（开发时 fallback）
    """
    import glob as _g

    # 1. 环境变量
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if env_root:
        env_skills = Path(env_root) / "skills"
        if (env_skills / "drec" / "SKILL.md").exists():
            return env_skills

    # 2. Marketplace: 找到包含 skills/drec/SKILL.md 的 marketplace 目录
    plugins_dir = Path.home() / ".claude" / "plugins" / "marketplaces"
    if plugins_dir.is_dir():
        for mp in sorted(plugins_dir.iterdir()):
            mp_skills = mp / "skills"
            if (mp_skills / "drec" / "SKILL.md").exists():
                return mp_skills

    # 3. Cache: .claude/plugins/cache/ 下匹配
    cache_dir = Path.home() / ".claude" / "plugins" / "cache"
    if cache_dir.is_dir():
        for cp in sorted(cache_dir.iterdir()):
            cp_skills = cp / "skills"
            if (cp_skills / "drec" / "SKILL.md").exists():
                return cp_skills

    # 4. Fallback: PLUGIN_ROOT (仓库根目录)
    fallback = PLUGIN_ROOT / "skills"
    if (fallback / "drec" / "SKILL.md").exists():
        return fallback

    return None


def cmd_sync_skills(cwd: Path) -> dict:
    """创建 .agents/skills/ 下各 skill 的 symlink 指向 plugin skills 目录。"""
    skills_src = _find_skills_dir()
    if skills_src is None:
        skills_src = PLUGIN_ROOT / "skills"  # 最终 fallback
    target_dir = cwd / ".agents" / "skills"

    if not skills_src.is_dir():
        return {"ok": False, "status": "skills_dir_missing",
                "message": f"skills/ 目录不存在: {skills_src}"}

    ensure_dir(target_dir)

    symlinks_report = []
    created = skipped = fixed = broken = 0

    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir():
            continue
        if not (skill_dir / "SKILL.md").exists():
            continue

        name = skill_dir.name
        link_path = target_dir / name
        real_target = skills_src / name
        # 使用绝对路径作为 symlink target——相对路径的深度取决于 cwd 到
        # target 的目录层级差，浅路径 clone 会断链；绝对路径对同机始终有效。
        expected_target = str(real_target.resolve())

        if link_path.exists() or link_path.is_symlink():
            if link_path.is_symlink():
                current_target = os.readlink(str(link_path))
                resolved = Path(link_path.parent / current_target).resolve()
                if current_target == expected_target and resolved.exists():
                    skipped += 1
                    symlinks_report.append({"name": name, "target": expected_target, "status": "SKIPPED"})
                    continue
                elif current_target == expected_target and not resolved.exists():
                    # 路径正确但目标不可达（broken）→ 重建
                    broken += 1
                    link_path.unlink()
                    repair_kind = "FIXED_BROKEN"
                else:
                    # 错误路径 → 删除重建
                    fixed += 1
                    link_path.unlink()
                    repair_kind = "FIXED_WRONG"
            else:
                # 不是 symlink → 跳过用户自定义
                skipped += 1
                symlinks_report.append({"name": name, "target": expected_target, "status": "USER_CUSTOM"})
                continue
        else:
            repair_kind = None

        # 创建新 symlink（含修复重建和全新创建）
        try:
            os.symlink(expected_target, str(link_path))
            if repair_kind == "FIXED_BROKEN":
                symlinks_report.append({"name": name, "target": expected_target, "status": "FIXED"})
            elif repair_kind == "FIXED_WRONG":
                symlinks_report.append({"name": name, "target": expected_target, "status": "FIXED"})
            else:
                created += 1
                symlinks_report.append({"name": name, "target": expected_target, "status": "CREATED"})
        except OSError as e:
            symlinks_report.append({"name": name, "target": expected_target, "status": f"ERROR: {e}"})

    total = created + skipped + fixed + broken
    return {
        "ok": True,
        "status": "synced",
        "data": {"symlinks": symlinks_report, "summary": {"total": total, "created": created, "skipped": skipped, "fixed": fixed, "broken": broken}},
        "formatted_text": (
            f"🔗 Skills Symlink 同步完成\n"
            f"   总计: {total} | 新建: {created} | 跳过: {skipped} | 修复: {fixed} | 坏链修复: {broken}"
        ),
    }


def cmd_create_config(cwd: Path, project_info_file: str | None = None,
                      scan_result_file: str | None = None) -> dict:
    """从模板创建项目配置文件（CLAUDE.md、dtask.toml、runtime dirs）。

    T13: 通过 --project-info-file 和 --scan-result-file 传入数据。
    """
    diwu_dir = cwd / ".diwu"
    claude_dir = cwd / ".claude"
    report = {"files": [], "summary": {"total": 0, "created": 0, "skipped": 0, "error": 0}}

    def _record(path_str: str, status: str):
        report["files"].append({"path": path_str, "status": status})
        report["summary"]["total"] += 1
        if status == "CREATED":
            report["summary"]["created"] += 1
        elif status == "SKIPPED":
            report["summary"]["skipped"] += 1
        else:
            report["summary"]["error"] += 1

    # 加载输入数据
    project_info = {}
    if project_info_file:
        p = Path(project_info_file)
        if p.exists():
            project_info = load_json_or_empty(p) or {}

    scan_result = {}
    if scan_result_file:
        s = Path(scan_result_file)
        if s.exists():
            scan_result = load_json_or_empty(s) or {}

    proj_name = project_info.get("name", cwd.name)
    proj_desc = project_info.get("description", "")

    # 4.1 CLAUDE.md
    claude_md = claude_dir / "CLAUDE.md"
    template = ASSETS_DIR / "claude-md-portable.template"
    if template.exists() and not claude_md.exists():
        content = template.read_text(encoding="utf-8")
        # 简单占位符替换（完整填充由 AI 在 Step 4 子代理中完成）
        content = content.replace("{PROJECT_NAME}", proj_name)
        content = content.replace("{PROJECT_DESCRIPTION}", proj_desc)
        ensure_dir(claude_dir)
        claude_md.write_text(content, encoding="utf-8")
        _record(str(claude_md.relative_to(cwd)), "CREATED")
    elif claude_md.exists():
        _record(str(claude_md.relative_to(cwd)), "SKIPPED")
    else:
        _record(str(claude_md.relative_to(cwd)), "ERROR_NO_TEMPLATE")

    # 4.2 dtask.toml
    ensure_dir(diwu_dir)
    dtask = diwu_dir / "dtask.toml"
    dtask_template = ASSETS_DIR / "task.toml.template"
    if not dtask.exists():
        if dtask_template.exists():
            shutil.copy2(str(dtask_template), str(dtask))
        else:
            from common import save_toml
            save_toml({"tasks": []}, dtask)
        _record(str(dtask.relative_to(cwd)), "CREATED")
    else:
        _record(str(dtask.relative_to(cwd)), "SKIPPED")

    # 4.4-4.6 运行时目录
    for runtime_dir in ["recording", "archive"]:
        rp = diwu_dir / runtime_dir
        if not rp.exists():
            rp.mkdir(parents=True, exist_ok=True)
            _record(str(rp.relative_to(cwd)), "CREATED")
        else:
            _record(str(rp.relative_to(cwd)), "SKIPPED")

    # 4.7 dsettings.toml
    dsettings = diwu_dir / "dsettings.toml"
    ds_template = ASSETS_DIR / "dsettings.toml.template"
    if not dsettings.exists() and ds_template.exists():
        shutil.copy2(str(ds_template), str(dsettings))
        _record(str(dsettings.relative_to(cwd)), "CREATED")
    elif dsettings.exists():
        _record(str(dsettings.relative_to(cwd)), "SKIPPED")

    # 4.8 project-pitfalls.md
    pitfalls = diwu_dir / "project-pitfalls.md"
    pp_template = ASSETS_DIR / "project-pitfalls.md.template"
    if not pitfalls.exists() and pp_template.exists():
        shutil.copy2(str(pp_template), str(pitfalls))
        _record(str(pitfalls.relative_to(cwd)), "CREATED")
    elif pitfalls.exists():
        _record(str(pitfalls.relative_to(cwd)), "SKIPPED")

    # 4.9 smoke.sh
    checks_dir = diwu_dir / "checks"
    smoke = checks_dir / "smoke.sh"
    smoke_template = ASSETS_DIR / "smoke.sh.template"
    if not smoke.exists() and smoke_template.exists():
        ensure_dir(checks_dir)
        shutil.copy2(str(smoke_template), str(smoke))
        smoke.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXOTH)
        _record(str(smoke.relative_to(cwd)), "CREATED")
    elif smoke.exists():
        _record(str(smoke.relative_to(cwd)), "SKIPPED")

    return {
        "ok": True,
        "status": "created",
        "data": report,
        "formatted_text": (
            f"📦 配置文件创建完成\n"
            f"   新建: {report['summary']['created']} | "
            f"跳过: {report['summary']['skipped']} | "
            f"错误: {report['summary']['error']}"
        ),
    }


def _convert_dsettings_json_to_toml(json_path: Path, toml_path: Path) -> dict:
    """将旧 dsettings.json 转换为 dsettings.toml（含键名映射）。

    旧格式 (.json) → 新格式 (.toml)，键名按 Issue #31 D3 映射表转换。
    不返回错误——JSON 损坏时返回空映射，由调用方决定是否继续。
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": False, "reason": "json_parse_failed"}

    result = {}
    # 顶层键映射
    key_map = {
        "task_archive_threshold": "task_archive_limit",
        "recording_archive_threshold": "recording_file_limit",
        "review_limit": "dloop_review_cap",
        "context_monitor_warning": "ctxmon_warn_at",
        "context_monitor_critical": "ctxmon_checkpoint_at",
        "context_monitor_delay": "ctxmon_checkpoint_delay",
    }
    passthrough = {
        "recording_keep_days", "dloop_max_consecutive",
        "error_tracking_enabled",
    }
    for old_key, new_key in key_map.items():
        if old_key in data:
            result[new_key] = data[old_key]
    for key in passthrough:
        if key in data:
            result[key] = data[key]

    # 嵌套 table → 摊平顶层
    if "drift_detection" in data and isinstance(data["drift_detection"], dict):
        result["drift_enabled"] = data["drift_detection"].get("enabled", True)
    if "recording_reminder" in data and isinstance(data["recording_reminder"], dict):
        result["reminder_on_taskdone"] = data["recording_reminder"].get("enabled", True)

    if not result:
        return {"ok": False, "reason": "no_mappable_keys"}

    save_toml(result, toml_path)

    if not _verify_roundtrip(result, toml_path):
        toml_path.unlink(missing_ok=True)
        return {"ok": False, "reason": "roundtrip_mismatch"}

    return {"ok": True}


def _verify_roundtrip(original: Any, toml_path: Path) -> bool:
    """写入 TOML 后回读，与原始数据深度比对。"""
    from common import load_toml_or_empty

    reloaded = load_toml_or_empty(toml_path)
    return _deep_equal(original, reloaded)


def _deep_equal(a: Any, b: Any) -> bool:
    """递归深度比对，兼容 dict/list/scalar。"""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_deep_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_deep_equal(x, y) for x, y in zip(a, b))
    return a == b


def _convert_dtask_json_to_toml(json_path: Path, toml_path: Path) -> dict:
    """将旧 dtask.json 转换为 dtask.toml。

    JSON schema: {"tasks": [...]} → TOML [[tasks]].
    无需键名映射，结构完全兼容。
    写入后回读 TOML 与原始 JSON 做 round-trip 比对，不一致则删除 TOML 并返回失败。
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": False, "reason": "json_parse_failed"}

    if not isinstance(data, dict) or "tasks" not in data:
        return {"ok": False, "reason": "invalid_schema"}

    save_toml(data, toml_path)

    if not _verify_roundtrip(data, toml_path):
        toml_path.unlink(missing_ok=True)
        return {"ok": False, "reason": "roundtrip_mismatch"}

    return {"ok": True}


def _convert_dtask_state_json_to_toml(json_path: Path, toml_path: Path) -> dict:
    """将旧 dtask-state.json 转换为 dtask-state.toml。

    清除 None 值（tomli_w 不支持），其余结构不变。
    写入后回读 TOML 与清除 None 后的数据做 round-trip 比对。
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": False, "reason": "json_parse_failed"}

    if not isinstance(data, dict):
        return {"ok": False, "reason": "invalid_schema"}

    def _remove_none(obj):
        if isinstance(obj, dict):
            return {k: _remove_none(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [_remove_none(v) for v in obj if v is not None]
        return obj

    cleaned = _remove_none(data)
    save_toml(cleaned, toml_path)

    if not _verify_roundtrip(cleaned, toml_path):
        toml_path.unlink(missing_ok=True)
        return {"ok": False, "reason": "roundtrip_mismatch"}

    return {"ok": True}


def cmd_migrate_legacy(cwd: Path) -> dict:
    """检测旧版 v0.x 标志并执行迁移。"""
    claude_rules = cwd / ".claude" / "rules"
    states_old = claude_rules / "states.md"
    task_new = claude_rules / "task.md"

    is_legacy = states_old.exists() and not task_new.exists()

    # 检测旧运行时文件
    old_runtime_patterns = [
        (cwd / ".claude" / "recording", cwd / ".diwu" / "recording"),
        (cwd / ".claude" / "decisions.md", cwd / ".diwu" / "decisions.md"),
        (cwd / ".claude" / "dsettings.json", cwd / ".diwu" / "dsettings.toml"),
        (cwd / ".claude" / "project-pitfalls.md", cwd / ".diwu" / "project-pitfalls.md"),
        (cwd / ".claude" / "archive", cwd / ".diwu" / "archive"),
        (cwd / ".claude" / "continue-here.md", cwd / ".diwu" / "continue-here.md"),
        (cwd / ".claude" / "checks", cwd / ".diwu" / "checks"),
    ]

    migrations = []
    has_old_runtime = False
    for old_path, new_path in old_runtime_patterns:
        if old_path.exists() and not new_path.parent.exists():
            has_old_runtime = True
            break

    actions = []

    # 迁移旧版 ideas archive（v0.1.0 的 status: archived → v0.1.1 物理移动）
    # 始终执行，不依赖其他旧版标志检测
    ideas_dir = cwd / ".diwu" / "ideas"
    ideas_archive_dir = ideas_dir / "archived"
    ideas_migrated = 0
    if ideas_dir.is_dir():
        for idea_file in sorted(ideas_dir.glob("*.md")):
            try:
                content = idea_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            fm_block = parts[1]
            for line in fm_block.splitlines():
                stripped = line.strip()
                if stripped.startswith("status:") and "archived" in stripped.split(":", 1)[-1].strip().lower():
                    ensure_dir(ideas_archive_dir)
                    dest = ideas_archive_dir / idea_file.name
                    if not dest.exists():
                        shutil.move(str(idea_file), str(dest))
                        ideas_migrated += 1
                        actions.append(f"迁移归档想法: {idea_file.name} → ideas/archived/")
                    break

    if ideas_migrated:
        actions.insert(0, f"ideas 归档迁移: {ideas_migrated} 个文件（status: archived → 物理移动）")

    # 归档文件 JSON→TOML 迁移
    archive_dir = cwd / ".diwu" / "archive"
    if archive_dir.is_dir():
        for json_file in sorted(archive_dir.glob("task_archive_*.json")):
            toml_file = json_file.with_suffix(".toml")
            if not toml_file.exists():
                try:
                    raw = _load_json(json_file)
                    if raw is not None:
                        save_toml(raw, toml_file)
                        backup_path = json_file.with_suffix(".json.backup")
                        if not backup_path.exists():
                            shutil.copy2(str(json_file), str(backup_path))
                        json_file.unlink()
                        actions.append(f"归档格式转换: {json_file.name} → .toml")
                except Exception as e:
                    actions.append(f"归档转换失败 ({e}): {json_file.name}")

        # summary 文件同理
        summary_json = archive_dir / ".last_archive_summary.json"
        summary_toml = archive_dir / ".last_archive_summary.toml"
        if summary_json.exists() and not summary_toml.exists():
            try:
                raw = _load_json(summary_json)
                if raw is not None:
                    save_toml(raw, summary_toml)
                    backup_path = summary_json.with_suffix(".json.backup")
                    if not backup_path.exists():
                        shutil.copy2(str(summary_json), str(backup_path))
                    summary_json.unlink()
                    actions.append(f"summary 格式转换: .last_archive_summary.json → .toml")
            except Exception as e:
                actions.append(f"summary 转换失败 ({e})")

    if not is_legacy and not has_old_runtime and not actions:
        return {
            "ok": True,
            "status": "no_migration_needed",
            "data": {"is_legacy": False, "has_old_runtime": False},
            "message": "未检测到旧版格式或旧运行时文件，无需迁移",
            "formatted_text": "✅ 无需迁移（非旧版且无旧运行时文件）",
        }

    if is_legacy:
        # 备份 states.md
        backup = claude_rules / "states.md.backup"
        if not backup.exists():
            shutil.copy2(str(states_old), str(backup))
            actions.append(f"备份 states.md → states.md.backup")

    # dsettings JSON→TOML 转换（在文件迁移之前，优先处理格式转换）
    for dsettings_json_path in (
        cwd / ".claude" / "dsettings.json",
        cwd / ".diwu" / "dsettings.json",
    ):
        if dsettings_json_path.exists():
            dsettings_toml_path = cwd / ".diwu" / "dsettings.toml"
            if not dsettings_toml_path.exists():
                result = _convert_dsettings_json_to_toml(dsettings_json_path, dsettings_toml_path)
                if result.get("ok"):
                    actions.append(f"dsettings 格式转换: JSON → TOML ({dsettings_json_path.name})")
                    backup_path = dsettings_json_path.with_suffix(".json.backup")
                    if not backup_path.exists():
                        shutil.copy2(str(dsettings_json_path), str(backup_path))
                        actions.append(f"备份: {dsettings_json_path.name} → .backup")
                    dsettings_json_path.unlink()
                    actions.append(f"删除旧: {dsettings_json_path.name}")
                else:
                    actions.append(f"dsettings 转换失败 ({result.get('reason')}): {dsettings_json_path.name}")

    # dtask JSON→TOML 转换
    for dtask_json_path in (
        cwd / ".diwu" / "dtask.json",
        cwd / ".claude" / "dtask.json",
    ):
        if dtask_json_path.exists():
            dtask_toml_path = cwd / ".diwu" / "dtask.toml"
            if not dtask_toml_path.exists():
                result = _convert_dtask_json_to_toml(dtask_json_path, dtask_toml_path)
                if result.get("ok"):
                    actions.append(f"dtask 格式转换: JSON → TOML ({dtask_json_path.name})")
                    backup_path = dtask_json_path.with_suffix(".json.backup")
                    if not backup_path.exists():
                        shutil.copy2(str(dtask_json_path), str(backup_path))
                        actions.append(f"备份: {dtask_json_path.name} → .backup")
                    dtask_json_path.unlink()
                    actions.append(f"删除旧: {dtask_json_path.name}")
                else:
                    actions.append(f"dtask 转换失败 ({result.get('reason')}): {dtask_json_path.name}")

    # dtask-state JSON→TOML 转换
    for state_json_path in (
        cwd / ".diwu" / "dtask-state.json",
        cwd / ".claude" / "dtask-state.json",
    ):
        if state_json_path.exists():
            state_toml_path = cwd / ".diwu" / "dtask-state.toml"
            if not state_toml_path.exists():
                result = _convert_dtask_state_json_to_toml(state_json_path, state_toml_path)
                if result.get("ok"):
                    actions.append(f"dtask-state 格式转换: JSON → TOML ({state_json_path.name})")
                    backup_path = state_json_path.with_suffix(".json.backup")
                    if not backup_path.exists():
                        shutil.copy2(str(state_json_path), str(backup_path))
                        actions.append(f"备份: {state_json_path.name} → .backup")
                    state_json_path.unlink()
                    actions.append(f"删除旧: {state_json_path.name}")
                else:
                    actions.append(f"dtask-state 转换失败 ({result.get('reason')}): {state_json_path.name}")

    # 迁移旧运行时文件
    migrated_count = 0
    for old_path, new_path in old_runtime_patterns:
        if old_path.exists():
            if old_path.is_dir():
                if not new_path.exists():
                    shutil.copytree(str(old_path), str(new_path))
                    migrated_count += 1
                    actions.append(f"迁移目录: {old_path.name} → .diwu/{old_path.name}")
            else:
                # 跳过 dsettings（已单独处理格式转换）
                if "dsettings.json" in str(old_path):
                    continue
                ensure_dir(new_path.parent)
                if not new_path.exists():
                    shutil.copy2(str(old_path), str(new_path))
                    migrated_count += 1
                    actions.append(f"迁移文件: {old_path.name} → .diwu/{old_path.name}")

    return {
        "ok": True,
        "status": "migrated" if actions else "no_action",
        "data": {
            "is_legacy": is_legacy,
            "has_old_runtime": has_old_runtime,
            "actions": actions,
            "migrated_count": migrated_count,
            "ideas_migrated": ideas_migrated,
        },
        "formatted_text": (
            f"🔄 迁移完成\n"
            f"   旧版: {'是' if is_legacy else '否'} | "
            f"旧运行时文件: {'是' if has_old_runtime else '否'}\n"
            f"   迁移操作数: {len(actions)}"
            + (f"\n   ideas 归档迁移: {ideas_migrated} 个文件" if ideas_migrated else "")
        ),
    }


def cmd_validate(cwd: Path) -> dict:
    """运行验证清单（Step 7 的自动化版本）。"""
    checks = []
    all_passed = True

    def check(name: str, condition: bool, message: str = ""):
        nonlocal all_passed
        status = "PASS" if condition else "FAIL"
        checks.append({"name": name, "status": status, "message": message})
        if not condition:
            all_passed = False

    # 基础文件
    claude_md = cwd / ".claude" / "CLAUDE.md"
    check("CLAUDE.md 存在", claude_md.exists(), str(claude_md) if claude_md.exists() else "不存在")
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        check("CLAUDE.md 无 @rules/ 引用", "@rules/" not in content)
        check("CLAUDE.md ≤200 行", len(content.splitlines()) <= 200, f"{len(content.splitlines())} 行")

    dtask = cwd / ".diwu" / "dtask.toml"
    check("dtask.toml 合法 TOML", _is_valid_toml(dtask))

    # Rules
    rules_dir = cwd / ".claude" / "rules"
    if MANIFEST_PATH.exists():
        manifest = load_json_or_empty(MANIFEST_PATH)
        expected_rules = manifest.get("rules", [])
        for r in expected_rules:
            check(f"Rule 存在: {r}", (rules_dir / r).exists())

    # Skills
    skills_dir = cwd / ".agents" / "skills"
    skills_src = _find_skills_dir() or (PLUGIN_ROOT / "skills")
    skill_count = 0
    if skills_src.is_dir():
        for sd in skills_src.iterdir():
            if sd.is_dir() and (sd / "SKILL.md").exists():
                skill_count += 1
                link = skills_dir / sd.name
                if link.is_symlink():
                    target = os.readlink(str(link))
                    resolved = Path(link.parent / target).resolve()
                    real_target = skills_src / sd.name
                    real_resolved = real_target.resolve()
                    if resolved == real_resolved and real_resolved.exists():
                        check(f"Skill symlink 正确: {sd.name}", True)
                    elif not real_resolved.exists():
                        check(f"Skill symlink 正确: {sd.name}", False,
                              f"broken symlink: target={target} -> {resolved} 不存在（期望 {real_resolved}）")
                    else:
                        check(f"Skill symlink 正确: {sd.name}", False,
                              f"wrong target: expected={real_resolved} actual={resolved}")

    # 运行时目录
    for d in ["recording", "archive"]:
        check(f".diwu/{d}/ 存在", (cwd / ".diwu" / d).is_dir())

    # 旧版残留检查
    check("无旧 states.md", not (rules_dir / "states.md").exists())
    check("无旧 recording.md", not (cwd / ".claude" / "recording.md").exists())

    # 清理 .dinit/ 临时工作目录
    dinit_tmp = cwd / ".diwu" / ".dinit"
    if dinit_tmp.is_dir():
        try:
            shutil.rmtree(str(dinit_tmp))
            check(".diwu/.dinit/ 已清理", True)
        except OSError as exc:
            check(".diwu/.dinit/ 清理失败", False, str(exc))

    passed_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {
        "ok": True,  # T19: always exit 0
        "status": "passed" if all_passed else "failed",
        "data": {
            "all_passed": all_passed,
            "checks": checks,
            "summary": {"total": len(checks), "passed": passed_count, "failed": fail_count},
        },
        "formatted_text": (
            f"✅ 验证完成 ({passed_count}/{len(checks)} 通过)"
            if all_passed else
            f"⚠️ 验证完成 ({passed_count}/{len(checks)} 通过, {fail_count} 失败)"
        ),
    }


def cmd_run(cwd: Path) -> dict:
    """自动编排入口：检测模式并执行所需步骤。

    AI/用户只需调用此入口，脚本自动完成可自动化部分。
    返回结果包含 mode 和每步执行状态，AI 据此决定是否需要交互式操作。
    """
    root = cwd.resolve()
    task_md = root / ".claude" / "rules" / "task.md"
    is_init_mode = not task_md.exists()

    results = {
        "ok": True,
        "mode": "init" if is_init_mode else "refresh",
        "steps": [],
    }

    def _step(name, fn):
        """执行一步并记录结果。"""
        try:
            r = fn(root)
            status = "ok" if r.get("ok") else "fail"
        except Exception as e:
            r = {"ok": False, "error": str(e)}
            status = "error"
        results["steps"].append({"name": name, "status": status, "detail": r})
        return r

    # Step A: 迁移（始终执行，幂等）
    _step("migrate-legacy", lambda c: cmd_migrate_legacy(c))

    # Step B: 资产同步（始终执行）
    _step("sync-rules", lambda c: cmd_sync_rules(c))
    _step("sync-skills", lambda c: cmd_sync_skills(c))

    if is_init_mode:
        # 初始化模式：扫描 + 创建配置 + 验证
        _step("scan-repo", lambda c: cmd_scan_repo(c))
        # create-config 需要 project-info 和 scan-result，这里先跳过
        # 由 AI 在拿到 scan 结果后自行调用 create-config
        results["next_actions"] = [
            "collect_project_info",  # AI 需要问用户
            "create_config",         # AI 调 create-config --project-info-file ... --scan-result-file ...
        ]
    else:
        # 刷新模式：直接验证
        results["next_actions"] = []

    # 最后验证
    _step("validate", lambda c: cmd_validate(c))

    return results


def _is_valid_json(path: Path) -> bool:
    """检查是否为合法 JSON。"""
    if not path.exists():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except (json.JSONDecodeError, OSError):
        return False


def _is_valid_toml(path: Path) -> bool:
    """检查是否为合法 TOML。"""
    if not path.exists():
        return False
    try:
        with open(path, "rb") as f:
            tomllib.load(f)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="diwu-flow 项目初始化")
    sub = parser.add_subparsers(dest="command")

    # run (auto orchestration)
    p_run = sub.add_parser("run", help="自动编排入口：检测模式并执行初始化/刷新")
    p_run.add_argument("--cwd", type=str, default=".")

    # scan-repo
    p_scan = sub.add_parser("scan-repo", help="扫描项目目录结构和技术栈")
    p_scan.add_argument("--cwd", type=str, default=".")

    # sync-rules
    p_rules = sub.add_parser("sync-rules", help="同步 rules 文件到 .claude/rules/")
    p_rules.add_argument("--cwd", type=str, default=".")

    # sync-skills
    p_skills = sub.add_parser("sync-skills", help="创建 skills symlink 到 .agents/skills/")
    p_skills.add_argument("--cwd", type=str, default=".")

    # create-config
    p_config = sub.add_parser("create-config", help="创建项目配置文件")
    p_config.add_argument("--project-info-file", type=str, default=None)
    p_config.add_argument("--scan-result-file", type=str, default=None)
    p_config.add_argument("--cwd", type=str, default=".")

    # migrate-legacy
    p_migrate = sub.add_parser("migrate-legacy", help="检测并迁移旧版格式")
    p_migrate.add_argument("--cwd", type=str, default=".")

    # validate
    p_val = sub.add_parser("validate", help="运行初始化验证清单")
    p_val.add_argument("--cwd", type=str, default=".")

    args = parser.parse_args()
    cwd = Path(args.cwd).resolve()

    commands_map = {
        "run": lambda: cmd_run(cwd),
        "scan-repo": lambda: cmd_scan_repo(cwd),
        "sync-rules": lambda: cmd_sync_rules(cwd),
        "sync-skills": lambda: cmd_sync_skills(cwd),
        "create-config": lambda: cmd_create_config(
            cwd, args.project_info_file, args.scan_result_file),
        "migrate-legacy": lambda: cmd_migrate_legacy(cwd),
        "validate": lambda: cmd_validate(cwd),
    }

    result = commands_map.get(args.command, lambda: {"ok": True, "status": "help"})()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
