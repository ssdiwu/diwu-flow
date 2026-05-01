"""Task#168: 防硬编码路径回归测试。

扫描所有插件源码文件，禁止：
1. 绝对路径硬编码（/Users/、/home/ 等）
2. hook 脚本用 os.getcwd() 解析项目路径（应使用 event.cwd 或参数传入）
3. commands/*.md 用相对路径引用插件内部脚本（应使用 ${CLAUDE_PLUGIN_ROOT}）

允许的白名单：
- Path(__file__) 动态推导（含 .resolve()、.parent 等链式调用）
- 注释/文档中的示例路径（用于说明而非执行）
- 测试断言中检查"不应包含"的断言模式
- .diwu/ 和 .claude/ 项目相对路径（运行时数据，正确用法）
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
HOOKS_SCRIPTS_DIR = PROJECT_ROOT / "hooks" / "scripts"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
COMMANDS_DIR = PROJECT_ROOT / "commands"
SKILLS_DIR = PROJECT_ROOT / "skills"

# ── 扫描目标 ──────────────────────────────────────────────

SOURCE_PY_DIRS = [
    HOOKS_SCRIPTS_DIR,
    SCRIPTS_DIR,
]

# 绝对路径模式：匹配 /Users/xxx、/home/xxx、/opt/local 等用户级绝对路径
ABSOLUTE_PATH_PATTERN = re.compile(
    r'(?:^|["\s\'(=/])'
    r'/(?:Users|home|opt/local|usr/local)[/\w]'
)

# os.getcwd() 用于路径拼接的模式（排除纯注释行和 or fallback 模式）
GETCWD_PATH_PATTERN = re.compile(
    r'os\.getcwd\(\)'
)
# 合法的 fallback 模式：event.get("cwd") or os.getcwd()
GETCWD_FALLBACK_PATTERN = re.compile(
    r'\bor\s+os\.getcwd\(\)'
)
# 合法的 __file__ fallback 模式：globals().get("__file__", os.getcwd()...)
GETCWD_FILE_FALLBACK_PATTERN = re.compile(
    r'globals\(\)\.get\("__file__"\s*,.*?os\.getcwd\(\)'
)

# commands 中引用插件脚本的相对路径模式（如 python3 scripts/xxx.py）
COMMAND_RELATIVE_SCRIPT_PATTERN = re.compile(
    r'python3\s+scripts/[a-zA-Z_]'
)


def _is_comment_or_docstring(line: str, prev_lines: list[str] | None = None) -> bool:
    """判断一行是否为注释或 docstring 内部。"""
    stripped = line.strip()
    if stripped.startswith('#'):
        return True
    # 三引号 docstring 内部（简化判断：缩进 > 0 且看起来像字符串内容）
    if prev_lines:
        # 检查前一行是否开启了三引号
        for pl in reversed(prev_lines):
            if '"""' in pl or "'''" in pl:
                # 简单启发：如果当前行不是关闭三引号，视为 docstring 内部
                if '"""' not in stripped and "'''" not in stripped:
                    return True
                break
    return False


def _scan_py_files(directory: Path) -> list[tuple[Path, int, str]]:
    """扫描目录下所有 .py 文件，返回 [(文件, 行号, 内容)]。"""
    results = []
    if not directory.is_dir():
        return results
    for py_file in sorted(directory.glob("*.py")):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            results.append((py_file, i, line))
    return results


