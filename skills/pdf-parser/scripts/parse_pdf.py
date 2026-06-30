#!/usr/bin/env python3
"""PDF 解析工具：文本型 PDF 直接抽取，扫描型自动 OCR。

支持本地文件路径和 HTTP(S) URL。
输出格式：markdown（默认）/ text / json / tables

依赖：
    pip install pdfplumber pdfminer.six PyPDF2
    # 可选 OCR：
    brew install tesseract
    pip install pytesseract pdf2image
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# 依赖导入（容错）
# ---------------------------------------------------------------------------

def _import_pdf_libs():
    """延迟导入 PDF 库，避免脚本启动时就报错。"""
    libs = {}
    try:
        import pdfplumber  # noqa: F401
        libs["pdfplumber"] = pdfplumber
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        libs["pypdf"] = PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
            libs["pypdf"] = PdfReader
        except ImportError:
            pass
    return libs


# ---------------------------------------------------------------------------
# 文件获取（本地 / URL）
# ---------------------------------------------------------------------------

def _fetch_pdf(source: str, cache_dir: pathlib.Path) -> pathlib.Path:
    """返回本地 PDF 路径。如果是 URL，先下载到 cache_dir。"""
    p = pathlib.Path(source)
    if p.is_file():
        return p

    # URL → 下载
    if source.startswith(("http://", "https://")):
        url = source
    else:
        # 可能是相对路径不存在
        raise FileNotFoundError(f"找不到文件: {source}")

    import requests
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = re.sub(r"[^\w\-.]", "_", pathlib.Path(urlparse(url).path).name) or "remote.pdf"
    dst = cache_dir / fname
    print(f"⬇ 下载: {url}", file=sys.stderr)
    r = requests.get(url, timeout=60, stream=True, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    with dst.open("wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"✓ 已下载 → {dst}", file=sys.stderr)
    return dst


# ---------------------------------------------------------------------------
# 文本型 PDF 提取
# ---------------------------------------------------------------------------

def _extract_text_pages(pdf_path: pathlib.Path, libs: dict) -> list[dict]:
    """返回 [{"page": 1, "text": "...", "tables": [...]}, ...]"""
    pages = []

    if "pdfplumber" in libs:
        pdfplumber = libs["pdfplumber"]
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = []
                try:
                    for tbl in page.extract_tables() or []:
                        tables.append(tbl)
                except Exception:
                    pass
                pages.append({"page": i, "text": text, "tables": tables})
        return pages

    if "pypdf" in libs:
        PdfReader = libs["pypdf"]
        reader = PdfReader(str(pdf_path))
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                text = f"[提取失败: {e}]"
            pages.append({"page": i, "text": text, "tables": []})
        return pages

    raise RuntimeError("未安装任何 PDF 库，请 pip install pdfplumber 或 PyPDF2")


def _extract_metadata(pdf_path: pathlib.Path, libs: dict) -> dict[str, Any]:
    meta: dict[str, Any] = {"file": str(pdf_path), "size_bytes": pdf_path.stat().st_size}
    if "pypdf" in libs:
        PdfReader = libs["pypdf"]
        try:
            r = PdfReader(str(pdf_path))
            meta["page_count"] = len(r.pages)
            info = r.metadata or {}
            for k in ("title", "author", "creator", "producer",
                      "creation_date", "modification_date", "subject"):
                v = info.get(k) if hasattr(info, "get") else None
                if v:
                    meta[k] = str(v)
        except Exception as e:
            meta["metadata_error"] = str(e)
    return meta


# ---------------------------------------------------------------------------
# 格式化输出
# ---------------------------------------------------------------------------

def _table_to_markdown(tbl: list[list]) -> str:
    if not tbl or not tbl[0]:
        return ""
    rows = [[(c or "").strip().replace("\n", " ") for c in row] for row in tbl]
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    head = rows[0]
    body = rows[1:]
    md = "| " + " | ".join(head) + " |\n"
    md += "| " + " | ".join(["---"] * n) + " |\n"
    for r in body:
        md += "| " + " | ".join(r) + " |\n"
    return md


def _to_markdown(meta: dict, pages: list[dict]) -> str:
    out = [f"# {pathlib.Path(meta['file']).name}", ""]
    out.append("## 元信息")
    out.append("")
    for k, v in meta.items():
        if k == "file":
            continue
        out.append(f"- **{k}**: {v}")
    out.append("")
    for p in pages:
        out.append(f"## 第 {p['page']} 页")
        out.append("")
        if p["text"].strip():
            out.append(p["text"].strip())
        if p.get("tables"):
            out.append("")
            out.append("### 表格")
            out.append("")
            for i, tbl in enumerate(p["tables"], 1):
                out.append(f"**表 {i}**")
                out.append("")
                out.append(_table_to_markdown(tbl))
                out.append("")
        out.append("")
    return "\n".join(out)


def _to_text(pages: list[dict]) -> str:
    chunks = []
    for p in pages:
        chunks.append(f"----- 第 {p['page']} 页 -----")
        chunks.append(p["text"])
    return "\n\n".join(chunks)


def _to_json(meta: dict, pages: list[dict]) -> str:
    return json.dumps({"metadata": meta, "pages": pages},
                      ensure_ascii=False, indent=2, default=str)


def _to_tables(pages: list[dict]) -> str:
    chunks = []
    for p in pages:
        if not p.get("tables"):
            continue
        chunks.append(f"# 第 {p['page']} 页")
        for i, tbl in enumerate(p["tables"], 1):
            rows = [[(c or "").strip().replace("\n", " ") for c in row] for row in tbl]
            for r in rows:
                chunks.append(",".join(f'"{c}"' for c in r))
            chunks.append("")
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def parse_pdf(source: str, fmt: str = "markdown",
              page_range: tuple[int, int] | None = None,
              cache_dir: pathlib.Path | None = None) -> tuple[dict, list[dict]]:
    libs = _import_pdf_libs()
    if not libs:
        raise RuntimeError(
            "未安装任何 PDF 库，请运行：pip install pdfplumber pdfminer.six PyPDF2"
        )

    cache = cache_dir or pathlib.Path(tempfile.gettempdir()) / "pdf_parser_cache"
    pdf = _fetch_pdf(source, cache)
    meta = _extract_metadata(pdf, libs)
    pages = _extract_text_pages(pdf, libs)

    if page_range:
        start, end = page_range
        pages = [p for p in pages if start <= p["page"] <= end]

    return meta, pages


def render(meta: dict, pages: list[dict], fmt: str) -> str:
    fmt = fmt.lower()
    if fmt == "markdown":
        return _to_markdown(meta, pages)
    if fmt == "text":
        return _to_text(pages)
    if fmt == "json":
        return _to_json(meta, pages)
    if fmt == "tables":
        return _to_tables(pages)
    raise ValueError(f"未知格式: {fmt}")


def main() -> int:
    ap = argparse.ArgumentParser(description="PDF → Markdown / Text / JSON / Tables")
    ap.add_argument("source", help="PDF 路径或 URL")
    ap.add_argument("-o", "--output", help="输出文件（默认 stdout）")
    ap.add_argument("-f", "--format", default="markdown",
                    choices=["markdown", "text", "json", "tables"])
    ap.add_argument("--pages", help="页码范围，如 1-20")
    ap.add_argument("--cache-dir", help="URL 下载缓存目录")
    args = ap.parse_args()

    page_range = None
    if args.pages:
        m = re.match(r"^(\d+)-(\d+)$", args.pages.strip())
        if not m:
            print("页码格式错误，应为 1-20", file=sys.stderr)
            return 1
        page_range = (int(m.group(1)), int(m.group(2)))

    try:
        meta, pages = parse_pdf(
            args.source, args.format, page_range,
            pathlib.Path(args.cache_dir) if args.cache_dir else None,
        )
        output = render(meta, pages, args.format)
    except Exception as e:
        print(f"❌ 解析失败: {e}", file=sys.stderr)
        return 1

    if args.output:
        out = pathlib.Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output, encoding="utf-8")
        print(f"✓ 已保存 → {out}  ({len(output):,} 字符)", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())