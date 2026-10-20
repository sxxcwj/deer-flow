import json
from types import SimpleNamespace
from typing import cast

from langchain.agents.middleware import ModelRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.methods_context_middleware import MethodsContextMiddleware
from deerflow.methods.brief import format_methods_brief


def _write_method(tmp_path, title: str, body: str):
    method_id = "a1b2c3d4e5f6"
    directory = tmp_path / "methods"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{method_id}.excerpt.txt").write_text(body, encoding="utf-8")
    (tmp_path / "methods.json").write_text(
        json.dumps(
            [
                {
                    "id": method_id,
                    "title": title,
                    "body": body,
                    "filename": f"{method_id}.txt",
                }
            ]
        ),
        encoding="utf-8",
    )


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


def test_methods_brief_contains_body(tmp_path):
    _write_method(tmp_path, "月薪口径", "月薪按十三个月计算")
    brief = format_methods_brief(tmp_path)
    assert "月薪按十三个月计算" in brief
    assert "<method_context>" in brief


def test_middleware_prepends_brief_to_request(tmp_path):
    _write_method(tmp_path, "月薪口径", "月薪按十三个月计算")
    middleware = MethodsContextMiddleware(base_dir=str(tmp_path))
    request = _request([HumanMessage(content=[{"type": "text", "text": "材料里怎么算月薪？"}])])

    sent = _capture(middleware, request)
    content = sent.messages[-1].content
    assert content[0]["text"].count("<method_context>") == 1
    assert "月薪按十三个月计算" in content[0]["text"]
    assert content[1]["text"] == "材料里怎么算月薪？"


def test_middleware_does_not_mutate_conversation_state(tmp_path):
    """The brief must never reach the checkpoint, so it cannot accumulate."""
    _write_method(tmp_path, "月薪口径", "月薪按十三个月计算")
    middleware = MethodsContextMiddleware(base_dir=str(tmp_path))

    first = HumanMessage(content="第一轮提问")
    state = [first]
    for _ in range(3):
        sent = _capture(middleware, _request(state))
        assert "<method_context>" in str(sent.messages[-1].content)
        # wrap_model_call does not write back to the conversation state.
        state = list(state)
        state.append(HumanMessage(content="下一轮提问"))

    assert all("<method_context>" not in str(message.content) for message in state)
    assert "<method_context>" not in str(first.content)


def test_middleware_keeps_brief_across_tool_calls_in_one_turn(tmp_path):
    """After a tool call the last message is a ToolMessage; the brief must stay."""
    _write_method(tmp_path, "月薪口径", "月薪按十三个月计算")
    middleware = MethodsContextMiddleware(base_dir=str(tmp_path))

    messages = [
        HumanMessage(content="材料里怎么算月薪？"),
        AIMessage(content="", tool_calls=[{"name": "bash", "args": {}, "id": "call-1"}]),
        ToolMessage(content="done", tool_call_id="call-1"),
    ]
    sent = _capture(middleware, _request(messages))
    joined = " ".join(str(message.content) for message in sent.messages)
    assert joined.count("<method_context>") == 1
    assert "月薪按十三个月计算" in joined


def test_middleware_keeps_single_brief_copy_across_turns(tmp_path):
    """Older turns stay clean, so the request carries exactly one brief."""
    _write_method(tmp_path, "月薪口径", "月薪按十三个月计算")
    middleware = MethodsContextMiddleware(base_dir=str(tmp_path))

    history = [
        HumanMessage(content="第一轮"),
        AIMessage(content="回答一"),
        HumanMessage(content="第二轮"),
        AIMessage(content="回答二"),
    ]
    sent = _capture(middleware, _request(history))
    joined = " ".join(str(message.content) for message in sent.messages)
    assert joined.count("<method_context>") == 1
    assert "<method_context>" not in str(sent.messages[0].content)


def test_middleware_skips_when_no_user_message(tmp_path):
    _write_method(tmp_path, "月薪口径", "月薪按十三个月计算")
    middleware = MethodsContextMiddleware(base_dir=str(tmp_path))
    request = _request([AIMessage(content="只有 AI 消息")])

    sent = _capture(middleware, request)
    assert sent.messages[0].content == "只有 AI 消息"


def test_middleware_skips_when_no_methods_configured(tmp_path):
    middleware = MethodsContextMiddleware(base_dir=str(tmp_path))
    request = _request([HumanMessage(content="没有任何方法论")])

    sent = _capture(middleware, request)
    assert sent.messages[0].content == "没有任何方法论"


def test_agent_sees_brief_but_state_stays_clean(tmp_path):
    """End-to-end: the model receives the brief, the checkpoint does not."""
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    _write_method(tmp_path, "月薪口径", "月薪按十三个月计算")

    seen: list[list] = []

    class SpyModel(GenericFakeChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            seen.append(messages)
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    model = SpyModel(messages=iter([AIMessage(content="好的")]))
    agent = create_agent(model=model, tools=[], middleware=[MethodsContextMiddleware(base_dir=str(tmp_path))])

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "材料里怎么算月薪？"}]},
        {"configurable": {"thread_id": "thread-1"}},
    )

    model_input = " ".join(str(message.content) for message in seen[0])
    assert "<method_context>" in model_input
    assert "月薪按十三个月计算" in model_input

    state_text = " ".join(str(message.content) for message in result["messages"])
    assert "<method_context>" not in state_text
    assert "材料里怎么算月薪？" in state_text
