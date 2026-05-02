"""session_start.py project-pitfalls.md 自动注入行为验证"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
SESSION_START = PROJECT_ROOT / "hooks" / "scripts" / "session_start.py"
MAX_PITFALLS_LEN = 8000  # 与 session_start.py 中的上限一致


def _run_session_start(cwd: str, stdin_data: dict = None) -> dict:
    """执行 session_start.py 并解析 JSON 输出"""
    env = os.environ.copy()
    input_json = json.dumps(stdin_data or {"cwd": cwd})
    result = subprocess.run(
        ["python3", str(SESSION_START)],
        input=input_json,
        capture_output=True,
        text=True,
        env=env,
        cwd=PROJECT_ROOT,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return {}


def _extract_injected(prompt: str) -> str:
    """从 additionalSystemPrompt 中提取 pitfalls 注入部分"""
    marker = "项目历史踩坑经验"
    if marker in prompt:
        return prompt[prompt.index(marker):]
    return ""


def test_no_pitfalls_file():
    """文件不存在时不注入、不报错"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        output = _run_session_start(tmpdir)
        assert "项目历史踩坑经验" not in output.get("additionalSystemPrompt", "")


def test_empty_pitfalls_file():
    """空文件不注入"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        pitfalls = os.path.join(diwu, "project-pitfalls.md")
        Path(pitfalls).write_text("", encoding="utf-8")
        output = _run_session_start(tmpdir)
        assert "项目历史踩坑经验" not in output.get("additionalSystemPrompt", "")


def test_pure_template_skipped():
    """纯模板文件（仅含 HTML 注释和占位行，无真实数据行）不注入（P1）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        pitfalls = os.path.join(diwu, "project-pitfalls.md")
        # dinit 复制的原始模板：HTML 注释 + 占位表格，零真实数据行
        Path(pitfalls).write_text(
            "<!-- project-pitfalls.md.template -->\n"
            "<!-- 自动生成标注 -->\n\n"
            "# 项目高频误判表\n\n"
            "## 环境相关\n\n"
            "| 现象 | 默认先查 | 暂不下结论 | 何时下结论 |\n"
            "|------|---------|-----------|------------|\n"
            "| （示例：占位，请替换为本项目实际误判） | | | |\n\n"
            "## 数据相关\n\n"
            "| 现象 | 默认先查 | 暂不下结论 | 何时下结论 |\n"
            "|------|---------|-----------|------------|\n"
            "| （示例：占位，请替换为本项目实际误判） | | | |",
            encoding="utf-8",
        )
        output = _run_session_start(tmpdir)
        assert "项目历史踩坑经验" not in output.get("additionalSystemPrompt", "")


def test_template_header_with_real_data_injected():
    """保留模板头注释但填入真实条目时正常注入（P1 修复验证）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        pitfalls = os.path.join(diwu, "project-pitfalls.md")
        # 用户在原模板上追加真实条目（保留 HTML 注释头）
        Path(pitfalls).write_text(
            "<!-- project-pitfalls.md.template -->\n\n"
            "# 项目高频误判表\n\n"
            "## 环境漂移\n\n"
            "| 现象 | 根因 | 正确做法 | 来源 |\n"
            "|------|------|---------|------|\n"
            "| CI 超时 | 缺代理配置 | 检查 CI 环境变量 | session-001.md |\n"
            "| 本地通过远程失败 | 环境差异 | 加集成测试 | session-002.md |",
            encoding="utf-8",
        )
        output = _run_session_start(tmpdir)
        prompt = output.get("additionalSystemPrompt", "")
        assert "项目历史踩坑经验" in prompt
        assert "CI 超时" in prompt
        assert "环境漂移" in prompt


def test_real_pitfalls_injected():
    """纯真实踩坑数据正常注入"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        pitfalls = os.path.join(diwu, "project-pitfalls.md")
        Path(pitfalls).write_text(
            "# 项目踩坑聚合表\n\n## 环境漂移\n\n"
            "| 现象 | 根因 | 正确做法 | 来源 |\n"
            "|------|------|---------|------|\n"
            "| 测试通过但 CI 超时 | CI 缺代理 | 检查 CI 配置 | session-003.md |",
            encoding="utf-8",
        )
        output = _run_session_start(tmpdir)
        prompt = output.get("additionalSystemPrompt", "")
        assert "项目历史踩坑经验" in prompt
        assert "环境漂移" in prompt
        assert "测试通过但 CI 超时" in prompt


