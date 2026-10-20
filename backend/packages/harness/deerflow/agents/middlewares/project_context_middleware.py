"""Inject a bounded project brief into the model request.

The brief is attached to the outgoing model request only. It is never written
back into the conversation state, so a long-running thread does not accumulate
one copy of the brief per turn.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage

from deerflow.config.paths import Paths, get_paths
from deerflow.methods.brief import format_methods_brief
from deerflow.projects.brief import format_project_brief

logger = logging.getLogger(__name__)


class ProjectContextMiddleware(AgentMiddleware):
    """Prepend project notes and material excerpts for the active conversation."""

    def __init__(self, base_dir: str | None = None):
        super().__init__()
        self._paths = Paths(base_dir) if base_dir else get_paths()

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return handler(self._with_brief(request))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(self._with_brief(request))

    def _with_brief(self, request: ModelRequest) -> ModelRequest:
        """Return a request whose latest user message carries the brief.

        The returned request is a copy: the conversation state keeps the
        original message, so nothing is checkpointed and nothing accumulates
        across turns.
        """
        brief = self._build_brief(request)
        if not brief:
            return request

        messages = list(request.messages)
        index = _last_human_index(messages)
        if index is None:
            return request

        current = messages[index]
        if _has_tag(current.content, "<method_context>") or _has_tag(current.content, "<project_context>"):
            return request

        messages[index] = _prepend(current, brief)
        logger.debug("Injected project brief for thread %s", _thread_id(request))
        return request.override(messages=messages)

    def _build_brief(self, request: ModelRequest) -> str:
        context = _runtime_context(request)
        thread_id = context.get("thread_id")
        project_id = context.get("project_id")
        if thread_id is None or project_id is None:
            try:
                from langgraph.config import get_config

                configurable = get_config().get("configurable", {})
                thread_id = thread_id or configurable.get("thread_id")
                project_id = project_id or configurable.get("project_id")
            except RuntimeError:
                pass
        if not isinstance(thread_id, str):
            thread_id = None
        if not isinstance(project_id, str):
            project_id = None

        chunks: list[str] = []
        methods = format_methods_brief(self._paths.base_dir)
        if methods:
            chunks.append(methods)
        if thread_id or project_id:
            project = format_project_brief(
                self._paths.base_dir,
                thread_id=thread_id,
                project_id=project_id,
            )
            if project:
                chunks.append(project)
        return "\n\n".join(chunks)


def _runtime_context(request: ModelRequest) -> dict:
    runtime = getattr(request, "runtime", None)
    context = getattr(runtime, "context", None)
    return context if isinstance(context, dict) else {}


def _thread_id(request: ModelRequest) -> str | None:
    thread_id = _runtime_context(request).get("thread_id")
    return thread_id if isinstance(thread_id, str) else None


def _last_human_index(messages: list) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return index
    return None


def _has_tag(content, tag: str) -> bool:
    if isinstance(content, str):
        return tag in content
    if isinstance(content, list):
        return any(tag in _block_text(block) for block in content)
    return False


def _block_text(block) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        text = block.get("text")
        return text if isinstance(text, str) else ""
    return ""


def _prepend(message: HumanMessage, brief: str) -> HumanMessage:
    content = message.content
    if isinstance(content, str):
        new_content: object = f"{brief}\n\n{content}"
    elif isinstance(content, list):
        new_content = [{"type": "text", "text": f"{brief}\n\n"}, *content]
    else:
        return message
    return HumanMessage(
        content=new_content,
        id=message.id,
        additional_kwargs=message.additional_kwargs,
    )
