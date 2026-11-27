"""Chat model adapter. Mock replies are deterministic so tests and evals are stable."""

import hashlib
from collections.abc import Iterator
from typing import Any, Literal

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.config import Settings

CANNED_REPLIES = (
    "Thank you for sharing that. What feels most present for you right now?",
    "That sounds like a lot to carry. Would a few quiet minutes help?",
    "I'm here. Take your time.",
)


class MockChatModel(BaseChatModel):
    """Picks a canned reply by hashing the last message. No network, no keys."""

    model_name: str = "mock"

    @property
    def _llm_type(self) -> str:
        return "grove-mock"

    def _reply(self, messages: list[BaseMessage]) -> str:
        last = str(messages[-1].content) if messages else ""
        idx = int(hashlib.sha256(last.encode()).hexdigest(), 16) % len(CANNED_REPLIES)
        return CANNED_REPLIES[idx]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        msg = AIMessage(content=self._reply(messages))
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        words = self._reply(messages).split(" ")
        for i, word in enumerate(words):
            token = word if i == 0 else " " + word
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=token))
            if run_manager:
                run_manager.on_llm_new_token(token, chunk=chunk)
            yield chunk


def get_chat_model(settings: Settings, tier: Literal["main", "fast"]) -> BaseChatModel:
    provider = settings.llm_provider_main if tier == "main" else settings.llm_provider_fast
    model = settings.llm_model_main if tier == "main" else settings.llm_model_fast
    if provider == "mock":
        return MockChatModel(model_name=f"mock:{model}")
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        from pydantic import SecretStr

        return ChatAnthropic(
            model=model,
            api_key=SecretStr(settings.anthropic_api_key),
            max_tokens=1024 if tier == "main" else 256,
            timeout=60,
        )
    raise NotImplementedError(f"LLM provider '{provider}' is not wired up yet")
