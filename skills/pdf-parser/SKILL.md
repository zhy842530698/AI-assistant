---
name: pdf-parser
description: 解析 PDF 文件并输出结构化内容。触发场景：(1) 用户提供 PDF 并要求提取文字/表格；(2) 解析招股书、财报、年报等长文档；(3) 批量将 PDF 转为 Markdown / JSON；(4) 从 PDF 中抽取关键章节（目录、风险提示、财务摘要等）。支持本地文件路径和 URL。
---

# PDF Parser Skill

把 PDF 文件解析成结构化文本（Markdown / JSON / 纯文本），方便后续喂给 LLM 分析或保存归档。

## 快速使用

```bash
# 解析本地 PDF → Markdown（默认）
python3 <skill_dir>/scripts/parse_pdf.py /path/to/file.pdf

# 解析远程 PDF
python3 <skill_dir>/scripts/parse_pdf.py https://example.com/file.pdf

# 指定输出格式和路径
python3 <skill_dir>/scripts/parse_pdf.py file.pdf -o out.md -f markdown
python3 <skill_dir>/scripts/parse_pdf.py file.pdf -o out.json -f json
python3 <skill_dir>/scripts/parse_pdf.py file.pdf -o out.txt  -f text

# 只提取前 N 页
python3 <skill_dir>/scripts/parse_pdf.py file.pdf --pages 1-10

# 仅提取表格
python3 <skill_dir>/scripts/parse_pdf.py file.pdf -f tables
```

## 输出格式

- **markdown**（默认）：保留段落结构，表格转为 Markdown 表格
- **text**：纯文本，按页分隔
- **json**：结构化数据，含元信息（页数、作者、创建时间等）+ 每页文本
- **tables**：仅输出表格（CSV 形式）

## 功能特性

- 自动识别 PDF 类型：文本型 PDF / 扫描型 PDF
- 文本型 PDF：直接提取，速度快、保真度高
- 扫描型 PDF：自动 OCR（需安装 `pytesseract` + `tesseract`）
- 表格识别：使用 `pdfplumber`，转换为 Markdown / CSV
- 批量处理：支持目录扫描（见 `scripts/batch_parse.py`）
- 元信息提取：标题、作者、页数、创建日期

## 依赖

```bash
# 核心依赖
pip install pdfplumber pdfminer.six PyPDF2

# 可选：扫描型 PDF OCR
brew install tesseract          # macOS
pip install pytesseract pdf2image
```

## 使用示例

### 示例 1：解析港交所招股书 PDF

```bash
python3 <skill_dir>/scripts/parse_pdf.py \
  https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0629/2026062900025.pdf \
  -o output/MOMENTA_prospectus.md
```

输出 `output/MOMENTA_prospectus.md`，包含：
- 标题、页数等元信息
- 每页 Markdown 文本
- 自动识别的表格（转为 Markdown 表格）

### 示例 2：批量解析目录下的所有 PDF

```bash
python3 <skill_dir>/scripts/batch_parse.py ./pdfs/ -o ./output/
```

递归扫描 `./pdfs/`，每个 PDF 生成同名 `.md` 文件到 `./output/`。

### 示例 3：只提取前 20 页

```bash
python3 <skill_dir>/scripts/parse_pdf.py file.pdf --pages 1-20
```

适合快速预览长文档（如招股书 500+ 页）。

## 集成到 AI-assistant 项目

可在 `chat.py` 中调用本 skill，把 PDF 内容作为上下文喂给 LLM：

```python
import subprocess

def parse_pdf(pdf_path: str) -> str:
    result = subprocess.run(
        ["python3", "<skill_dir>/scripts/parse_pdf.py", pdf_path, "-f", "text"],
        capture_output=True, text=True
    )
    return result.stdout
```

## 注意事项

- **大文件**：招股书可能 500+ 页，全量解析会消耗大量 token。建议先用 `--pages` 提取关键章节
- **扫描型 PDF**：OCR 速度慢（~5 秒/页），且准确率不如文本型
- **加密 PDF**：需要先解密（用 `qpdf --decrypt`）
- **表格复杂度**：跨页表格可能识别不完整，需要人工校对
- **编码问题**：部分 PDF 包含非 UTF-8 字符，脚本会自动尝试 GBK / Latin-1 回退

## 错误处理

- **文件不存在**：提示检查路径
- **PDF 损坏**：提示用 `qpdf --check` 验证
- **权限不足**：提示检查文件权限
- **OCR 失败**：提示安装 tesseract

## 后续扩展

- [ ] 支持多线程批量处理
- [ ] 集成 LLM 自动摘要（结合 chat.py）
- [ ] 支持 PDF → DOCX 转换
- [ ] 支持图片提取（用 `pdf2image`）