class TestNoHardcodedAbsolutePaths:
    """P0: 插件源码中不允许出现硬编码绝对路径。"""

    def test_hook_scripts_no_absolute_paths(self):
        """hooks/scripts/*.py 不含 /Users/、/home/ 等绝对路径（Path(__file__) 除外）。"""
        offenders = []
        for fpath, lineno, line in _scan_py_files(HOOKS_SCRIPTS_DIR):
            # 跳过 Path(__file__) 动态推导行
            if '__file__' in line:
                continue
            # 跳过注释行
            if _is_comment_or_docstring(line):
                continue
            match = ABSOLUTE_PATH_PATTERN.search(line)
            if match:
                offenders.append(f"{fpath.name}:{lineno}: {line.strip()}")
        assert offenders == [], (
            "发现硬编码绝对路径（应使用 Path(__file__) 或参数传入 cwd）：\n"
            + "\n".join(offenders)
        )

    def test_scripts_no_absolute_paths(self):
        """scripts/*.py 不含硬编码绝对路径（Path(__file__) 除外）。"""
        offenders = []
        for fpath, lineno, line in _scan_py_files(SCRIPTS_DIR):
            if '__file__' in line:
                continue
            if _is_comment_or_docstring(line):
                continue
            match = ABSOLUTE_PATH_PATTERN.search(line)
            if match:
                offenders.append(f"{fpath.name}:{lineno}: {line.strip()}")
        assert offenders == [], (
            "发现硬编码绝对路径：\n" + "\n".join(offenders)
        )


class TestHookScriptsUseEventCwd:
    """P1: hook 脚本不得用 os.getcwd() 解析项目路径。"""

    def test_no_getcwd_for_path_resolution(self):
        """hooks/scripts/*.py 不得在非注释行中使用 os.getcwd() 做路径拼接。

        正确做法：从 stdin event 的 cwd 字段获取，或通过参数传入。
        白名单：or os.getcwd() 作为 event.get("cwd") 的 fallback 是合法的。
        """
        offenders = []
        for fpath, lineno, line in _scan_py_files(HOOKS_SCRIPTS_DIR):
            if _is_comment_or_docstring(line):
                continue
            if GETCWD_PATH_PATTERN.search(line) and not GETCWD_FALLBACK_PATTERN.search(line) and not GETCWD_FILE_FALLBACK_PATTERN.search(line):
                offenders.append(f"{fpath.name}:{lineno}: {line.strip()}")
        assert offenders == [], (
            "hook 脚本使用了 os.getcwd()（应改用 event.cwd 或 cwd 参数）：\n"
            + "\n".join(offenders)
        )


class TestCommandsUsePluginRoot:
    """P1: commands/*.md 引用插件脚本必须使用 ${CLAUDE_PLUGIN_ROOT}。"""

    def test_commands_reference_scripts_via_plugin_root(self):
        """commands/*.md 中的可执行命令引用 scripts/ 时须带 ${CLAUDE_PLUGIN_ROOT} 前缀。

        用户在自家项目目录执行命令，相对路径 scripts/ 会解析到错误位置。
        """
        if not COMMANDS_DIR.is_dir():
            return
        offenders = []
        for md_file in sorted(COMMANDS_DIR.glob("*.md")):
            lines = md_file.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines, 1):
                # 跳过纯说明文字（不含代码块标记的行不在代码块内时跳过）
                # 但 markdown 代码块内的命令需要检查
                match = COMMAND_RELATIVE_SCRIPT_PATTERN.search(line)
                if match and '${CLAUDE_PLUGIN_ROOT}' not in line:
                    offenders.append(f"{md_file.name}:{i}: {line.strip()}")
        assert offenders == [], (
            "commands 引用插件脚本缺少 ${CLAUDE_PLUGIN_ROOT} 前缀：\n"
            + "\n".join(offenders)
            + "\n\n正确写法示例：python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dtask_transition.py ..."
        )

    def test_no_bare_python3_scripts_in_commands(self):
        """commands/*.md 中不得出现无任何路径限定的 python3 scripts/... 形式。

        即使在代码块内也不允许——Claude Code 执行时代码块的 cwd 是用户项目目录。
        """
        if not COMMANDS_DIR.is_dir():
            return
        offenders = []
        bare_pattern = re.compile(r'(?<!\w)python3\s+scripts/')
        for md_file in sorted(COMMANDS_DIR.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            for m in bare_pattern.finditer(text):
                lineno = text[:m.start()].count('\n') + 1
                offenders.append(f"{md_file.name}:{lineno}: {m.group().strip()}")
        assert offenders == [], (
            "commands 中存在裸 python3 scripts/ 引用：\n"
            + "\n".join(offenders)
        )
