import json
from types import SimpleNamespace
from typing import cast

from langchain.agents.middleware import ModelRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.project_context_middleware import ProjectContextMiddleware
from deerflow.projects.brief import format_project_brief


def _write_project(tmp_path, project_id: str, thread_ids: list[str], sentence: str):
    material_id = "a1b2c3d4e5f6"
    directory = tmp_path / "projects" / project_id / "materials"
    directory.mkdir(parents=True)
    (directory / f"{material_id}.excerpt.txt").write_text(sentence, encoding="utf-8")
    (tmp_path / "projects.json").write_text(
        json.dumps(
            [
                {
                    "id": project_id,
                    "name": "组织诊断",
                    "summary": "第一阶段",
                    "thread_ids": thread_ids,
                    "outputs": [{"title": "阶段记录", "note": "自己填写"}],
                    "materials": [{"id": material_id, "filename": "口径说明.txt"}],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_brief_includes_material_for_attached_thread(tmp_path):
    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")
    brief = format_project_brief(tmp_path, thread_id="thread-1", project_id="other0000000")
    assert "月薪按十三个月计算" in brief
    assert "组织诊断" in brief
    assert "阶段记录" in brief
    assert "<project_context>" in brief


def test_brief_uses_project_id_before_thread_is_attached(tmp_path):
    _write_project(tmp_path, "abc123abc123", [], "月薪按十三个月计算")
    brief = format_project_brief(tmp_path, thread_id="brand-new", project_id="abc123abc123")
    assert "月薪按十三个月计算" in brief


def test_brief_ignores_unrelated_project(tmp_path):
    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")
    other = {
        "id": "def456def456",
        "name": "另一个项目",
        "thread_ids": [],
        "materials": [],
    }
    raw = json.loads((tmp_path / "projects.json").read_text(encoding="utf-8"))
    raw.append(other)
    (tmp_path / "projects.json").write_text(json.dumps(raw), encoding="utf-8")
    brief = format_project_brief(tmp_path, thread_id="thread-1", project_id="def456def456")
    assert "月薪按十三个月计算" in brief
    assert "另一个项目" not in brief


def _request(messages, thread_id: str | None = "thread-1", project_id: str | None = None):
    return ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=messages,
        runtime=cast(Runtime, SimpleNamespace(context={"thread_id": thread_id, "project_id": project_id})),
    )


def _capture(middleware, request):
    """Run wrap_model_call and return the request the handler actually received."""
    seen = {}

    def handler(req):
        seen["request"] = req
        return "ok"

    middleware.wrap_model_call(request, handler)
    return seen["request"]


def test_middleware_prepends_brief_to_request(tmp_path):
    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")
    middleware = ProjectContextMiddleware(base_dir=str(tmp_path))
    request = _request([HumanMessage(content=[{"type": "text", "text": "材料里怎么算月薪？"}])])

    sent = _capture(middleware, request)
    content = sent.messages[-1].content
    assert content[0]["text"].count("<project_context>") == 1
    assert "月薪按十三个月计算" in content[0]["text"]
    assert content[1]["text"] == "材料里怎么算月薪？"


def test_middleware_does_not_mutate_conversation_state(tmp_path):
    """The brief must never reach the checkpoint, so it cannot accumulate."""
    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")
    middleware = ProjectContextMiddleware(base_dir=str(tmp_path))

    first = HumanMessage(content="第一轮提问")
    state = [first]
    for _ in range(3):
        sent = _capture(middleware, _request(state))
        assert "<project_context>" in str(sent.messages[-1].content)
        # wrap_model_call does not write back to the conversation state.
        state = list(state)
        state.append(HumanMessage(content="下一轮提问"))

    assert all("<project_context>" not in str(message.content) for message in state)
    assert "<project_context>" not in str(first.content)


def test_middleware_keeps_brief_across_tool_calls_in_one_turn(tmp_path):
    """After a tool call the last message is a ToolMessage; the brief must stay."""
    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")
    middleware = ProjectContextMiddleware(base_dir=str(tmp_path))

    messages = [
        HumanMessage(content="材料里怎么算月薪？"),
        AIMessage(content="", tool_calls=[{"name": "bash", "args": {}, "id": "call-1"}]),
        ToolMessage(content="done", tool_call_id="call-1"),
    ]
    sent = _capture(middleware, _request(messages))
    joined = " ".join(str(message.content) for message in sent.messages)
    assert joined.count("<project_context>") == 1
    assert "月薪按十三个月计算" in joined


def test_middleware_keeps_single_brief_copy_across_turns(tmp_path):
    """Older turns stay clean, so the request carries exactly one brief."""
    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")
    middleware = ProjectContextMiddleware(base_dir=str(tmp_path))

    history = [
        HumanMessage(content="第一轮"),
        AIMessage(content="回答一"),
        HumanMessage(content="第二轮"),
        AIMessage(content="回答二"),
    ]
    sent = _capture(middleware, _request(history))
    joined = " ".join(str(message.content) for message in sent.messages)
    assert joined.count("<project_context>") == 1
    assert "第一轮" in sent.messages[0].content
    assert "<project_context>" not in str(sent.messages[0].content)


def test_middleware_skips_when_no_user_message(tmp_path):
    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")
    middleware = ProjectContextMiddleware(base_dir=str(tmp_path))
    request = _request([AIMessage(content="只有 AI 消息")])

    sent = _capture(middleware, request)
    assert sent.messages[0].content == "只有 AI 消息"


def test_agent_sees_brief_but_state_stays_clean(tmp_path):
    """End-to-end: the model receives the brief, the checkpoint does not."""
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    _write_project(tmp_path, "abc123abc123", ["thread-1"], "月薪按十三个月计算")

    seen: list[list] = []

    class SpyModel(GenericFakeChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            seen.append(messages)
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    model = SpyModel(messages=iter([AIMessage(content="好的")]))
    agent = create_agent(model=model, tools=[], middleware=[ProjectContextMiddleware(base_dir=str(tmp_path))])

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "材料里怎么算月薪？"}]},
        {"configurable": {"thread_id": "thread-1"}},
    )

    model_input = " ".join(str(message.content) for message in seen[0])
    assert "<project_context>" in model_input
    assert "月薪按十三个月计算" in model_input

    state_text = " ".join(str(message.content) for message in result["messages"])
    assert "<project_context>" not in state_text
    assert "材料里怎么算月薪？" in state_text
