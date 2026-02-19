"""내장 도구 시스템 테스트예요."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from codial_service.app.tools.base import BaseTool, ToolResult
from codial_service.app.tools.defaults import build_default_tool_registry
from codial_service.app.tools.file_read import FileReadTool
from codial_service.app.tools.file_write import FileWriteTool
from codial_service.app.tools.glob import GlobTool
from codial_service.app.tools.grep import GrepTool
from codial_service.app.tools.hashline import (
    build_hash_to_lineno_map,
    format_lines_with_hash,
    generate_line_hash,
    resolve_hash_to_index,
)
from codial_service.app.tools.hashline_edit import HashlineEditTool
from codial_service.app.tools.registry import ToolRegistry
from codial_service.app.tools.shell import ShellTool
from codial_service.app.tools.web_fetch import WebFetchTool

# ─── ToolRegistry 테스트 ───


class _DummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "테스트용 더미 도구예요."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"msg": {"type": "string"}}}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(ok=True, output=f"echo: {arguments.get('msg', '')}")


@pytest.mark.asyncio
async def test_registry_register_and_call() -> None:
    registry = ToolRegistry()
    registry.register(_DummyTool())
    assert "dummy" in registry
    assert len(registry) == 1
    result = await registry.call("dummy", {"msg": "hello"})
    assert result.ok is True
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_registry_call_unknown_tool() -> None:
    registry = ToolRegistry()
    result = await registry.call("no_such_tool", {})
    assert result.ok is False
    assert "등록되지 않은" in result.error


def test_registry_unregister() -> None:
    registry = ToolRegistry()
    registry.register(_DummyTool())
    assert registry.unregister("dummy") is True
    assert "dummy" not in registry
    assert registry.unregister("dummy") is False


def test_registry_to_provider_specs() -> None:
    registry = ToolRegistry()
    registry.register(_DummyTool())
    specs = registry.to_provider_specs()
    assert len(specs) == 1
    assert specs[0].name == "dummy"
    assert specs[0].description == "테스트용 더미 도구예요."


def test_default_registry_has_all_tools() -> None:
    registry = build_default_tool_registry(workspace_root=".")
    expected = {"web_fetch", "shell", "file_read", "file_write", "hashline_edit", "glob", "grep"}
    assert set(registry.list_names()) == expected


# ─── ShellTool 테스트 ───


@pytest.mark.asyncio
async def test_shell_tool_echo(tmp_path: Path) -> None:
    tool = ShellTool(workspace_root=str(tmp_path))
    result = await tool.execute({"command": "echo 'hello world'"})
    assert result.ok is True
    assert "hello world" in result.output


@pytest.mark.asyncio
async def test_shell_tool_nonzero_exit(tmp_path: Path) -> None:
    tool = ShellTool(workspace_root=str(tmp_path))
    result = await tool.execute({"command": "exit 42"})
    assert result.ok is False
    assert "42" in result.error


@pytest.mark.asyncio
async def test_shell_tool_timeout(tmp_path: Path) -> None:
    tool = ShellTool(workspace_root=str(tmp_path), timeout_seconds=0.5)
    result = await tool.execute({"command": "sleep 10"})
    assert result.ok is False
    assert "초과" in result.error


@pytest.mark.asyncio
async def test_shell_tool_missing_command() -> None:
    tool = ShellTool()
    result = await tool.execute({})
    assert result.ok is False


# ─── FileReadTool 테스트 (Hashline 포맷) ───


@pytest.mark.asyncio
async def test_file_read_tool_hashline_format(tmp_path: Path) -> None:
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n", encoding="utf-8")
    tool = FileReadTool(workspace_root=str(tmp_path))
    result = await tool.execute({"path": "test.txt"})
    assert result.ok is True
    # hashline 포맷: "줄번호:해시| 내용"
    h1 = generate_line_hash("line1")
    h3 = generate_line_hash("line3")
    assert f"1:{h1}| line1" in result.output
    assert f"3:{h3}| line3" in result.output


@pytest.mark.asyncio
async def test_file_read_tool_with_offset(tmp_path: Path) -> None:
    test_file = tmp_path / "test.txt"
    test_file.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    tool = FileReadTool(workspace_root=str(tmp_path))
    result = await tool.execute({"path": "test.txt", "offset": 3, "limit": 2})
    assert result.ok is True
    h_c = generate_line_hash("c")
    h_d = generate_line_hash("d")
    assert f"3:{h_c}| c" in result.output
    assert f"4:{h_d}| d" in result.output
    h_a = generate_line_hash("a")
    assert f"1:{h_a}| a" not in result.output


@pytest.mark.asyncio
async def test_file_read_tool_directory(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "file.txt").touch()
    tool = FileReadTool(workspace_root=str(tmp_path))
    result = await tool.execute({"path": str(tmp_path)})
    assert result.ok is True
    assert "sub/" in result.output
    assert "file.txt" in result.output


@pytest.mark.asyncio
async def test_file_read_tool_not_found(tmp_path: Path) -> None:
    tool = FileReadTool(workspace_root=str(tmp_path))
    result = await tool.execute({"path": "nonexistent.txt"})
    assert result.ok is False


# ─── FileWriteTool 테스트 ───


@pytest.mark.asyncio
async def test_file_write_tool(tmp_path: Path) -> None:
    tool = FileWriteTool(workspace_root=str(tmp_path))
    result = await tool.execute({"path": "output.txt", "content": "hello\nworld"})
    assert result.ok is True
    written = (tmp_path / "output.txt").read_text(encoding="utf-8")
    assert written == "hello\nworld"


@pytest.mark.asyncio
async def test_file_write_tool_creates_dirs(tmp_path: Path) -> None:
    tool = FileWriteTool(workspace_root=str(tmp_path))
    result = await tool.execute({"path": "a/b/c/deep.txt", "content": "deep"})
    assert result.ok is True
    assert (tmp_path / "a" / "b" / "c" / "deep.txt").read_text(encoding="utf-8") == "deep"


# ─── HashlineEditTool 테스트 ───


@pytest.mark.asyncio
async def test_hashline_edit_single_line_replace(tmp_path: Path) -> None:
    """단일 라인 교체: start_hash == end_hash."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    h_x = generate_line_hash("x = 1")
    result = await tool.execute({
        "path": "code.py",
        "start_hash": h_x,
        "end_hash": h_x,
        "new_content": "x = 42\n",
    })
    assert result.ok is True
    content = test_file.read_text(encoding="utf-8")
    assert "x = 42" in content
    assert "x = 1" not in content
    assert "y = 2" in content