def test_long_content_hard_capped():
    """超长内容硬上限严格不超过 MAX_PITFALLS_LEN + 固定包装头开销（摘要模式）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        pitfalls = os.path.join(diwu, "project-pitfalls.md")
        # 单 section 超大数据集（摘要模式下现象列含增长后缀，远超 8000）
        lines = ["# 项目踩坑聚合表\n\n## 巨型类别\n\n| 现象 | 根因 | 正确做法 | 来源 |"]
        lines.append("|------|------|---------|------|")
        for j in range(300):
            lines.append(f"| 超长现象描述-{j} {j * 'word'} | 根因-{j} | 做法-{j} | session-big-{j}.md |")
        long_content = "\n".join(lines)
        assert len(long_content) > MAX_PITFALLS_LEN * 1.5
        Path(pitfalls).write_text(long_content, encoding="utf-8")

        output = _run_session_start(tmpdir)
        prompt = output.get("additionalSystemPrompt", "")
        injected = _extract_injected(prompt)
        assert injected, "应有注入内容"

        # 包装头固定开销（标题行 + 说明行 + 底部提示）
        WRAPPER_HEADER_LEN = 150
        assert len(injected) <= MAX_PITFALLS_LEN + WRAPPER_HEADER_LEN, (
            f"注入长度 {len(injected)} 超过数据上限 {MAX_PITFALLS_LEN} + 包装头 {WRAPPER_HEADER_LEN}"
        )
        assert "[...]" in injected or "已裁剪" in injected, "应有裁剪标记"


def test_multi_section_long_content_truncated():
    """多 section 长内容裁剪到最近 section 边界并标注"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        pitfalls = os.path.join(diwu, "project-pitfalls.md")
        # 多个 section，总长 >4000
        lines = ["# 项目踩坑聚合表"]
        for i in range(20):
            lines.append(f"\n## 类别{i}\n\n| 现象 | 根因 | 正确做法 | 来源 |")
            lines.append("|------|------|---------|------|")
            for j in range(10):
                lines.append(f"| 现象{i}-{j} | 根因{i}-{j} | 做法{i}-{j} | s{i}.md |")
        long_content = "\n".join(lines)
        assert len(long_content) > MAX_PITFALLS_LEN
        Path(pitfalls).write_text(long_content, encoding="utf-8")

        output = _run_session_start(tmpdir)
        prompt = output.get("additionalSystemPrompt", "")
        injected = _extract_injected(prompt)
        assert injected
        assert len(injected) <= len(long_content), "应比原文短"
        # 应包含尾部最新 section 或裁剪标记
        assert ("已裁剪" in injected or "类别19" in injected)


def test_truncation_never_cuts_newest_category_mid_section():
    """P1 修复验证：裁剪多类别后最新类别必须完整，不能切成半段"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diwu = os.path.join(tmpdir, ".diwu")
        os.makedirs(diwu)
        pitfalls = os.path.join(diwu, "project-pitfalls.md")
        # 10 个类别，每类 30 条现象（摘要远超 8000），最新类别命名为 z-最新类
        lines = ["# 项目踩坑聚合表"]
        for cat_i in range(10):
            lines.append(f"\n## 类别{cat_i}\n\n| 现象 | 根因 | 正确做法 | 来源 |")
            lines.append("|------|------|---------|------|")
            for j in range(30):
                lines.append(
                    f"| 类别{cat_i}-现象-{j} 这是一段足够长的描述文本用于填满摘要空间 |"
                    f" 根因-{cat_i}-{j} | 做法-{cat_i}-{j} | s{cat_i}-{j}.md |"
                )
        long_content = "\n".join(lines)
        assert len(long_content) > MAX_PITFALLS_LEN * 2
        Path(pitfalls).write_text(long_content, encoding="utf-8")

        output = _run_session_start(tmpdir)
        prompt = output.get("additionalSystemPrompt", "")
        injected = _extract_injected(prompt)
        assert injected
        assert "已裁剪早期类别" in injected, "多类别应触发裁剪标记"

        # 最新类别（类别9）必须完整出现——所有 30 条现象无一丢失
        for j in range(30):
            assert f"类别9-现象-{j}" in injected, (
                f"最新类别条目 类别9-现象-{j} 不应被截断丢失"
            )

        # 最早类别应已被裁剪
        assert "类别0-现象-0" not in injected, "最早类别应已被裁剪"


def test_coexists_with_existing_prompt():
    """pitfalls 内容使用 get+拼接模式，不覆盖已有 additionalSystemPrompt"""
    source = Path(SESSION_START).read_text(encoding="utf-8")
    assert 'result.get("additionalSystemPrompt", "")' in source
    assert "pitfalls_section =" in source
    assign_lines = [l for l in source.split("\n") if "additionalSystemPrompt" in l and "=" in l and "result[" in l]
    assert len(assign_lines) >= 2, f"应有多次赋值（追加模式），实际: {assign_lines}"
