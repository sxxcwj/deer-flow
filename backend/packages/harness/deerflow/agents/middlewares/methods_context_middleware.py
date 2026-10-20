"""Inject a bounded brief of the firm's own methods into the model request.

The brief is attached to the outgoing model request only. It is never written
back into the conversation state, so a long-running thread does not accumulate
one copy of the brief per turn.

Project context is *not* handled here: upstream renders the pinned project
snapshot (name, instructions, document shelf) through
``DynamicContextMiddleware.wrap_model_call``, which is request-only as well.
This middleware only covers firm-wide methods, which upstream does not model.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage

from deerflow.config.paths import Paths, get_paths
from deerflow.methods.brief import format_methods_brief

logger = logging.getLogger(__name__)

_METHODS_TAG = "<method_context>"


class MethodsContextMiddleware(AgentMiddleware):
    """Attach the firm's methodology brief to the latest user message."""

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
        brief = format_methods_brief(self._paths.base_dir)
        if not brief:
            return request

        messages = list(request.messages)
        index = _last_human_index(messages)
        if index is None:
            return request

        current = messages[index]
        if _has_tag(current.content, _METHODS_TAG):
            return request

        messages[index] = _prepend(current, brief)
        logger.debug("Injected methods brief into the model request")
        return request.override(messages=messages)


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
