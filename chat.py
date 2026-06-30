"""终端 REPL：和 MiniMax-M3 多轮对话。"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from client import MiniMaxClient


SYSTEM_PROMPT = "你是用户的个人 AI 助手 MiniMax-M3，回答简洁、友好、可执行。"

console = Console()


def main() -> int:
    load_dotenv()
    try:
        client = MiniMaxClient()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    console.print(
        Panel.fit(
            f"[bold]AI-assistant[/bold] · 模型 {client.model}\n"
            "输入内容直接回车发送 · /clear 清空 · /quit 退出",
            border_style="cyan",
        )
    )

    while True:
        try:
            user_input = console.input("[bold green]你[/bold green] › ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见。[/dim]")
            return 0

        if not user_input:
            continue
        if user_input == "/quit":
            console.print("[dim]再见。[/dim]")
            return 0
        if user_input == "/clear":
            messages = [messages[0]]
            console.print("[dim]上下文已清空。[/dim]")
            continue

        messages.append({"role": "user", "content": user_input})

        console.print(f"[bold cyan]{client.model}[/bold cyan] › ", end="")
        try:
            parts: list[str] = []
            for chunk in client.stream_chat(messages):
                console.print(chunk, end="", soft_wrap=True)
                parts.append(chunk)
            console.print()
        except Exception as e:
            console.print(f"\n[red]调用失败: {e}[/red]")
            # 回滚刚加入的 user，避免脏上下文
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": "".join(parts)})


if __name__ == "__main__":
    sys.exit(main())