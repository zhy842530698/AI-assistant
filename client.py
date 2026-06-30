"""MiniMax-M3 API 客户端(Anthropic 兼容协议)。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import anthropic
from dotenv import load_dotenv

# 让 client.py 即便被直接 import 也能读到 .env
_ENV_PATH = Path(__file__).resolve().parent / ".env"
print(f"[client.py] .env 路径: {_ENV_PATH} 存在={_ENV_PATH.exists()}")
_loaded = load_dotenv(_ENV_PATH)
print(f"[client.py] load_dotenv 返回: {_loaded} (True 表示从文件读到东西)")
print(f"[client.py] load_dotenv 后 os.environ['ANTHROPIC_API_KEY']: "
      f"{os.environ.get('ANTHROPIC_API_KEY')!r}")


class MiniMaxClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        print(f"[MiniMaxClient.__init__] 传入 api_key 参数: {api_key!r}")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        masked = (self.api_key[:4] + "***" + self.api_key[-2:]) if self.api_key else "<空>"
        print(f"[MiniMaxClient.__init__] 最终 self.api_key: {masked} "
              f"(长度={len(self.api_key)}, 是否为空={not self.api_key})")
        self.base_url = base_url or os.environ.get(
            "ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"
        )
        self.model = model or os.environ.get(
            "ANTHROPIC_MODEL", "MiniMax-M3"
        )
        if not self.api_key:
            raise RuntimeError(
                "未设置 ANTHROPIC_API_KEY,请先 export 或写入 .env"
            )
        self._client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def _split_system(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Anthropic 协议要求 system 单独传,所以从 messages 里抽出来。"""
        system_parts: list[str] = []
        rest: list[dict] = []
        for m in messages:
            if m.get("role") == "system":
                system_parts.append(m["content"])
            else:
                rest.append(m)
        system = "\n\n".join(system_parts) if system_parts else None
        return system, rest

    def chat(
        self,
        messages: Iterable[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """非流式对话,返回完整回复文本。"""
        msgs = list(messages)
        system, msgs = self._split_system(msgs)
        kwargs = dict(
            model=self.model,
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        return self._extract_text(resp)

    def stream_chat(
        self,
        messages: Iterable[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterable[str]:
        """流式对话，逐块 yield 文本。"""
        msgs = list(messages)
        system, msgs = self._split_system(msgs)
        kwargs = dict(
            model=self.model,
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if system:
            kwargs["system"] = system
        # Anthropic SDK: messages.stream() 本身就是流式入口，
        # 不接受 stream=True 参数（传了会报 unexpected keyword argument）
        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                if text:
                    yield text

    @staticmethod
    def _extract_text(resp) -> str:
        """从 Anthropic Message 响应里拼出文本。"""
        parts: list[str] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts)