@pytest.mark.asyncio
async def test_hashline_edit_multi_line_replace(tmp_path: Path) -> None:
    """여러 라인 범위 교체."""
    test_file = tmp_path / "code.py"
    test_file.write_text("a = 1\nb = 2\nc = 3\nd = 4\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    h_b = generate_line_hash("b = 2")
    h_c = generate_line_hash("c = 3")
    result = await tool.execute({
        "path": "code.py",
        "start_hash": h_b,
        "end_hash": h_c,
        "new_content": "b = 20\nc = 30\n",
    })
    assert result.ok is True
    content = test_file.read_text(encoding="utf-8")
    assert "b = 20" in content
    assert "c = 30" in content
    assert "b = 2\n" not in content
    assert "a = 1" in content
    assert "d = 4" in content


@pytest.mark.asyncio
async def test_hashline_edit_delete_lines(tmp_path: Path) -> None:
    """라인 삭제: new_content를 빈 문자열로."""
    test_file = tmp_path / "code.py"
    test_file.write_text("keep1\ndelete_me\nkeep2\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    h_del = generate_line_hash("delete_me")
    result = await tool.execute({
        "path": "code.py",
        "start_hash": h_del,
        "end_hash": h_del,
        "new_content": "",
    })
    assert result.ok is True
    content = test_file.read_text(encoding="utf-8")
    assert "delete_me" not in content
    assert "keep1" in content
    assert "keep2" in content


@pytest.mark.asyncio
async def test_hashline_edit_insert_after(tmp_path: Path) -> None:
    """insert_after_hash로 라인 삽입."""
    test_file = tmp_path / "code.py"
    test_file.write_text("line1\nline2\nline3\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    h_line2 = generate_line_hash("line2")
    result = await tool.execute({
        "path": "code.py",
        "insert_after_hash": h_line2,
        "new_content": "inserted_a\ninserted_b\n",
    })
    assert result.ok is True
    content = test_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines[0] == "line1"
    assert lines[1] == "line2"
    assert lines[2] == "inserted_a"
    assert lines[3] == "inserted_b"
    assert lines[4] == "line3"


@pytest.mark.asyncio
async def test_hashline_edit_hash_not_found(tmp_path: Path) -> None:
    """존재하지 않는 해시 → 에러."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    result = await tool.execute({
        "path": "code.py",
        "start_hash": "zz",
        "end_hash": "zz",
        "new_content": "y = 2\n",
    })
    assert result.ok is False
    assert "찾을 수 없어요" in result.error


@pytest.mark.asyncio
async def test_hashline_edit_missing_start_hash(tmp_path: Path) -> None:
    """start_hash 없이 호출 → 에러."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    result = await tool.execute({
        "path": "code.py",
        "new_content": "y = 2\n",
    })
    assert result.ok is False
    assert "start_hash" in result.error


@pytest.mark.asyncio
async def test_hashline_edit_with_lineno_hint(tmp_path: Path) -> None:
    """동일 해시가 여러 줄에 있을 때 lineno 힌트로 모호성 해소."""
    test_file = tmp_path / "code.py"
    # 같은 내용의 라인을 여러 개 만들어서 해시 충돌 유발
    test_file.write_text("pass\nkeep\npass\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    h_pass = generate_line_hash("pass")
    # 3번째 줄(1-indexed)의 pass를 교체하고 싶음
    result = await tool.execute({
        "path": "code.py",
        "start_hash": h_pass,
        "end_hash": h_pass,
        "new_content": "return\n",
        "start_lineno": 3,
        "end_lineno": 3,
    })
    assert result.ok is True
    content = test_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines[0] == "pass"
    assert lines[1] == "keep"
    assert lines[2] == "return"


@pytest.mark.asyncio
async def test_hashline_edit_preview_in_output(tmp_path: Path) -> None:
    """교체 후 미리보기가 output에 포함되는지 확인."""
    test_file = tmp_path / "code.py"
    test_file.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    h_b = generate_line_hash("b = 2")
    result = await tool.execute({
        "path": "code.py",
        "start_hash": h_b,
        "end_hash": h_b,
        "new_content": "b = 99\n",
    })
    assert result.ok is True
    assert "미리보기" in result.output
    h_b_new = generate_line_hash("b = 99")
    assert h_b_new in result.output


# ─── Hashline 유틸리티 테스트 ───


def test_generate_line_hash_strip_insensitive() -> None:
    """공백을 무시하고 같은 해시를 생성하는지 확인."""
    assert generate_line_hash("  x = 1  ") == generate_line_hash("x = 1")
    assert generate_line_hash("\tx = 1") == generate_line_hash("x = 1")


def test_generate_line_hash_different_content() -> None:
    """다른 내용은 다른 해시를 생성해야 함."""
    h1 = generate_line_hash("x = 1")
    h2 = generate_line_hash("x = 2")
    # 2글자 해시라 충돌 가능성은 있지만, 이 특정 경우는 달라야 함
    assert h1 != h2


def test_format_lines_with_hash() -> None:
    """format_lines_with_hash 포맷 검증."""
    result = format_lines_with_hash(["def hello():", "    pass"], start=1)
    assert len(result) == 2
    assert result[0].startswith("1:")
    assert "| def hello():" in result[0]
    assert result[1].startswith("2:")
    assert "|     pass" in result[1]


def test_build_hash_to_lineno_map() -> None:
    """해시→인덱스 매핑 빌드 검증."""
    lines = ["a", "b", "a"]  # 'a'가 두 번
    mapping = build_hash_to_lineno_map(lines)
    h_a = generate_line_hash("a")
    h_b = generate_line_hash("b")
    assert 0 in mapping[h_a]
    assert 2 in mapping[h_a]
    assert mapping[h_b] == [1]


def test_resolve_hash_with_hint() -> None:
    """힌트로 모호한 해시 해소."""
    lines = ["x", "y", "x"]
    mapping = build_hash_to_lineno_map(lines)
    h_x = generate_line_hash("x")
    # 힌트 없으면 첫 번째(0)
    assert resolve_hash_to_index(h_x, mapping) == 0
    # 힌트를 줄 번호 3 근처로 주면 인덱스 2
    assert resolve_hash_to_index(h_x, mapping, hint_lineno=2) == 2


# ─── GlobTool 테스트 ───


@pytest.mark.asyncio
async def test_glob_tool(tmp_path: Path) -> None:
    (tmp_path / "a.py").touch()
    (tmp_path / "b.py").touch()
    (tmp_path / "c.txt").touch()
    tool = GlobTool(workspace_root=str(tmp_path))
    result = await tool.execute({"pattern": "*.py"})
    assert result.ok is True
    assert "a.py" in result.output
    assert "b.py" in result.output
    assert "c.txt" not in result.output


@pytest.mark.asyncio
async def test_glob_tool_no_match(tmp_path: Path) -> None:
    tool = GlobTool(workspace_root=str(tmp_path))
    result = await tool.execute({"pattern": "*.xyz"})
    assert result.ok is True
    assert "일치하는 파일이 없어요" in result.output


# ─── GrepTool 테스트 ───


@pytest.mark.asyncio
async def test_grep_tool(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def hello():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def world():\n    pass\n", encoding="utf-8")
    tool = GrepTool(workspace_root=str(tmp_path))
    result = await tool.execute({"pattern": "def hello"})
    assert result.ok is True
    assert "a.py" in result.output
    assert "b.py" not in result.output


@pytest.mark.asyncio
async def test_grep_tool_with_include(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("target\n", encoding="utf-8")
    (tmp_path / "a.txt").write_text("target\n", encoding="utf-8")
    tool = GrepTool(workspace_root=str(tmp_path))
    result = await tool.execute({"pattern": "target", "include": "*.py"})
    assert result.ok is True
    assert "a.py" in result.output
    assert "a.txt" not in result.output


@pytest.mark.asyncio
async def test_grep_tool_invalid_regex(tmp_path: Path) -> None:
    tool = GrepTool(workspace_root=str(tmp_path))
    result = await tool.execute({"pattern": "[invalid"})
    assert result.ok is False
    assert "정규식" in result.error


# ─── WebFetchTool 테스트 ───


@pytest.mark.asyncio
async def test_web_fetch_tool_invalid_url() -> None:
    tool = WebFetchTool()
    result = await tool.execute({"url": "not-a-url"})
    assert result.ok is False
    assert "http" in result.error


@pytest.mark.asyncio
async def test_web_fetch_tool_missing_url() -> None:
    tool = WebFetchTool()
    result = await tool.execute({})
    assert result.ok is False


# ─── file_read → hashline_edit 강제 순서 테스트 ───


@pytest.mark.asyncio
async def test_hashline_edit_blocked_without_file_read(tmp_path: Path) -> None:
    """file_read 없이 hashline_edit 호출 시 거부돼야 해요."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\n", encoding="utf-8")
    registry = ToolRegistry()
    edit_tool = HashlineEditTool(workspace_root=str(tmp_path), registry=registry)
    registry.register(edit_tool)

    h_x = generate_line_hash("x = 1")
    result = await edit_tool.execute({
        "path": "code.py",
        "start_hash": h_x,
        "end_hash": h_x,
        "new_content": "x = 99\n",
    })
    assert result.ok is False
    assert "file_read" in result.error


@pytest.mark.asyncio
async def test_hashline_edit_allowed_after_file_read(tmp_path: Path) -> None:
    """file_read 후 hashline_edit이 허용돼야 해요."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\n", encoding="utf-8")
    registry = ToolRegistry()
    read_tool = FileReadTool(workspace_root=str(tmp_path), registry=registry)
    edit_tool = HashlineEditTool(workspace_root=str(tmp_path), registry=registry)
    registry.register(read_tool)
    registry.register(edit_tool)

    # file_read 먼저
    read_result = await read_tool.execute({"path": "code.py"})
    assert read_result.ok is True

    h_x = generate_line_hash("x = 1")
    result = await edit_tool.execute({
        "path": "code.py",
        "start_hash": h_x,
        "end_hash": h_x,
        "new_content": "x = 99\n",
    })
    assert result.ok is True
    assert "x = 99" in test_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_hashline_edit_blocked_after_external_modification(tmp_path: Path) -> None:
    """file_read 후 외부에서 파일이 변경되면 다시 read 요구해야 해요."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\n", encoding="utf-8")
    registry = ToolRegistry()
    read_tool = FileReadTool(workspace_root=str(tmp_path), registry=registry)
    edit_tool = HashlineEditTool(workspace_root=str(tmp_path), registry=registry)
    registry.register(read_tool)
    registry.register(edit_tool)

    # file_read 먼저
    await read_tool.execute({"path": "code.py"})

    # 외부에서 파일 변경 (mtime을 미래로 강제)
    await asyncio.sleep(0.01)
    test_file.write_text("x = 2\n", encoding="utf-8")

    h_x = generate_line_hash("x = 2")
    result = await edit_tool.execute({
        "path": "code.py",
        "start_hash": h_x,
        "end_hash": h_x,
        "new_content": "x = 99\n",
    })
    assert result.ok is False
    assert "변경됐어요" in result.error
    assert "file_read" in result.error


@pytest.mark.asyncio
async def test_hashline_edit_allowed_after_re_read(tmp_path: Path) -> None:
    """외부 변경 후 file_read를 다시 하면 편집이 허용돼야 해요."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\n", encoding="utf-8")
    registry = ToolRegistry()
    read_tool = FileReadTool(workspace_root=str(tmp_path), registry=registry)
    edit_tool = HashlineEditTool(workspace_root=str(tmp_path), registry=registry)
    registry.register(read_tool)
    registry.register(edit_tool)

    # 최초 read
    await read_tool.execute({"path": "code.py"})

    # 외부 변경
    await asyncio.sleep(0.01)
    test_file.write_text("x = 2\n", encoding="utf-8")

    # 다시 read
    await read_tool.execute({"path": "code.py"})

    h_x = generate_line_hash("x = 2")
    result = await edit_tool.execute({
        "path": "code.py",
        "start_hash": h_x,
        "end_hash": h_x,
        "new_content": "x = 99\n",
    })
    assert result.ok is True


@pytest.mark.asyncio
async def test_hashline_edit_no_registry_bypasses_check(tmp_path: Path) -> None:
    """registry=None으로 생성한 도구는 read 이력 검사를 건너뛰어요."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\n", encoding="utf-8")
    # registry 없이 단독 생성 (테스트 편의용)
    tool = HashlineEditTool(workspace_root=str(tmp_path))
    h_x = generate_line_hash("x = 1")
    result = await tool.execute({
        "path": "code.py",
        "start_hash": h_x,
        "end_hash": h_x,
        "new_content": "x = 0\n",
    })
    assert result.ok is True
