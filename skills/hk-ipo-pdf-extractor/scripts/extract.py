#!/usr/bin/env python3
"""港股新股 PDF → 结构化 JSON（按 SKILL.md 第 13 节 Prompt + 第 15 节标准化）。

依赖：
    pip install pdfplumber pdfminer.six PyPDF2 requests
    export MINIMAX_API_KEY=...

用法：
    python3 extract.py <pdf_url>
    python3 extract.py <pdf_url> -o output.json
    python3 extract.py <pdf_url> --pages 1-30
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
PROJECT_DIR = SKILL_DIR.parent.parent  # AI-assistant/
PDF_PARSER = SKILL_DIR.parent / "pdf-parser" / "scripts" / "parse_pdf.py"


# ---------------------------------------------------------------------------
# SKILL.md 第 13 节 Prompt
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
你是港股新股 PDF 结构化抽取助手。

请根据输入的 HKEX PDF 文本块、表格和 OCR 内容，抽取港股打新相关字段。

要求：
1. 只能根据输入内容抽取，不要使用外部知识。
2. 不要猜测，缺失字段填 null。
3. 日期统一转换为 ISO 8601 格式。
4. 港股时间默认使用 Asia/Hong_Kong 时区。
5. 金额去除千分位逗号，并转为 number。
6. 股数去除千分位逗号，并转为 integer。
7. 百分比同时保留原文和 decimal 数值。
8. 表格数据必须保持原始行列关系。
9. 每个关键字段必须给出 evidence，包括 page_no、原文片段。
10. 如果字段来自计算，需要说明计算来源。
11. 输出严格 JSON，不要输出解释性文字。
12. 不要给出是否值得申购的投资建议。

重点抽取：
- 公司名称（中英文）
- 股票代码
- 文档类型
- 一手股数 (board_lot)
- 招股价区间 (offer_price_min/max)
- 最终发售价 (final_offer_price)
- 一手入场费 (one_lot_entry_fee_hkd)
- 申购开始/截止时间
- 公布结果时间
- 上市交易时间
- 全球发售 / 香港公开发售 / 国际发售股份数
- 回拨机制 / 超额配售权
- 基石投资人
- 保荐人 / 承销商
- 财务快照
- 募资用途
- 风险因素
"""


# ---------------------------------------------------------------------------
# SKILL.md 第 20 节 MVP 字段
# ---------------------------------------------------------------------------

MVP_FIELDS = [
    "stock_code",
    "company_name_en",
    "company_name_cn",
    "document_type",
    "offer_price_min",
    "offer_price_max",
    "final_offer_price",
    "board_lot",
    "one_lot_entry_fee_hkd",
    "application_start",
    "application_deadline",
    "allotment_result_time",
    "listing_time",
    "source_url",
]


# ---------------------------------------------------------------------------
# Step 1: 调 pdf-parser 抽文本
# ---------------------------------------------------------------------------

