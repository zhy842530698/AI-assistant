"""港交所主板新股信息抓取。

默认输出：output/hkex_listings.tsv（tab 分隔：公司代号、公司名、PDF 链接）

用法：
    python spider.py                  # 默认输出到 output/hkex_listings.tsv
    python spider.py -o my.tsv        # 自定义输出
    python spider.py --print          # 只打印到终端
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://www2.hkexnews.hk/New-Listings/New-Listing-Information/Main-Board?sc_lang=en"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_OUTPUT = "output/hkex_listings.tsv"


def fetch_listing_rows(url: str = URL) -> list[str]:
    """返回 tab 分隔的行（公司代号\t公司名\tPDF 链接），已去重。"""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows: list[str] = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        first_col = tds[0].get_text(strip=True)
        second_col = tds[1].get_text(strip=True)
        a_tags = tds[2].select('a[rel~="noopener"][rel~="noreferrer"]')
        if not a_tags:
            continue
        for a in a_tags:
            href = (a.get("href") or "").strip()
            if not href:
                continue
            full_url = urljoin(url, href)
            if not full_url.lower().endswith(".pdf"):
                continue
            rows.append(f"{first_col}\t{second_col}\t{full_url}")

    # 去重保序
    return list(dict.fromkeys(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description="港交所主板新股 PDF 链接抓取")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help=f"输出 TSV 路径（默认 {DEFAULT_OUTPUT}）")
    parser.add_argument("--print", action="store_true",
                        help="只打印到终端，不写文件")
    parser.add_argument("--url", default=URL, help="目标 URL（调试用）")
    args = parser.parse_args()

    rows = fetch_listing_rows(args.url)

    if args.print:
        for line in rows:
            print(line)
        return 0

    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    print(f"✓ 已保存 {len(rows)} 条记录 → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())