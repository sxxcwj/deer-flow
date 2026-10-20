from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from deerflow.tools.builtins.setup_agent_tool import setup_agent


class _DummyRuntime(SimpleNamespace):
    context: dict
    tool_call_id: str


def test_setup_agent_rejects_invalid_agent_name_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    outside_dir = tmp_path.parent / "outside-target"
    traversal_agent = f"../../../{outside_dir.name}/evil"
    runtime = _DummyRuntime(context={"agent_name": traversal_agent}, tool_call_id="tool-1")

    result = setup_agent.func(soul="test soul", description="desc", runtime=runtime)

    messages = result.update["messages"]
    assert len(messages) == 1
    assert "Invalid agent name" in messages[0].content
    assert not (tmp_path / "agents").exists()
    assert not (outside_dir / "evil" / "SOUL.md").exists()


def test_setup_agent_keeps_existing_avatar(tmp_path, monkeypatch):
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    agent_dir = tmp_path / "agents" / "guide"
    agent_dir.mkdir(parents=True)
    (agent_dir / "config.yaml").write_text("name: guide\navatar: 🦌\n", encoding="utf-8")
    runtime = _DummyRuntime(context={"agent_name": "guide"}, tool_call_id="tool-avatar")

    result = setup_agent.func(soul="new soul", description="a guide", runtime=runtime)

    assert "created successfully" in result.update["messages"][0].content
    saved = yaml.safe_load((agent_dir / "config.yaml").read_text(encoding="utf-8"))
    assert saved["avatar"] == "🦌"


def test_setup_agent_rejects_absolute_agent_name_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    absolute_agent = str(tmp_path / "outside-agent")
    runtime = _DummyRuntime(context={"agent_name": absolute_agent}, tool_call_id="tool-2")

    result = setup_agent.func(soul="test soul", description="desc", runtime=runtime)

    messages = result.update["messages"]
    assert len(messages) == 1
    assert "Invalid agent name" in messages[0].content
    assert not (tmp_path / "agents").exists()
    assert not (Path(absolute_agent) / "SOUL.md").exists()
