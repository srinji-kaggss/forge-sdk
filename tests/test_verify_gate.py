"""Regression tests for issue #20 — SUCCESS must be gated on an actual
build/test run of the files written, not asserted on unverified output.

Run with: pytest tests/test_verify_gate.py -v
"""

from __future__ import annotations

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.models.types import ModelResponse
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.verifiers import VerificationStatus

CARGO_TOML = """\
[package]
name = "verifygate"
version = "0.1.0"
edition = "2021"
"""

GOOD_MAIN_RS = """\
fn main() {
    println!("ok");
}
"""

# Mirrors issue #20's actual repro: .clone() on a type that doesn't derive
# Clone -- a real, not invented, compile-blocker.
BROKEN_MAIN_RS = """\
struct NotCloneable {
    value: i32,
}

fn main() {
    let a = NotCloneable { value: 1 };
    let b = a.clone();
    println!("{}", b.value);
}
"""


def _agent() -> ReactAgent:
    return ReactAgent(model=object(), tools=object())


def test_detect_verify_command_for_cargo_project(tmp_path):
    (tmp_path / "Cargo.toml").write_text(CARGO_TOML)
    agent = _agent()
    assert agent._detect_verify_command(str(tmp_path), ["src/main.rs"]) == "cargo build --quiet"


def test_detect_verify_command_for_python_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    agent = _agent()
    cmd = agent._detect_verify_command(str(tmp_path), ["mod.py"])
    assert cmd is not None
    assert "py_compile" in cmd
    assert "mod.py" in cmd


def test_detect_verify_command_returns_none_when_no_project_markers(tmp_path):
    agent = _agent()
    assert agent._detect_verify_command(str(tmp_path), ["notes.md"]) is None


def test_detect_verify_command_skips_cargo_build_when_no_rust_file_edited(tmp_path):
    """Live bug: a pure doc-review task (write only docs/review.md) in a
    Cargo repo triggered `cargo build --quiet` on the whole crate anyway,
    failing on a pre-existing, task-unrelated dependency-fetch error and
    reporting the task FAILED even though the review doc was written fine.
    The Python branch below already scopes to edited .py files; the Rust
    branch didn't have the equivalent check.
    """
    (tmp_path / "Cargo.toml").write_text(CARGO_TOML)
    agent = _agent()
    assert agent._detect_verify_command(str(tmp_path), ["docs/review.md"]) is None


async def test_run_verify_command_passes_on_valid_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text(CARGO_TOML)
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.rs").write_text(GOOD_MAIN_RS)

    agent = _agent()
    evidence = await agent._run_verify_command("cargo build --quiet", str(tmp_path))
    assert evidence.status == VerificationStatus.PASSED


async def test_run_verify_command_fails_on_the_exact_issue_20_repro(tmp_path):
    """The real bug: forge wrote a .rs file with a .clone() on a
    non-Clone type and reported Status: SUCCESS in 3 steps with no build
    step. Prove cargo build actually catches it now.
    """
    (tmp_path / "Cargo.toml").write_text(CARGO_TOML)
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.rs").write_text(BROKEN_MAIN_RS)

    agent = _agent()
    evidence = await agent._run_verify_command("cargo build --quiet", str(tmp_path))
    assert evidence.status == VerificationStatus.FAILED
    assert "clone" in evidence.message.lower() or "error" in evidence.message.lower()


class _FakeModel:
    """Scripted model: write a broken Rust file, then call finish."""

    name = "fake"
    provider = "fake"
    context_window = 100_000
    max_output = 4096
    supports_reasoning = False

    def __init__(self, written_file: str, content: str):
        self._written_file = written_file
        self._content = content
        self._step = 0

    def complete(self, messages, *, temperature=0.0, max_tokens=None, stop=None, tools=None):
        self._step += 1
        if self._step == 1:
            action_input = {"path": self._written_file, "content": self._content}
            body = {
                "thought": "writing the file",
                "action": "write_file",
                "action_input": action_input,
            }
        else:
            body = {
                "thought": "done",
                "action": "finish",
                "action_input": {"output": "Status: SUCCESS — wrote the file."},
            }
        import json

        return ModelResponse(content=json.dumps(body))


def _write_file_registry() -> ToolRegistry:
    from forge_sdk.tools.filesystem import FILE_TOOLS

    reg = ToolRegistry()
    for tool in FILE_TOOLS:
        reg.register(tool)
    return reg


async def test_arun_flips_success_false_when_build_gate_fails(tmp_path):
    """End-to-end repro of issue #20: a 2-step agent loop (write_file then
    finish) against a real Cargo project, writing the exact broken file from
    the issue. Before this fix, the loop had no build step at all and
    reported SUCCESS unconditionally; now it must report success=False with
    the build failure attached as evidence.
    """
    (tmp_path / "Cargo.toml").write_text(CARGO_TOML)
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.rs").write_text(GOOD_MAIN_RS)  # starts valid; agent "edits" it below

    model = _FakeModel("src/main.rs", BROKEN_MAIN_RS)
    agent = ReactAgent(model=model, tools=_write_file_registry())
    context = AgentContext(task="add a clone() call to main.rs", cwd=str(tmp_path), max_steps=5)

    result = await agent.arun(context)

    assert result.success is False
    assert (src / "main.rs").read_text() == BROKEN_MAIN_RS  # the write did happen


async def test_arun_reports_success_when_build_gate_passes(tmp_path):
    (tmp_path / "Cargo.toml").write_text(CARGO_TOML)
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.rs").write_text("fn main() {}\n")

    model = _FakeModel("src/main.rs", GOOD_MAIN_RS)
    agent = ReactAgent(model=model, tools=_write_file_registry())
    context = AgentContext(task="update the greeting in main.rs", cwd=str(tmp_path), max_steps=5)

    result = await agent.arun(context)

    assert result.success is True
