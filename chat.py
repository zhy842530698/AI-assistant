"""终端 REPL：和 MiniMax-M3 多轮对话（金融分析师角色）。"""
from __future__ import annotations

import datetime as _dt
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from client import MiniMaxClient


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    today = _dt.date.today().strftime("%Y-%m-%d")
    return (
        "你是一名资深金融市场分析师，拥有强大的信息收集、分析与解决问题能力。\n"
        "职责：基于用户提供的工具与公开信息，汇总财务/市场数据，回答用户关于个股、"
        "行业与宏观的问题；对编程任务，只使用你被授权的工具，不要臆造数据或接口。\n"
        "风格：结论先行、要点分明、给出可执行的判断与依据，必要时附上风险提示。\n"
        "完成任务后，在回复末尾单独一行输出 TERMINATE。\n\n"
        f"当前日期：{today}。当用户问题中出现 \"今天\" / \"今日\" 等相对时间时，"
        "以此日期为准。"
    )


USER_PROMPT_TEMPLATE = """\
Instruction: You are an experienced stock market analyst. \
Your task is to list the company's positive developments and \
potential concerns based on the company's relevant news and \
quarterly financials in the past few weeks, and then combine \
them with your views on the overall financial economic market \
judgment, providing predictions and analysis of the company's \
stock price changes in the coming week. Your answer format \
should be as follows:
[Positive development]:
1. ...
[Potential concerns]:
1. ...
[Forecast and Analysis]:
...
Information:
a. Company Introduction #公司简介
b. Stock Price Changes #股票的变动价格
c. Recent News Information #近期的新闻
d. Recent Basic Financials # 基本财务信息

Instruction: Based on all the information before {data_latest_date}, \
let's first analyze the positive developments and potential concerns \
for {company}. Come up with 2-4 most important factors respectively \
and keep them concise. Then make your prediction of the {company} \
price movement for next week ({begin_forecaster_date} to \
{end_forecaster_date}). Provide a summary analysis to support your prediction."""


def _next_week_range(today: _dt.date) -> tuple[_dt.date, _dt.date]:
    """返回下周一 ~ 下周日。"""
    days_to_monday = (7 - today.weekday()) % 7 or 7
    start = today + _dt.timedelta(days=days_to_monday)
    end = start + _dt.timedelta(days=6)
    return start, end


def _render_user_template(company: str = "AAPL") -> str:
    today = _dt.date.today()
    start, end = _next_week_range(today)
    return USER_PROMPT_TEMPLATE.format(
        company=company.upper(),
        data_latest_date=today.strftime("%Y-%m-%d"),
        begin_forecaster_date=start.strftime("%Y-%m-%d"),
        end_forecaster_date=end.strftime("%Y-%m-%d"),
    )


console = Console()


def main() -> int:
    load_dotenv()
    try:
        client = MiniMaxClient()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    messages: list[dict] = [{"role": "system", "content": _build_system_prompt()}]

    console.print(
        Panel.fit(
            f"[bold]AI-assistant[/bold] · 模型 {client.model}\n"
            "输入内容直接回车发送 · /clear 清空 · /quit 退出 · "
            "/template [公司] 注入股票分析模板",
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
        if user_input.startswith("/template"):
            parts = user_input.split(maxsplit=1)
            company = parts[1].strip() if len(parts) == 2 else "AAPL"
            user_input = _render_user_template(company)
            console.print(
                Panel(
                    Markdown(user_input),
                    title=f"已注入模板 · {company.upper()}",
                    border_style="yellow",
                )
            )

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