def extract_text_via_pdf_parser(pdf_url: str, pages: str | None = None) -> str:
    """调 pdf-parser skill 抽文本，返回 text 格式字符串。"""
    cmd = [
        sys.executable,
        str(PDF_PARSER),
        pdf_url,
        "-f", "text",
    ]
    if pages:
        cmd += ["--pages", pages]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(
            f"pdf-parser 失败 (exit {result.returncode}):\n{result.stderr[:500]}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Step 2 & 3: 调 LLM 抽 JSON
# ---------------------------------------------------------------------------

def _load_minimax_client():
    """从项目 client.py 加载 MiniMax 客户端。"""
    sys.path.insert(0, str(PROJECT_DIR))
    try:
        from client import MiniMaxClient  # type: ignore
        return MiniMaxClient()
    except Exception as e:
        raise RuntimeError(
            f"无法加载 MiniMaxClient：{e}\n"
            f"请确认 {PROJECT_DIR}/client.py 存在且环境变量 MINIMAX_API_KEY 已设置"
        )


def call_llm_for_extraction(client, text: str, source_url: str) -> dict[str, Any]:
    """把 PDF 文本发给 LLM，让它按 MVP 字段抽取并返回 JSON。"""
    # 控制上下文长度：招股书前 30 页 text 大约 30~60K 字符，
    # 截到 80K 避免爆 token；优先保留前面。
    MAX_CHARS = 80_000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[... 已截断，后续内容省略 ...]"

    user_msg = (
        "以下是一份港交所 HKEX PDF（来源 URL 见末尾）解析出的纯文本。"
        "请按系统提示中的规范抽取 MVP 字段，并输出严格 JSON。\n\n"
        f"--- PDF 文本开始 ---\n{text}\n--- PDF 文本结束 ---\n\n"
        f"source_url: {source_url}"
    )

    # 把 SKILL.md MVP JSON Schema 放在 user msg 末尾，强制模型按这个结构输出
    schema_hint = (
        "\n\n请严格输出以下 JSON 结构（缺失字段填 null）：\n"
        + json.dumps(
            {k: None for k in MVP_FIELDS + ["evidence_summary"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    user_msg += schema_hint

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    raw = client.chat(messages, temperature=0.1)
    return _parse_llm_json(raw)


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """从 LLM 回复里抠出 JSON（容忍 ```json ... ``` 围栏、前后多余文字）。"""
    raw = raw.strip()
    # 去掉 ```json 围栏
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        # 找第一个 { 到最后一个 }
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {
            "_parse_error": str(e),
            "_raw_response": raw[:2000],
        }


# ---------------------------------------------------------------------------
# Step 4: 字段标准化（金额去千分位等）
# ---------------------------------------------------------------------------

_NUMBER_CLEAN_RE = re.compile(r"[,\s]")


def _to_number(v: Any) -> Any:
    """从字符串里抠出数字（容忍 'HK$3,262.57' / '216,167,000'）。"""
    if v is None or isinstance(v, (int, float)):
        return v
    if not isinstance(v, str):
        return v
    s = _NUMBER_CLEAN_RE.sub("", v)
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m and "." in m.group(0) else (
        int(m.group(0)) if m else None
    )


def normalize_fields(data: dict[str, Any], source_url: str) -> dict[str, Any]:
    """按 SKILL.md 第 15 节规则做基础标准化。"""
    out = dict(data)
    # 数字字段
    for k in (
        "offer_price_min",
        "offer_price_max",
        "final_offer_price",
        "board_lot",
        "one_lot_entry_fee_hkd",
    ):
        if k in out:
            out[k] = _to_number(out[k])

    # 时间字段：暂保留 LLM 输出（已要求 ISO 8601），后续可加 dateutil 校验
    # URL 兜底
    if not out.get("source_url"):
        out["source_url"] = source_url

    # evidence_summary 兜底
    if "evidence_summary" not in out:
        out["evidence_summary"] = None

    # 保留所有原始字段（包括 _parse_error 等），方便调试
    return out


# ---------------------------------------------------------------------------
# Step 5: 主流程
# ---------------------------------------------------------------------------

def extract(pdf_url: str, pages: str | None = "1-30") -> dict[str, Any]:
    """端到端：URL → PDF 文本 → LLM JSON → 标准化 JSON。"""
    print(f"[1/4] 抽文本（pages={pages}）...", file=sys.stderr)
    text = extract_text_via_pdf_parser(pdf_url, pages)
    print(f"      ✓ {len(text):,} 字符", file=sys.stderr)

    print("[2/4] 加载 LLM 客户端...", file=sys.stderr)
    client = _load_minimax_client()
    print(f"      ✓ model={client.model}", file=sys.stderr)

    print("[3/4] 调 LLM 抽取 MVP 字段...", file=sys.stderr)
    raw_data = call_llm_for_extraction(client, text, pdf_url)
    print(f"      ✓ 字段数: {len(raw_data)}", file=sys.stderr)

    print("[4/4] 标准化字段...", file=sys.stderr)
    normalized = normalize_fields(raw_data, pdf_url)

    # 加上 meta
    normalized["_meta"] = {
        "pdf_url": pdf_url,
        "pages": pages,
        "text_chars": len(text),
        "skill_version": "hk-ipo-pdf-extractor/v1",
    }

    return normalized


def main() -> int:
    ap = argparse.ArgumentParser(description="港股新股 PDF → 结构化 JSON")
    ap.add_argument("pdf_url", help="HKEX PDF URL（http/https）")
    ap.add_argument("-o", "--output", help="输出 JSON 路径（默认 stdout）")
    ap.add_argument("--pages", default="1-30",
                    help="抽取页码范围（默认 1-30，'all' 表示全部）")
    args = ap.parse_args()

    pages = None if args.pages == "all" else args.pages

    try:
        result = extract(args.pdf_url, pages)
    except Exception as e:
        print(f"❌ 抽取失败: {e}", file=sys.stderr)
        return 1

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        out = pathlib.Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output, encoding="utf-8")
        print(f"✓ 已保存 → {out}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())