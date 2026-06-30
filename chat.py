"""终端 REPL：和 MiniMax-M3 多轮对话（金融分析师角色）。"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import subprocess
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


# ---------------------------------------------------------------------------
# /pdf 命令相关：解析 HKEX 新股 PDF
# ---------------------------------------------------------------------------

HERE = pathlib.Path(__file__).resolve().parent
EXTRACT_SCRIPT = HERE / "skills" / "hk-ipo-pdf-extractor" / "scripts" / "extract.py"
DEFAULT_LISTINGS_TSV = HERE / "output" / "hkex_listings.tsv"


def _resolve_pdf_url(arg: str) -> tuple[str, str] | None:
    """根据参数解析 PDF URL。返回 (url, label)，失败返回 None。

    支持三种形式：
      1. http(s)://...  → URL 直接用
      2. 纯数字          → DEFAULT_LISTINGS_TSV 第 N 行
      3. 其他字符串      → 在 TSV 里模糊匹配公司名
    """
    arg = arg.strip()
    if not arg:
        return None

    if arg.startswith(("http://", "https://")):
        return arg, arg

    if not DEFAULT_LISTINGS_TSV.exists():
        console.print(f"[red]找不到 {DEFAULT_LISTINGS_TSV}，请先跑 python3 spider.py[/red]")
        return None

    rows = [
        line.split("\t")
        for line in DEFAULT_LISTINGS_TSV.read_text(encoding="utf-8").splitlines()
        if line.count("\t") >= 2
    ]
    if not rows:
        console.print("[red]TSV 为空[/red]")
        return None

    # 纯数字 → 行号
    if arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(rows):
            code, name, url = rows[idx][0], rows[idx][1], rows[idx][2]
            return url, f"#{arg} {code} {name}"
        console.print(f"[red]行号超出范围（共 {len(rows)} 行）[/red]")
        return None

    # 否则模糊匹配公司名 / 代码
    needle = arg.lower()
    for code, name, url in rows:
        if needle in name.lower() or needle in code.lower():
            return url, f"{code} {name}"
    console.print(f"[red]在 TSV 中找不到匹配 '{arg}' 的公司[/red]")
    return None


def _run_pdf_extract(pdf_url: str) -> dict | None:
    """调 hk-ipo-pdf-extractor 抽取，stdout 是 JSON，返回 dict。"""
    if not EXTRACT_SCRIPT.exists():
        console.print(f"[red]找不到抽取脚本: {EXTRACT_SCRIPT}[/red]")
        return None

    console.print(f"[dim]正在抽取 {pdf_url} ...[/dim]")
    try:
        proc = subprocess.run(
            [sys.executable, str(EXTRACT_SCRIPT), pdf_url],
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        console.print("[red]抽取超时（>10 分钟）[/red]")
        return None

    if proc.returncode != 0:
        console.print(f"[red]抽取失败 (exit {proc.returncode}):[/red]")
        console.print(f"[red]{proc.stderr[:500]}[/red]")
        return None

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        console.print(f"[red]解析 JSON 失败: {e}[/red]")
        return None


def _format_extract_for_context(data: dict) -> str:
    """把抽取结果格式化成可读文本，送进 LLM 上下文。"""
    lines = ["【港股新股 PDF 抽取结果（hk-ipo-pdf-extractor）】"]
    for k in (
        "stock_code", "company_name_en", "company_name_cn", "document_type",
        "offer_price_min", "offer_price_max", "final_offer_price",
        "board_lot", "one_lot_entry_fee_hkd",
        "application_start", "application_deadline",
        "allotment_result_time", "listing_time", "source_url",
    ):
        v = data.get(k)
        if v is not None:
            lines.append(f"- {k}: {v}")
    if data.get("evidence_summary"):
        lines.append(f"\n抽取说明: {data['evidence_summary']}")
    if data.get("_parse_error"):
        lines.append(f"\n[警告] JSON 解析异常: {data['_parse_error']}")
    return "\n".join(lines)


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
            "/template [公司] 注入股票分析模板 · "
            "/pdf <URL|行号|公司> 抽取港股 PDF",
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
        elif user_input.startswith("/pdf"):
            parts = user_input.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) == 2 else ""
            resolved = _resolve_pdf_url(arg)
            if not resolved:
                continue
            pdf_url, label = resolved
            data = _run_pdf_extract(pdf_url)
            if not data:
                continue
            # 预览
            console.print(
                Panel(
                    _format_extract_for_context(data),
                    title=f"已抽取 · {label}",
                    border_style="magenta",
                )
            )
            # 拼到 messages 里，让模型基于结构化数据回答
            user_input = (
                f"以下是用户调 /pdf {arg} 抽取出来的港股 PDF 结构化数据：\n\n"
                + _format_extract_for_context(data)
                + "\n\n请基于以上数据，向用户介绍这只新股。"
            )

        messages.append({"role": "user", "content": user_input})

        # ---- debug: 打印即将发出去的请求体 ----
        try:
            payload = client.build_payload(messages)  # type: ignore[attr-defined]
            console.print(
                Panel(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    title="[dim]→ 请求体[/dim]",
                    border_style="dim",
                )
            )
        except AttributeError:
            # 如果 MiniMaxClient 没暴露 build_payload，就退化为打印 messages
            console.print(
                Panel(
                    json.dumps(messages, ensure_ascii=False, indent=2),
                    title="[dim]→ messages[/dim]",
                    border_style="dim",
                )
            )

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