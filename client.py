"""MiniMax-M3 API 客户端（OpenAI 兼容协议）。"""
from __future__ import annotations

import os
from typing import Iterable

from openai import OpenAI


class MiniMaxClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "MINIMAX_BASE_URL", "https://api.minimax.chat/v1"
        )
        self.model = model or os.environ.get(
            "MINIMAX_MODEL", "minimax-portal/MiniMax-M3"
        )
        if not self.api_key:
            raise RuntimeError(
                "未设置 MINIMAX_API_KEY，请先 export 或写入 .env"
            )
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: Iterable[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """非流式对话，返回完整回复文本。"""
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def stream_chat(
        self,
        messages: Iterable[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        """流式对话，逐块 yield 文本。"""
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta