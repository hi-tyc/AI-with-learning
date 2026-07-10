from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse
from openai import APITimeoutError, APIConnectionError, APIStatusError, RateLimitError
from pydantic import BaseModel
from typing import Optional
import uuid
import json
import io
import base64
import re
from datetime import datetime
import os
import asyncio

from app.api.endpoints.auth import get_current_user
from app.api.endpoints.settings_api import _get_deepseek_model_name
from app.api.endpoints.match_answers import cleanup_matches_after_deletion
from app.api.endpoints.materials import _docx_to_html as _materials_docx_to_html
from app.core.user_data import (
    get_user_config_path,
    get_user_subject,
    get_problems_path,
    get_materials_path,
    get_answers_path,
    get_words_path,
    get_library_trash_path,
)
from app.core.paths import UPLOAD_DIR
from app.utils.file_lock import read_json, write_json, update_json
from app.utils.ai_client import create_client, DEEPSEEK_BASE_URL, KIMI_BASE_URL
from app.core.pricing import compute_cost, get_pricing, _pricing_key
from app.core.daily_cost import check_daily_limit, add_daily_cost

router = APIRouter()


def _safe_extract_json(text: str) -> dict | None:
    """Robust JSON extraction from AI response text with multiple fallback strategies."""
    if not text:
        return None

    cleaned = text.strip()
    # Remove markdown code blocks
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: json5 parse (if available)
    try:
        import json5
        return json5.loads(cleaned)
    except Exception:
        pass

    # Strategy 3: Extract outermost braces
    try:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        pass

    # Strategy 4: Fix common OCR/AI errors
    try:
        fixed = cleaned.replace("：", ":").replace("，", ",").replace("\u201c", """).replace("\u201d", """)
        # Replace single quotes with double quotes (simple heuristic)
        fixed = re.sub(r"(?<!\\)'", '"', fixed)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return None


def _normalize_choice_options(content: str) -> str:
    """
    对选择题选项做格式规范化：
    - 若同一行出现多个 A/B/C/D 选项，保持在一行，选项之间用 5 个空格分隔
    - 不合并原本就在多行的选项，不改变总行数
    """
    if not content:
        return content
    option_split_re = re.compile(r'\s+([A-D])\s*[.、)\]］】]\s*')
    lines = content.splitlines()
    out = []
    for line in lines:
        markers = list(option_split_re.finditer(line))
        if len(markers) >= 2:
            parts = option_split_re.split(line)
            stem = parts[0].rstrip()
            rebuilt = stem
            for i in range(1, len(parts), 2):
                label = parts[i]
                text = parts[i + 1].strip() if i + 1 < len(parts) else ""
                rebuilt += f"{' ' * 5}{label}. {text}"
            out.append(rebuilt)
        else:
            out.append(line)
    return "\n".join(out)


def _upsert_material(materials: list, file_id: str, filename: str, ext: str, data: bytes, extracted_text: str, ocr_text: str, tag: str, subject: str, now: str):
    """将上传的原始文件登记到 materials 列表；若已存在则补齐缺失字段。"""
    abs_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    for m in materials:
        if m.get("id") == file_id:
            if not m.get("file_path"):
                m["file_path"] = abs_path
            if not m.get("file_type"):
                m["file_type"] = ext.lstrip(".") if ext else "docx"
            if not m.get("file_size"):
                m["file_size"] = len(data) if data else 0
            if not m.get("filename"):
                m["filename"] = filename or f"未命名{ext}"
            if not m.get("subject"):
                m["subject"] = subject
            return
    materials.append({
        "id": file_id,
        "filename": filename or f"未命名{ext}",
        "subject": subject,
        "time": tag or "未分类",
        "tag": tag or "未分类",
        "summary": "",
        "file_path": abs_path,
        "file_type": ext.lstrip(".") if ext else "docx",
        "file_size": len(data) if data else 0,
        "has_text": bool(extracted_text) or bool(ocr_text),
        "created_at": now,
    })


# ========== 规则级提取兜底（提升小题识别准确率）==========

_ITEM_NUMBER_RE = re.compile(
    r'(?:^|\n\s*)'              # 行首或换行后
    r'(?:'
        r'\d{1,3}[\.、\)\]］】]'  # 1. 1、 1) 1]
        r'|'
        r'[（(]\d{1,3}[)）]'      # (1) （1）
        r'|'
        r'[①②③④⑤⑥⑦⑧⑨⑩]'        # 圆圈数字
    r')\s*',
    re.MULTILINE,
)

_READING_PASSAGE_RE = re.compile(
    r'( passages? | reading | 阅读理解 | 阅读下面短文 | 完形填空 | cloze )',
    re.IGNORECASE,
)


def _split_items_by_rules(text: str, doc_type: str = "题目") -> list[dict]:
    """当 AI JSON 提取完全失败时，用规则保守拆分条目。

    仅对题目/答案做拆分；返回 [{"content": "..."}, ...]。
    注意：不拆分阅读理解/完形填空等长文，避免把一道大题截断。
    """
    if not text or not text.strip():
        return []

    # 阅读理解、完形填空等长文整体是一道题，不拆分，避免截断
    if _READING_PASSAGE_RE.search(text):
        return []

    # 清理 markdown 表格分隔线、多余空行
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|---'):
            continue
        if stripped:
            cleaned_lines.append(line.rstrip())
        else:
            cleaned_lines.append('')

    # 把多行文本重新拼成一段，保留空行作为段落分隔
    paragraphs = []
    current = []
    for line in cleaned_lines:
        if line.strip():
            current.append(line)
        else:
            if current:
                paragraphs.append('\n'.join(current))
                current = []
    if current:
        paragraphs.append('\n'.join(current))

    items = []

    # 策略 1：按题号切分（每个题号开启新 item）
    # 合并段落后再切分，避免段落内题号被拆散
    full_text = '\n'.join(cleaned_lines)
    matches = list(_ITEM_NUMBER_RE.finditer(full_text))
    if len(matches) >= 2:
        # 按题号位置切分
        last_end = 0
        for i, m in enumerate(matches):
            start = m.start()
            if i == 0:
                # 第一个题号之前的文本忽略
                last_end = start
                continue
            segment = full_text[last_end:start].strip()
            if segment and len(segment) >= 6:
                items.append({"content": segment})
            last_end = start
        # 最后一段
        segment = full_text[last_end:].strip()
        if segment and len(segment) >= 6:
            items.append({"content": segment})

    # 策略 2：如果按题号切分太少，按段落切分
    if len(items) < 2 and len(paragraphs) >= 2:
        items = [{"content": p.strip()} for p in paragraphs if p.strip()]

    # 过滤掉过短/非题目/非答案的噪声
    result = []
    for it in items:
        content = it.get("content", '').strip()
        if len(content) < 6:
            continue
        # 跳过表头行
        if content.lower() in ('中文', '词性', '英文', 'chinese', 'pos', 'english'):
            continue
        result.append({"content": content})

    # 对答案文档，尝试保留 【答案】标记后的内容
    if doc_type == "答案" and not result:
        result = [{"content": p.strip()} for p in paragraphs if p.strip() and len(p.strip()) >= 6]

    return [{"content": _normalize_choice_options(it.get("content", ""))} for it in result]


def _extract_words_from_markdown_table(text: str) -> list[dict]:
    """从 Markdown 表格中抽取词单三列（中文/词性/英文）。

    支持常见表头顺序：中文-词性-英文、英文-词性-中文。
    """
    words = []
    lines = text.splitlines()
    header_idx = None
    headers = []
    for i, line in enumerate(lines):
        cells = [c.strip().strip('*').strip() for c in line.split('|')]
        cells = [c for c in cells if c]
        lowered = [c.lower() for c in cells]
        if any(h in lowered for h in ('中文', 'chinese', '英文', 'english', '词性', 'pos')):
            header_idx = i
            headers = cells
            break

    if header_idx is None or header_idx + 1 >= len(lines):
        return words

    # 映射列顺序
    def _col_index(keywords):
        for kw in keywords:
            for j, h in enumerate(headers):
                if kw in h.lower():
                    return j
        return None

    cn_idx = _col_index(['中文', 'chinese', '释义'])
    en_idx = _col_index(['英文', 'english'])
    pos_idx = _col_index(['词性', 'pos', 'part'])

    if cn_idx is None and en_idx is None:
        return words

    for line in lines[header_idx + 1:]:
        stripped = line.strip()
        # 跳过分隔线、空行
        if stripped.startswith('|---') or stripped.startswith('| ---') or stripped.startswith('|-'):
            continue
        if not stripped.replace('|', '').replace('-', '').replace(' ', ''):
            continue
        cells = [c.strip().strip('*').strip() for c in line.split('|')]
        cells = [c for c in cells if c]
        if not cells:
            continue
        cn = cells[cn_idx] if cn_idx is not None and cn_idx < len(cells) else ''
        en = cells[en_idx] if en_idx is not None and en_idx < len(cells) else ''
        pos = cells[pos_idx] if pos_idx is not None and pos_idx < len(cells) else ''
        # 忽略表头重复行或空行
        if not cn and not en:
            continue
        if cn.lower() in ('中文', 'chinese') or en.lower() in ('英文', 'english'):
            continue
        words.append({"chinese": cn, "pos": pos, "english": en})

    return words


def _extract_words_fallback(raw: str, text: str) -> list[dict]:
    """词单提取的多层 fallback。"""
    words = []
    # 1. JSON
    extracted = _safe_extract_json(raw)
    if extracted:
        w = extracted.get("words", [])
        if isinstance(w, list):
            words = w
    # 2. 正则字段
    if not words and raw:
        cleaned_fallback = raw.strip()
        triples = re.findall(r'"chinese"\s*:\s*"([^"]*)"\s*,\s*"pos"\s*:\s*"([^"]*)"\s*,\s*"english"\s*:\s*"([^"]*)"', cleaned_fallback)
        if not triples:
            triples = re.findall(r'"english"\s*:\s*"([^"]*)"\s*,\s*"pos"\s*:\s*"([^"]*)"\s*,\s*"chinese"\s*:\s*"([^"]*)"', cleaned_fallback)
            triples = [(c, p, e) for e, p, c in triples]
        if triples:
            words = [{"chinese": c, "pos": p, "english": e} for c, p, e in triples]
        if not words:
            pairs = re.findall(r'"english"\s*:\s*"([^"]*)"\s*,\s*"chinese"\s*:\s*"([^"]*)"', cleaned_fallback)
            if not pairs:
                pairs = re.findall(r'"chinese"\s*:\s*"([^"]*)"\s*,\s*"english"\s*:\s*"([^"]*)"', cleaned_fallback)
            if pairs:
                words = [{"chinese": c, "pos": "", "english": e} for e, c in pairs]
    # 3. Markdown 表格
    if not words and text:
        words = _extract_words_from_markdown_table(text)
    return words


def _dedup_key(content: str) -> str:
    """比 content[:100] 更稳定的去重键：短文本用完整内容，长文本取归一化后前 200 字符。"""
    if not content:
        return ''
    # 归一化：去掉多余空白、统一标点
    normalized = re.sub(r'\s+', ' ', content).strip()
    if len(normalized) <= 80:
        return normalized
    return normalized[:200]


def _chunk_text_for_extraction(text: str, chunk_size: int = 10000, overlap: int = 500) -> list[str]:
    """长文档分段提取，避免 12000 截断丢失后半部分。"""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        # 在段落边界处截断
        boundary = text.rfind('\n\n', end - overlap, end)
        if boundary == -1:
            boundary = text.rfind('\n', end - overlap, end)
        if boundary == -1 or boundary <= start:
            boundary = end
        chunks.append(text[start:boundary])
        start = boundary
    return chunks



# ========== 统一 Prompt 常量（三处复用，避免漂移）==========

EXTRACT_PROMPT = """你是一个严格的英语题目提取助手。根据以下文档内容，逐题/逐条完整提取。

## 核心原则
**不要填写答案。保留题目原文中的所有空格、横线、填空和空位原样。只提取题目本身，不提供解答或填入答案。**

## 题型处理规则（必须遵守）

### 单选题 / 阅读理解选择题
- 保留完整题干和所有选项 A/B/C/D
- 不要把答案填入选项中

### 首字母填空 / 语法填空 / 变形填空
- 保留原题的填空格式，**不要填入答案**
- 保持空格/横线原样，例如：
  - "The old bridge c________ during the storm."
  - "She ______ (go) to school every day."
- 括号中的原词保留，但**不要填写变形后的答案**

### 阅读理解题
- 一篇文章 + 其所有问题算作 **一道题**
- 将文章原文和所有问题合并到一条 item 的 content 中
- 格式示例：
  "[文章原文]\n\n1. 问题1\n2. 问题2\n..."

### 完形填空
- 文章与所有空算作一道题，保留文章上下文和空位

### 词单 / 默写表
- 每个单词或词组单独作为一条 item，content 中保留原行内容

## 输出要求
- 每道题一条 item，不要合并多题
- 保留题号、完整原文、选项
- 选择题保留所有选项（A/B/C/D）
- 输出严格 JSON，不要 Markdown 代码块

## 输出格式
{"items": [{"content": "完整题目内容"}]}
只输出JSON。"""

ANSWER_EXTRACT_PROMPT = """你是一个严格的英语答案提取助手。根据以下文档内容，逐条完整提取所有已经填写好的答案内容。

## 核心原则
**文档中已经包含了填写好的答案（如选项字母、填空内容）。你的任务是把这些答案原样提取出来，不要删除任何已填内容。**

## 题型处理规则

### 选择题
- 保留题号 + 题干 + 所有选项 + 正确答案标注（如有）
- 示例：
  "1. —What's this? —It's ___ orange.\n   A. a  B. an  C. the  D. /\n   答案：B"

### 填空题 / 首字母填空 / 变形填空
- 保留完整句子 + 已填写的答案（括号内或横线上）
- 示例：
  "2. She ______ (go) to school every day.\n   答案：goes"
  "3. The old bridge c________ during the storm.\n   答案：collapsed"

### 翻译/写作题
- 保留题目 + 参考译文或范文

## 输出要求
- 每道题或每条答案作为一条独立的 item
- 保留原文格式和排版
- 输出严格 JSON，不要 Markdown 代码块

## 输出格式
{"items": [{"content": "完整的答案内容（含题号、题干和已填答案）"}]}
只输出JSON。"""

WORD_EXTRACT_PROMPT = """你是一个英语词单提取助手。根据以下文档内容（Markdown 表格），提取所有单词/词组及其中文释义和词性。

## 规则
- 文档通常是三列表格，列名可能是「中文/词性/英文」或「英文/词性/中文」或类似变体
- 请按实际列含义提取，不要拘泥于列顺序
- 逐词提取每个单词或词组
- 保留原文的拼写和大小写
- 如果某个词没有明确的词性，pos 字段留空字符串
- 学生版词单中 english 列为空，也要提取 chinese 和 pos

## 输出格式
{"words": [{"chinese": "中文释义", "pos": "词性", "english": "英文单词"}]}
只输出JSON，不要额外文字。"""


MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89\x50\x4e\x47"
MAGIC_PDF = b"%PDF"
MAGIC_ZIP = b"PK\x03\x04"

def _is_image(data: bytes) -> bool:
    return data.startswith(MAGIC_JPEG) or data.startswith(MAGIC_PNG)

def _is_pdf(data: bytes) -> bool:
    return data.startswith(MAGIC_PDF)

def _is_docx(data: bytes, filename: str = "") -> bool:
    if not data.startswith(MAGIC_ZIP):
        return False
    if filename.lower().endswith(".docx"):
        return True
    try:
        import zipfile
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False

async def _compress_image(data: bytes, max_long: int, quality: int) -> bytes:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_long:
            ratio = max_long / max(w, h)
            w, h = int(w * ratio), int(h * ratio)
            img = img.resize((w, h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        # 文字文档需要更高质量，防止小字号、下划线、选项字母模糊
        effective_quality = max(quality, 65)
        img.save(buf, format="JPEG", quality=effective_quality, optimize=True)
        return buf.getvalue()
    except Exception:
        pass
    return data

async def _local_ocr(image_data: bytes) -> str:
    """本地OCR识别图片文字。优先使用 pytesseract，失败则返回空字符串。"""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(img, lang="eng+chi_sim")
        return text.strip()
    except Exception:
        return ""

async def _kimi_ocr(api_key: str, model: str, images: list[bytes], timeout: int) -> str:
    """Use Kimi Vision to extract text from scanned page images."""
    try:
        client = create_client(api_key, KIMI_BASE_URL, timeout)
        content = []
        for i, img_data in enumerate(images):
            b64 = base64.b64encode(img_data).decode("utf-8")
            content.append({"type": "text", "text": f"[第{i+1}页]"})
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        content.append({"type": "text", "text": "\n请逐页提取以上图片中的所有文字内容，保持原文格式和段落。直接输出文字，不要额外说明。"})

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是OCR识别助手。提取图片中的全部英文和中文文字，保持原文段落格式。"},
                {"role": "user", "content": content}
            ],
            max_tokens=16384,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return (response.choices[0].message.content or "").strip()
    except APITimeoutError:
        return "__kimi_timeout__"
    except RateLimitError:
        return "__kimi_ratelimit__"
    except (APIConnectionError, APIStatusError):
        return "__kimi_error__"
    except Exception:
        return ""

async def _pdf_to_pages(data: bytes, file_id: str, quality: int, max_long: int):
    import fitz
    pdf_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(data)
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        text_len = len(text)
        image_count = len(page.get_images())
        # 扫描页判定放宽：稀疏文字页不强行 OCR；只有真正少文字且图多，或图极多才走 OCR
        is_scanned = (text_len < 120 and image_count >= 3) or (image_count >= 8)
        if is_scanned:
            # 文字 OCR 用较大分辨率，保证小字清晰
            effective_max_long = max(max_long, 1400)
            mat = fitz.Matrix(2.5, 2.5)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("jpeg")
            compressed = await _compress_image(img_data, effective_max_long, quality)
            pages.append((page_num + 1, compressed, True, text))
        else:
            pages.append((page_num + 1, b"", False, text))
    doc.close()
    return pages

def _docx_to_markdown(data: bytes) -> str:
    """Convert docx XML to Markdown, preserving tables, headings, lists, bold/italic."""
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(data), "r") as z:
        if "word/document.xml" not in z.namelist():
            return ""
        xml_content = z.read("word/document.xml")
    root = ET.fromstring(xml_content)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    def _run_text(r) -> str:
        rpr = r.find(f"{{{ns['w']}}}rPr")
        bold = False
        italic = False
        if rpr is not None:
            bold = rpr.find(f"{{{ns['w']}}}b") is not None
            italic = rpr.find(f"{{{ns['w']}}}i") is not None
        parts = []
        for t in r.iter(f"{{{ns['w']}}}t"):
            if t.text:
                txt = t.text
                if bold:
                    txt = f"**{txt}**"
                if italic:
                    txt = f"*{txt}*"
                parts.append(txt)
        # Check for line break
        if r.find(f"{{{ns['w']}}}br") is not None:
            parts.append("<br>")
        return "".join(parts)

    def _para_text(p) -> str:
        texts = []
        for r in p.iter(f"{{{ns['w']}}}r"):
            texts.append(_run_text(r))
        return "".join(texts)

    # Find all table cells' paragraphs to skip them later
    tbl_pids = set()
    tables_data = []

    for tbl in root.iter(f"{{{ns['w']}}}tbl"):
        grid = []
        for tr in tbl.iter(f"{{{ns['w']}}}tr"):
            row = []
            for tc in tr.iter(f"{{{ns['w']}}}tc"):
                cell_paras = []
                for cp in tc.iter(f"{{{ns['w']}}}p"):
                    tbl_pids.add(id(cp))
                    cell_paras.append(_para_text(cp))
                row.append(" ".join(cell_paras).strip())
            grid.append(row)
        if grid:
            tables_data.append(grid)

    lines = []

    # Render tables in Markdown
    for grid in tables_data:
        if not grid:
            continue
        col_count = max(len(r) for r in grid)
        sep = "| " + " | ".join("---" for _ in range(col_count)) + " |"
        for ri, row in enumerate(grid):
            padded = list(row) + [""] * (col_count - len(row))
            lines.append("| " + " | ".join(padded) + " |")
            if ri == 0:
                lines.append(sep)
        lines.append("")

    # Render paragraphs (skip table-internal ones)
    for p in root.iter(f"{{{ns['w']}}}p"):
        if id(p) in tbl_pids:
            continue
        ppr = p.find(f"{{{ns['w']}}}pPr")
        heading = 0
        list_prefix = ""

        if ppr is not None:
            ps = ppr.find(f"{{{ns['w']}}}pStyle")
            if ps is not None:
                v = ps.get(f"{{{ns['w']}}}val", "")
                for i in range(1, 10):
                    if v == f"Heading{i}":
                        heading = i
                        break
            numPr = ppr.find(f"{{{ns['w']}}}numPr")
            if numPr is not None:
                ilvl = numPr.find(f"{{{ns['w']}}}ilvl")
                level = int(ilvl.get(f"{{{ns['w']}}}val", 0)) if ilvl is not None else 0
                indent = "  " * level
                # Simplified: use bullet for all lists (numbering info is complex to extract)
                list_prefix = f"{indent}- "

        text = _para_text(p)
        if not text.strip() and not heading and not list_prefix:
            lines.append("")
            continue

        if heading:
            lines.append("#" * heading + " " + text)
        elif list_prefix:
            lines.append(list_prefix + text)
        else:
            lines.append(text)

    return "\n".join(lines).strip()

async def _extract_docx_text(data: bytes) -> str:
    try:
        return _docx_to_markdown(data) or ""
    except Exception:
        return ""

async def _extract_pdf_text(data: bytes) -> str:
    try:
        import fitz
        tmp_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{tmp_id}_extract.pdf")
        with open(tmp_path, "wb") as f:
            f.write(data)
        doc = fitz.open(tmp_path)
        parts = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return "\n\n".join(parts).strip()
    except Exception:
        return ""

def _resolve_tag(tag: str, semester: str) -> str:
    """合并考试标签和学期标签。"""
    parts = []
    if tag:
        parts.append(tag)
    if semester:
        parts.append(semester)
    return " / ".join(parts) if parts else "未分类"


@router.post("/classify")
async def classify_upload(
    file: UploadFile = File(...),
    tag: str = Form(""),
    semester: str = Form(""),
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}

    daily_limit = config.get("daily_cost_limit", 10.0)
    if not await check_daily_limit(username, daily_limit):
        raise HTTPException(status_code=429, detail="今日 API 花费已达上限，请明天再试")

    max_size_mb = config.get("image_max_size_mb", 10)
    quality = config.get("image_compress_quality", 40)
    max_long = config.get("image_max_long_edge", 800)
    # 英语文字识别需要更清晰，对过低的配置做保底
    quality = max(int(quality or 40), 50)
    max_long = max(int(max_long or 800), 1200)

    api_key = config.get("deepseek_api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API Key 未配置")

    model_choice = config.get("deepseek_model", "flash")
    model_name = _get_deepseek_model_name(model_choice)
    ds_timeout = max(int(config.get("deepseek_timeout", 120) or 120), 180)
    kimi_timeout = max(int(config.get("kimi_timeout", 120) or 120), 180)

    data = await file.read()
    if len(data) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过 {max_size_mb}MB 限制")

    resolved_tag = _resolve_tag(tag, semester)
    filename = file.filename or "未命名"

    async def event_generator():
        await asyncio.sleep(0.1)

        images = []
        extracted_text = ""
        html_content = ""
        file_id = str(uuid.uuid4())
        ext = ""

        # ---- 阶段1: 解析文件 ----
        yield "data: " + json.dumps({"type": "text", "text": "正在解析文件…\n"}, ensure_ascii=False) + "\n\n"

        if _is_image(data):
            compressed = await _compress_image(data, max_long, quality)
            images.append(compressed)
            ext = ".jpg"
            with open(os.path.join(UPLOAD_DIR, f"{file_id}{ext}"), "wb") as f:
                f.write(compressed)
            yield "data: " + json.dumps({"type": "text", "text": "图片已保存\n"}, ensure_ascii=False) + "\n\n"
        elif _is_pdf(data):
            pages = await _pdf_to_pages(data, file_id, quality, max_long)
            for num, img_bytes, scanned, text in pages:
                if scanned:
                    images.append(img_bytes)
                elif text:
                    extracted_text += f"\n\n--- 第{num}页 ---\n\n{text}"
            ext = ".pdf"
            yield "data: " + json.dumps({"type": "text", "text": "PDF 已解析\n"}, ensure_ascii=False) + "\n\n"
        elif _is_docx(data, filename):
            extracted_text = await _extract_docx_text(data)
            ext = ".docx"
            with open(os.path.join(UPLOAD_DIR, f"{file_id}{ext}"), "wb") as f:
                f.write(data)
            # 用 python-docx 生成高质量的 HTML 和清洁纯文本，供预览和打印
            try:
                html_content = _materials_docx_to_html(data)
                if html_content:
                    html_path = os.path.join(UPLOAD_DIR, f"{file_id}_text.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
            except Exception:
                html_content = None
            yield "data: " + json.dumps({"type": "text", "text": f"Word 文档已提取，共 {len(extracted_text)} 字\n"}, ensure_ascii=False) + "\n\n"
        else:
            yield "data: " + json.dumps({"type": "error", "text": "仅支持 PDF、Word（docx）、JPG、PNG 文件"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        if not images and not extracted_text:
            yield "data: " + json.dumps({"type": "error", "text": "未能从文件中提取到任何内容"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        # 保存文本内容到 _text.txt（清洁纯文本，不含 markdown 标记）
        text_file_path = os.path.join(UPLOAD_DIR, f"{file_id}_text.txt")
        if extracted_text and html_content:
            clean_text = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
            clean_text = re.sub(r'</(p|div|li|tr|h[1-6]|td)>', '\n', clean_text)
            clean_text = re.sub(r'<[^>]+>', '', clean_text)
            clean_text = clean_text.replace('&nbsp;', ' ')
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()
            if clean_text:
                with open(text_file_path, "w", encoding="utf-8") as f:
                    f.write(clean_text)
        elif extracted_text:
            with open(text_file_path, "w", encoding="utf-8") as f:
                f.write(extracted_text)

        # ---- 阶段2: 文字提取（OCR / 纯文本） ----
        ocr_text = ""

        if images:
            # 先尝试 Kimi OCR（需要 Kimi API Key）
            kimi_key = config.get("kimi_api_key", "")
            kimi_model = config.get("kimi_model", "kimi-k2.6")
            kimi_ok = False
            if kimi_key:
                yield "data: " + json.dumps({"type": "text", "text": "正在使用 Kimi 进行OCR识别…\n"}, ensure_ascii=False) + "\n\n"
                kimi_result = await _kimi_ocr(kimi_key, kimi_model, images, kimi_timeout)
                if kimi_result and not kimi_result.startswith("__kimi_"):
                    ocr_text = kimi_result
                    kimi_ok = True
                    yield "data: " + json.dumps({"type": "text", "text": f"Kimi OCR成功，识别 {len(ocr_text)} 字\n"}, ensure_ascii=False) + "\n\n"
                elif kimi_result == "__kimi_timeout__":
                    yield "data: " + json.dumps({"type": "text", "text": "Kimi OCR 超时，尝试本地OCR…\n"}, ensure_ascii=False) + "\n\n"
                elif kimi_result == "__kimi_ratelimit__":
                    yield "data: " + json.dumps({"type": "text", "text": "Kimi OCR 触发限流，尝试本地OCR…\n"}, ensure_ascii=False) + "\n\n"
                elif kimi_result == "__kimi_error__":
                    yield "data: " + json.dumps({"type": "text", "text": "Kimi OCR API 错误，尝试本地OCR…\n"}, ensure_ascii=False) + "\n\n"
            if not kimi_ok:
                yield "data: " + json.dumps({"type": "text", "text": "正在执行本地OCR识别…\n"}, ensure_ascii=False) + "\n\n"
                ocr_text_parts = []
                for img_data in images:
                    ocr_result = await _local_ocr(img_data)
                    if ocr_result:
                        ocr_text_parts.append(ocr_result)
                ocr_text = "\n".join(ocr_text_parts)
                if ocr_text:
                    yield "data: " + json.dumps({"type": "text", "text": f"本地OCR成功，识别 {len(ocr_text)} 字\n"}, ensure_ascii=False) + "\n\n"
                else:
                    yield "data: " + json.dumps({"type": "text", "text": "本地OCR未生效，尝试AI视觉识别…\n"}, ensure_ascii=False) + "\n\n"
                    # 降级：将图片直接传给 DeepSeek（Vision 模式）做识别
                    try:
                        vision_client = create_client(api_key, DEEPSEEK_BASE_URL, ds_timeout)
                        vision_content = []
                        for i, img_data in enumerate(images):
                            b64 = base64.b64encode(img_data).decode("utf-8")
                            vision_content.append({"type": "text", "text": f"[第{i+1}页]"})
                            vision_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                        vision_content.append({"type": "text", "text": "\n请逐页提取以上图片中的所有文字内容，保持原文格式和段落。直接输出文字，不要额外说明。"})
                        vision_resp = await vision_client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": "你是OCR识别助手。提取图片中的全部英文和中文文字，保持原文段落格式。"},
                                {"role": "user", "content": vision_content}
                            ],
                            max_tokens=16384,
                        )
                        vision_text = (vision_resp.choices[0].message.content or "").strip()
                        if vision_text:
                            ocr_text = vision_text
                            yield "data: " + json.dumps({"type": "text", "text": f"AI视觉识别成功，识别 {len(ocr_text)} 字\n"}, ensure_ascii=False) + "\n\n"
                    except Exception as e:
                        yield "data: " + json.dumps({"type": "text", "text": f"AI视觉识别失败: {str(e)[:100]}\n"}, ensure_ascii=False) + "\n\n"

            # 将 OCR 文本写入 _text.txt（追加到已有文本后）
            if ocr_text:
                with open(text_file_path, "a", encoding="utf-8") as f:
                    if extracted_text:
                        f.write("\n\n--- OCR识别内容 ---\n\n")
                    f.write(ocr_text)

        # 检查是否完全没有文本（OCR 和 PDF/Word 提取都失败）
        full_text = ocr_text if ocr_text else extracted_text
        if extracted_text and ocr_text:
            full_text += "\n\n" + extracted_text

        if not full_text or not full_text.strip():
            yield "data: " + json.dumps({"type": "error", "text": "未能从文件中提取到任何文字内容（Kimi OCR、本地OCR和AI视觉识别均失败）。请确认文件内容清晰，或尝试手动输入。"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        # ---- 阶段3: AI 分析（两轮） ----
        yield "data: " + json.dumps({"type": "text", "text": "AI 正在分析文档内容…\n"}, ensure_ascii=False) + "\n\n"

        classification = {"type": "题目", "confidence": 0.5, "reason": "解析失败", "items": [], "summary": "", "suggested_tags": []}

        classify_prompt = """你是一个严格的英语文档分类器。分析文件名和文档内容，按以下优先级规则判断类型。

## 核心原则：文件名规则为主，内容分析为辅
**文件名中的版本标识和关键词是最高优先级信号。如果文件名规则明确，直接按文件名分类；如果文件名规则不够明确，则结合文档内容分析辅助判断。**

---

## 第一优先级：文件名版本标识（明确规则，不可违背）

以下文件名特征具有决定性，看到就直接判定，不需要再看内容：

### → 词单
- **"学生版" + "单词/默写/词组"**：如"学生版 四会单词+词组默写表汇总"
- **"答案版" + "单词/默写/词组"**：如"答案版 E1 单词默写表"
- **"教师版" + "单词/默写/词组"**：如"教师版 E1 U13-U14 单词"
- **"完整词单"**：如"EIM1U1-U14完整词单"

### → 题目
- **"学生版"**（不含"单词/默写/词组"时）：如"学生版 单选基础练习"、"学生版 阅读强化练习"
- **"考题汇总"**：如"学生版 考点&考题汇总"
- **"练习"**（无"答案/教师版/答案来源版"前缀）：如"6.4 阅读强化练习"
- **"默写表"**（无版本标识时，需结合内容判断）

### → 答案
- **"答案"**开头（不含"单词/默写/词组"时）：如"答案 6.11 课前测"
- **"答案来源版"**（不含"单词/默写/词组"时）：如"答案来源版 单句变形填空"
- **"批改和讲解"**：如"课后作业答案 批改和讲解"
- **"教师版"**（不含"单词/默写/词组"时）：如"教师版 2025南外初一期末单选考点&考题汇总"

### → 资料
- **"词单语言点"**：如"E1 U13 词单语言点"——这是语法讲解资料，不是词单
- **"课后知识梳理"**：如"6.4 课后知识梳理"
- **"课文考点"**：如"期末 E1 U12-U13 课文考点"
- **"考点清单"**（无"学生版"前缀）：如"月考2 单选考点清单"
- **"知识点"**：如"期末动词变形部分知识点"
- **"知识梳理"**：如"现在完成时 知识梳理"

---

## 第二优先级：文件名规则不够明确时，结合内容分析

如果文件名没有以上明确标识，则需要分析文档内容来判断类型。

### 内容分析"题目"的特征
- 学生用练习，有明显作答空位（横线、空格、括号待填）
- 有选择题（A/B/C/D选项）、填空题、判断题、连线题
- 有阅读理解（文章+问题）
- 有课前测、单元测、试卷
- 有中文释义 → ______（填写英文单词）的格式，但**包含完整句子**，不是纯单词列表
- 内容中有大量空白横线等待学生填写

### 内容分析"答案"的特征
- 已填好答案、供核对用的文档
- 题目后面跟着明确答案（如"答案：B"、"答案：goes"）
- 句子/段落层面的完整解答，不是纯单词对照
- 有解析、讲解、批改说明
- 内容比题目更完整，没有空白横线

### 内容分析"词单"的特征
- 纯单词/词组 + 中文释义的对照表
- 只有单词级别，没有完整句子或阅读理解
- 格式：英文 → 中文 或 中文 → 英文（填空但仅单词级别）
- 可能含音标、词性标注
- **没有语法讲解、没有变形规则、没有例句搭配**——如果有这些，就是资料不是词单

### 内容分析"资料"的特征
- 纯知识点归纳、语法讲解、时态总结、课文原文+重点标注
- 有词汇变形规则、例句搭配、固定用法说明
- 课堂笔记、考点清单（纯考点列表，无考题）
- 词单语言点（语法规则+词汇变形+例句搭配，教学参考）
- 侧重"讲解"和"归纳"，不是让学生做题

---

## 第三优先级：内容分析与文件名冲突时的处理

如果文件名规则和内容分析结果**不一致**，按以下规则处理：

1. 文件名含明确版本标识（学生版/答案版/教师版/答案来源版）→ **以文件名规则为准**
2. 文件名含明确关键词（完整词单/词单语言点/课后知识梳理/课文考点/知识梳理/知识点）→ **以文件名规则为准**
3. 文件名无明确标识，仅靠"练习/考题"等模糊词 → **以内容分析为准**
4. 文件名含"默写表"但无版本标识 → **结合内容判断**：纯单词对照=词单，有语法讲解=资料

---

## 易混淆场景速查表

| 文件名 | 内容特点 | 正确分类 | 判断逻辑 |
|---|---|---|---|
| 学生版 E1 U13-U14 单词 | 中文→英文填空（纯单词） | **词单** | 学生版+单词=词单 |
| 学生版 单选基础练习 | 选择题（有选项） | **题目** | 学生版+练习=题目 |
| 学生版 考点&考题汇总 | 含考题的练习 | **题目** | 学生版+考题=题目 |
| 6.4 阅读强化练习 | 阅读理解练习 | **题目** | "练习"+无版本标识=题目 |
| E1 U13 词单语言点 | 语法讲解+变形规则+例句 | **资料** | "词单语言点"=资料，不是词单 |
| 南外初一下 月考2 单选考点清单 | 纯考点列表，无考题 | **资料** | "考点清单"+无学生版=资料 |
| 答案 6.4阅读强化练习 | 已填答案的练习 | **答案** | "答案"前缀=答案 |
| 教师版 2025南外初一期末单选考点&考题汇总 | 含答案的汇总 | **答案** | 教师版+考题汇总=答案 |
| 课后作业答案 批改和讲解 | 含批改和讲解 | **答案** | "批改和讲解"=答案 |
| 完整词单 | 纯英中对照+音标例句 | **词单** | "完整词单"=词单 |

---

## 最终检查（输出前必须执行）
逐条确认，如果触发则直接输出对应类型：
1. 文件名含"学生版"+"单词/默写/词组" → 词单
2. 文件名含"答案版"+"单词/默写/词组" → 词单
3. 文件名含"词单语言点" → 资料（不是词单）
4. 文件名含"考点清单"且无"学生版" → 资料
5. 文件名含"考题汇总" → 题目
6. 文件名含"练习"且无"答案/教师版/答案来源版" → 题目
7. 文件名含"批改和讲解" → 答案
8. 文件名含"教师版"且不含"单词/默写/词组" → 答案
9. 文件名含"完整词单" → 词单

## 输出格式
{"type": "题目/答案/资料/词单", "confidence": 0.0-1.0, "reason": "判断依据（说明是根据文件名规则还是内容分析）", "summary": "...", "suggested_tags": [], "items": []}
只输出JSON，不要额外文字。"""

        extract_prompt = EXTRACT_PROMPT

        answer_extract_prompt = ANSWER_EXTRACT_PROMPT

        word_extract_prompt = WORD_EXTRACT_PROMPT

        try:
            client = create_client(api_key, DEEPSEEK_BASE_URL, ds_timeout)

            # 第一轮：分类（用前6000字快速判断）
            classify_text = (full_text or "")[:6000]
            if classify_text:
                yield "data: " + json.dumps({"type": "ai_token", "text": "正在分析文档类型...\n"}, ensure_ascii=False) + "\n\n"
                resp = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "直接判断类型输出JSON，不要思考不要解释。"},
                        {"role": "user", "content": f"文件名：{filename}\n\n{classify_prompt}\n\n---\n{classify_text}"}
                    ],
                    temperature=0.1, max_tokens=1024,
                    timeout=ds_timeout,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                text_output = resp.choices[0].message.content or ""
                cleaned = text_output.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                if cleaned.endswith("```"):
                    cleaned = re.sub(r'\s*```$', '', cleaned)
                text_output = cleaned.strip()
                try:
                    classification = json.loads(text_output)
                    yield "data: " + json.dumps({"type": "ai_token", "text": f"分类结果：{classification.get('type','?')}（置信度 {round(classification.get('confidence',0)*100)}%）\n"}, ensure_ascii=False) + "\n\n"
                except json.JSONDecodeError:
                    yield "data: " + json.dumps({"type": "error", "text": "AI返回格式无法解析，分类失败"}, ensure_ascii=False) + "\n\n"
                    yield "data: [DONE]\n\n"
                    return

            doc_type = classification.get("type", "题目")
            if doc_type == "词单" and full_text:
                is_student = bool(re.search(r'学生版', filename))
                label_student = "学生版词单，提取模板（英文留空）\n" if is_student else "正在提取单词列表...\n"
                yield "data: " + json.dumps({"type": "ai_token", "text": label_student}, ensure_ascii=False) + "\n\n"
                word_text = full_text[:12000]
                max_out = 8192 if model_choice == "flash" else 16384
                stream = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "直接提取单词输出JSON，不要思考不要解释。"},
                        {"role": "user", "content": f"文件名：{filename}\n\n{word_extract_prompt}\n\n---\n{word_text}"}
                    ],
                    temperature=0.1, max_tokens=max_out,
                    timeout=ds_timeout,
                    stream=True,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                collected = []
                token_count = 0
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        collected.append(delta.content)
                        token_count += 1
                        if token_count % 30 == 0:
                            yield "data: " + json.dumps({"type": "ai_token", "text": f"⏳ 处理中（已收集 {token_count} 个片段）\n"}, ensure_ascii=False) + "\n\n"
                yield "data: " + json.dumps({"type": "ai_token", "text": "解析结果...\n"}, ensure_ascii=False) + "\n\n"
                raw = "".join(collected)
                words = _extract_words_fallback(raw, word_text)
                if words:
                    classification["words"] = words
                    for w in words[:20]:
                        en = w.get("english", "")
                        cn = w.get("chinese", "")
                        pos = w.get("pos", "")
                        label = f"{cn} [{pos}] → {en}" if pos else f"{cn} → {en}"
                        yield "data: " + json.dumps({"type": "ai_token", "text": f"{label}\n"}, ensure_ascii=False) + "\n\n"
                    if len(words) > 20:
                        yield "data: " + json.dumps({"type": "ai_token", "text": f"... 等共 {len(words)} 个单词\n"}, ensure_ascii=False) + "\n\n"
                    yield "data: " + json.dumps({"type": "ai_token", "text": f"✅ 共提取 {len(words)} 个单词\n"}, ensure_ascii=False) + "\n\n"
                else:
                    yield "data: " + json.dumps({"type": "ai_token", "text": "⚠ 单词格式解析失败，保存为空词单\n"}, ensure_ascii=False) + "\n\n"
                    classification["words"] = "__skip__"
            elif doc_type in ("题目", "答案") and full_text:
                yield "data: " + json.dumps({"type": "ai_token", "text": f"正在逐条提取{doc_type}...\n"}, ensure_ascii=False) + "\n\n"
                chosen_prompt = answer_extract_prompt if doc_type == "答案" else extract_prompt
                if doc_type == "答案":
                    max_out = 12288 if model_choice == "flash" else 24576
                else:
                    max_out = 8192 if model_choice == "flash" else 16384

                all_items = []
                chunks = _chunk_text_for_extraction(full_text, 11000, 300)
                for chunk_idx, chunk_text in enumerate(chunks):
                    if len(chunks) > 1:
                        yield "data: " + json.dumps({"type": "ai_token", "text": f"处理文档片段 {chunk_idx + 1}/{len(chunks)}...\n"}, ensure_ascii=False) + "\n\n"
                    stream2 = await client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": f"直接逐条提取输出JSON，不要思考不要解释。"},
                            {"role": "user", "content": f"文件名：{filename}\n\n{chosen_prompt}\n\n---\n{chunk_text}"}
                        ],
                        temperature=0.2, max_tokens=max_out,
                        timeout=ds_timeout,
                        stream=True,
                        extra_body={"thinking": {"type": "disabled"}},
                    )
                    collected2 = []
                    token_count = 0
                    async for chunk2 in stream2:
                        delta2 = chunk2.choices[0].delta if chunk2.choices else None
                        if delta2 and delta2.content:
                            collected2.append(delta2.content)
                            token_count += 1
                            if token_count % 30 == 0:
                                yield "data: " + json.dumps({"type": "ai_token", "text": f"⏳ 处理中（已收集 {token_count} 个片段）\n"}, ensure_ascii=False) + "\n\n"
                    yield "data: " + json.dumps({"type": "ai_token", "text": "解析结果...\n"}, ensure_ascii=False) + "\n\n"
                    text_output2 = "".join(collected2)
                    extracted = _safe_extract_json(text_output2)
                    if extracted:
                        chunk_items = extracted.get("items", [])
                        for item in chunk_items:
                            content = (item.get("content") or item.get("c") or "").strip()
                            if content:
                                content = _normalize_choice_options(content)
                                all_items.append({"content": content})
                                if len(all_items) <= 10:
                                    yield "data: " + json.dumps({"type": "ai_token", "text": content + "\n"}, ensure_ascii=False) + "\n\n"

                # 兜底：AI 完全未提取到条目时，才使用规则保守拆分
                if not all_items:
                    yield "data: " + json.dumps({"type": "text", "text": "AI 提取未返回有效条目，启用规则兜底拆分...\n"}, ensure_ascii=False) + "\n\n"
                    all_items = _split_items_by_rules(full_text, doc_type)

                classification["items"] = all_items
                yield "data: " + json.dumps({"type": "ai_token", "text": f"\n共提取 {len(all_items)} 条\n"}, ensure_ascii=False) + "\n\n"
                if not all_items:
                    yield "data: " + json.dumps({"type": "error", "text": "✗ 未能提取到任何条目"}, ensure_ascii=False) + "\n\n"
                    yield "data: [DONE]\n\n"
                    return
        except APITimeoutError:
            yield "data: " + json.dumps({"type": "error", "text": "DeepSeek请求超时，请检查网络或增大超时设置"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return
        except RateLimitError:
            yield "data: " + json.dumps({"type": "error", "text": "请求过于频繁，请稍后重试"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return
        except (APIConnectionError, APIStatusError) as e:
            detail = str(e)[:100]
            yield "data: " + json.dumps({"type": "error", "text": f"DeepSeek API 错误: {detail}"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return
        except Exception as e:
            detail = str(e)[:100]
            yield "data: " + json.dumps({"type": "error", "text": f"AI分析异常: {detail}"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        doc_type = classification.get("type", "题目")
        confidence = classification.get("confidence", 0)
        reason = classification.get("reason", "")
        summary = classification.get("summary", "")
        suggested_tags = classification.get("suggested_tags", [])
        items = classification.get("items", [])

        subject = await get_user_subject(username)
        now = datetime.now().isoformat()

        # ---- 阶段4: 存储 ----
        yield "data: " + json.dumps({
            "type": "text",
            "text": f"AI判断类型：{doc_type}（置信度 {round(confidence * 100)}%）\n"
                   f"摘要：{summary}\n"
                   f"建议标签：{', '.join(suggested_tags) if suggested_tags else '无'}\n"
                   f"原因：{reason}\n正在保存…\n"
        }, ensure_ascii=False) + "\n\n"

        effective_tag = resolved_tag
        if not tag and suggested_tags:
            effective_tag = suggested_tags[0]

        if doc_type == "题目":
            counts = [0, 0]  # [count, skip_count]
            def _save_problems(problems):
                existing = {_dedup_key(p.get("content", "")) for p in problems if p.get("content")}
                for item in items:
                    content = item.get("content", "").strip()
                    if not content:
                        continue
                    key = _dedup_key(content)
                    if key and key in existing:
                        counts[1] += 1
                        continue
                    problems.append({
                        "id": str(uuid.uuid4())[:8], "subject": subject,
                        "exam": resolved_tag or "", "source": "", "school": "",
                        "big_question": "", "small_question": "",
                        "content": content, "image_file_id": "",
                        "knowledge_point": "", "is_wrong": False,
                        "is_shared": False, "created_at": now,
                        "solved_at": None, "solution": "", "session_id": "",
                        "parent_id": "", "is_big_question": False,
                        "filename": filename, "source_file": filename,
                        "upload_file_id": file_id,
                        "file_type": ext.lstrip(".") if ext else "docx",
                    })
                    if key:
                        existing.add(key)
                    counts[0] += 1
            await update_json(get_problems_path(username, subject), _save_problems)
            await update_json(get_materials_path(username, subject), lambda materials: _upsert_material(materials, file_id, filename, ext, data, extracted_text, ocr_text, effective_tag, subject, now))
            msg = f"已保存 {counts[0]} 道题目到题库"
            if counts[1]:
                msg += f"（{counts[1]} 道重复已跳过）"
            yield "data: " + json.dumps({"type": "text", "text": msg + "\n"}, ensure_ascii=False) + "\n\n"
        elif doc_type == "词单":
            words_flag = classification.get("words", [])
            is_skip = (words_flag == "__skip__")
            words = [] if is_skip else (words_flag if isinstance(words_flag, list) else [])
            word_count = len(words)
            is_student = bool(re.search(r'学生版', filename))
            saved = [False]
            def _save_words(all_words):
                existing_fnames = {w.get("filename", "") for w in all_words if w.get("filename")}
                if filename in existing_fnames:
                    return
                all_words.append({
                    "id": file_id, "filename": filename or f"未命名{ext}",
                    "tag": resolved_tag or "未分类",
                    "source_file": filename,
                    "upload_file_id": file_id,
                    "file_type": ext.lstrip(".") if ext else "docx",
                    "words": words,
                    "word_count": word_count,
                    "is_student": is_student,
                    "created_at": now,
                })
                saved[0] = True
            await update_json(get_words_path(username, subject), _save_words)
            if saved[0]:
                await update_json(get_materials_path(username, subject), lambda materials: _upsert_material(materials, file_id, filename, ext, data, extracted_text, ocr_text, effective_tag, subject, now))
                label = "学生版词单" if is_student else f"词单，共 {word_count} 个单词"
                yield "data: " + json.dumps({"type": "text", "text": f"已保存{label}\n"}, ensure_ascii=False) + "\n\n"
            else:
                yield "data: " + json.dumps({"type": "text", "text": f"文件「{filename}」已存在，跳过保存\n"}, ensure_ascii=False) + "\n\n"
        elif doc_type == "答案":
            counts = [0, 0]  # [count, skip_count]
            def _save_answers(answers):
                existing = {_dedup_key(a.get("content", "")) for a in answers if a.get("content")}
                for item in items:
                    content = item.get("content", "").strip()
                    if not content:
                        continue
                    key = _dedup_key(content)
                    if key and key in existing:
                        counts[1] += 1
                        continue
                    answers.append({
                        "id": str(uuid.uuid4())[:8], "tag": resolved_tag or "未分类",
                        "content": content, "answer": item.get("answer", ""),
                        "created_at": now, "filename": filename, "source_file": filename,
                        "upload_file_id": file_id,
                        "file_type": ext.lstrip(".") if ext else "docx",
                    })
                    if key:
                        existing.add(key)
                    counts[0] += 1
            await update_json(get_answers_path(username, subject), _save_answers)
            await update_json(get_materials_path(username, subject), lambda materials: _upsert_material(materials, file_id, filename, ext, data, extracted_text, ocr_text, effective_tag, subject, now))
            msg = f"已保存 {counts[0]} 条答案"
            if counts[1]:
                msg += f"（{counts[1]} 条重复已跳过）"
            yield "data: " + json.dumps({"type": "text", "text": msg + "\n"}, ensure_ascii=False) + "\n\n"
        else:
            saved = [False]
            def _save_material(materials):
                existing = {m.get("filename", "") for m in materials if m.get("filename")}
                if filename in existing:
                    return
                materials.append({
                    "id": file_id, "filename": filename or f"未命名{ext}",
                    "subject": subject, "time": effective_tag or "未分类",
                    "tag": effective_tag or "未分类",
                    "summary": summary,
                    "file_path": os.path.join(UPLOAD_DIR, f"{file_id}{ext}"),
                    "file_type": ext.lstrip("."), "file_size": len(data),
                    "has_text": bool(extracted_text) or bool(ocr_text),
                    "created_at": now,
                })
                saved[0] = True
            await update_json(get_materials_path(username, subject), _save_material)
            if saved[0]:
                yield "data: " + json.dumps({"type": "text", "text": "已保存为复习资料\n"}, ensure_ascii=False) + "\n\n"
            else:
                yield "data: " + json.dumps({"type": "text", "text": f"文件「{filename}」已存在，跳过保存\n"}, ensure_ascii=False) + "\n\n"

        raw_words = classification.get("words", [])
        word_count = len(raw_words) if isinstance(raw_words, list) else 0
        result_count = word_count if doc_type == "词单" else len(items)

        # Rough cost estimation for daily limit tracking.
        try:
            pk = _pricing_key("deepseek", model_name)
            est_in = max(1, int(len(full_text or "") * 0.35))
            output_text = json.dumps(classification, ensure_ascii=False) + json.dumps(items, ensure_ascii=False)
            est_out = max(1, int(len(output_text) * 0.35))
            cost = compute_cost(pk, 0, est_in, est_out, get_pricing(config)) or 0
            await add_daily_cost(username, cost)
        except Exception:
            pass

        # 后台预转换 docx → PDF（不阻塞上传响应）
        if ext == ".docx" and not classification.get("_pdf_converted"):
            try:
                from app.utils.doc_converter import convert_docx_to_pdf
                asyncio.ensure_future(convert_docx_to_pdf(
                    os.path.join(UPLOAD_DIR, f"{file_id}{ext}"),
                    UPLOAD_DIR,
                ))
            except Exception:
                pass

        yield "data: " + json.dumps({
            "type": "result", "doc_type": doc_type, "confidence": confidence,
            "reason": reason, "tag": effective_tag or resolved_tag or "未分类",
            "count": result_count, "word_count": word_count, "summary": summary,
        }, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/answers")
async def list_answers(
    tag: Optional[str] = None,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    answers = await read_json(get_answers_path(username, subject)) or []
    if tag:
        answers = [a for a in answers if a.get("tag") == tag]
    return {"items": answers}

@router.get("/answers/tags")
async def get_answer_tags(
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    answers = await read_json(get_answers_path(username, subject)) or []
    tags = sorted(set(a.get("tag", "") for a in answers if a.get("tag")))
    return {"tags": tags}

class BatchDeleteAnswersRequest(BaseModel):
    ids: list[str] = []


@router.post("/answers/batch-delete")
async def batch_delete_answers(
    req: BatchDeleteAnswersRequest,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    answers = await read_json(get_answers_path(username, subject)) or []
    ids_set = set(req.ids)
    kept = []
    trashed = []
    for a in answers:
        if a["id"] in ids_set:
            a["trashed_at"] = datetime.now().isoformat()
            a["_origin_type"] = "answer"
            trashed.append(a)
        else:
            kept.append(a)
    await write_json(get_answers_path(username, subject), kept)
    trash = await read_json(get_library_trash_path(username, subject)) or []
    trash.extend(trashed)
    await write_json(get_library_trash_path(username, subject), trash)
    await cleanup_matches_after_deletion(username, subject)
    return {"message": f"已移入废纸篓 {len(trashed)} 条答案", "deleted": len(trashed)}


@router.delete("/answers/{answer_id}")
async def delete_answer(
    answer_id: str,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    answers = await read_json(get_answers_path(username, subject)) or []
    target = None
    for a in answers:
        if a["id"] == answer_id:
            target = a
            break
    if not target:
        raise HTTPException(status_code=404, detail="答案不存在")
    new_answers = [a for a in answers if a["id"] != answer_id]
    await write_json(get_answers_path(username, subject), new_answers)
    target["trashed_at"] = datetime.now().isoformat()
    target["_origin_type"] = "answer"
    trash = await read_json(get_library_trash_path(username, subject)) or []
    trash.append(target)
    await write_json(get_library_trash_path(username, subject), trash)
    await cleanup_matches_after_deletion(username, subject)
    return {"message": "已移入废纸篓"}


@router.get("/words")
async def list_words(
    tag: Optional[str] = None,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    words_list = await read_json(get_words_path(username, subject)) or []
    if tag:
        words_list = [w for w in words_list if w.get("tag") == tag]
    return {"items": words_list}

@router.get("/words/tags")
async def get_word_tags(
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    words_list = await read_json(get_words_path(username, subject)) or []
    tags = sorted(set(w.get("tag", "") for w in words_list if w.get("tag")))
    return {"tags": tags}

# ========== 以下路由为重新实现（原备份缺失）==========

@router.put("/words/{word_id}/words")
async def update_word_items(
    word_id: str,
    data: dict,
    username: str = Depends(get_current_user),
):
    words = data.get("words", [])
    if not isinstance(words, list):
        raise HTTPException(status_code=400, detail="words must be a list")
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    for wl in word_lists:
        if wl["id"] == word_id:
            wl["words"] = words
            wl["word_count"] = len(words)
            await write_json(get_words_path(username, subject), word_lists)
            return {"words": words, "word_count": len(words)}
    raise HTTPException(status_code=404, detail="词单不存在")

@router.put("/words/{word_id}/words/{word_idx}")
async def update_single_word(
    word_id: str,
    word_idx: int,
    data: dict,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    for wl in word_lists:
        if wl["id"] == word_id:
            words = wl.get("words", [])
            if word_idx < 0 or word_idx >= len(words):
                raise HTTPException(status_code=404, detail="单词索引超出范围")
            if "english" in data:
                words[word_idx]["english"] = data["english"]
            if "pos" in data:
                words[word_idx]["pos"] = data["pos"]
            if "chinese" in data:
                words[word_idx]["chinese"] = data["chinese"]
            await write_json(get_words_path(username, subject), word_lists)
            return words[word_idx]
    raise HTTPException(status_code=404, detail="词单不存在")

@router.delete("/words/{word_id}/words/{word_idx}")
async def delete_single_word(
    word_id: str,
    word_idx: int,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    for wl in word_lists:
        if wl["id"] == word_id:
            words = wl.get("words", [])
            if word_idx < 0 or word_idx >= len(words):
                raise HTTPException(status_code=404, detail="单词索引超出范围")
            removed = words.pop(word_idx)
            wl["word_count"] = len(words)
            await write_json(get_words_path(username, subject), word_lists)
            return {"removed": removed, "word_count": len(words)}
    raise HTTPException(status_code=404, detail="词单不存在")

@router.post("/words/{word_id}/words")
async def add_single_word(
    word_id: str,
    data: dict,
    username: str = Depends(get_current_user),
):
    english = data.get("english", "")
    chinese = data.get("chinese", "")
    pos = data.get("pos", "")
    if not english:
        raise HTTPException(status_code=400, detail="需要提供 english")
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    for wl in word_lists:
        if wl["id"] == word_id:
            words = wl.get("words", [])
            new_word = {"english": english, "pos": pos, "chinese": chinese}
            words.append(new_word)
            wl["word_count"] = len(words)
            await write_json(get_words_path(username, subject), word_lists)
            return new_word
    raise HTTPException(status_code=404, detail="词单不存在")

@router.delete("/words/{word_id}")
async def delete_word_list(
    word_id: str,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    words_list = await read_json(get_words_path(username, subject)) or []
    target = None
    for w in words_list:
        if w["id"] == word_id:
            target = w
            break
    if not target:
        raise HTTPException(status_code=404, detail="词单不存在")
    new_list = [w for w in words_list if w["id"] != word_id]
    await write_json(get_words_path(username, subject), new_list)
    target["trashed_at"] = datetime.now().isoformat()
    target["_origin_type"] = "word"
    trash = await read_json(get_library_trash_path(username, subject)) or []
    trash.append(target)
    await write_json(get_library_trash_path(username, subject), trash)
    return {"message": "已移入废纸篓"}

@router.put("/answers/{answer_id}")
async def update_answer(
    answer_id: str,
    data: dict,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    answers = await read_json(get_answers_path(username, subject)) or []
    for a in answers:
        if a["id"] == answer_id:
            for field in ("content", "tag", "answer"):
                if field in data:
                    a[field] = data[field]
            await write_json(get_answers_path(username, subject), answers)
            return a
    raise HTTPException(status_code=404, detail="答案不存在")

@router.put("/words/{word_id}")
async def update_word_list(
    word_id: str,
    data: dict,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    for wl in word_lists:
        if wl["id"] == word_id:
            for field in ("filename", "tag"):
                if field in data:
                    wl[field] = data[field]
            await write_json(get_words_path(username, subject), word_lists)
            return wl
    raise HTTPException(status_code=404, detail="词单不存在")


@router.post("/adjust-type")
async def adjust_document_type(
    data: dict,
    username: str = Depends(get_current_user),
):
    source_file = data.get("source_file", "")
    current_type = data.get("current_type", "")
    new_type = data.get("new_type", "")
    file_id = data.get("file_id", "")
    filename = data.get("filename", "") or source_file
    tag = data.get("tag", "")
    semester = data.get("semester", "")

    if not source_file or not current_type or not new_type:
        raise HTTPException(status_code=400, detail="参数不完整")
    if current_type == new_type:
        raise HTTPException(status_code=400, detail="类型相同无需调整")

    subject = await get_user_subject(username)
    now = datetime.now().isoformat()
    resolved_tag = _resolve_tag(tag, semester)

    config = await read_json(get_user_config_path(username)) or {}
    model_choice = config.get("deepseek_model", "flash")
    model_name = _get_deepseek_model_name(model_choice)
    api_key = config.get("deepseek_api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API Key 未配置")
    timeout = max(int(config.get("deepseek_timeout", 60) or 60), 180)

    def _collect_by_source(items, source_key="source_file", filename_key="filename"):
        found = []
        kept = []
        for item in items:
            sf = item.get(source_key) or item.get(filename_key, "")
            if sf == source_file:
                found.append(item)
            else:
                kept.append(item)
        return found, kept

    # Read text file for re-extraction
    full_text = ""
    if file_id:
        text_path = os.path.join(UPLOAD_DIR, f"{file_id}_text.txt")
        if os.path.exists(text_path):
            with open(text_path, "r", encoding="utf-8") as f:
                full_text = f.read()

    extract_prompt = EXTRACT_PROMPT

    answer_extract_prompt = ANSWER_EXTRACT_PROMPT

    word_extract_prompt = WORD_EXTRACT_PROMPT

    async def event_generator():
        yield "data: " + json.dumps({"type": "text", "text": f"正在从「{current_type}」调整为「{new_type}」...\n"}, ensure_ascii=False) + "\n\n"

        # ---- 1. 从当前类型中删除 ----
        found = []
        if current_type == "题目":
            old_items = await read_json(get_problems_path(username, subject)) or []
            found, kept = _collect_by_source(old_items)
            if found:
                await write_json(get_problems_path(username, subject), kept)
                await cleanup_matches_after_deletion(username, subject)
                yield "data: " + json.dumps({"type": "text", "text": f"已删除 {len(found)} 道题目\n"}, ensure_ascii=False) + "\n\n"
        elif current_type == "答案":
            old_items = await read_json(get_answers_path(username, subject)) or []
            found, kept = _collect_by_source(old_items)
            if found:
                await write_json(get_answers_path(username, subject), kept)
                await cleanup_matches_after_deletion(username, subject)
                yield "data: " + json.dumps({"type": "text", "text": f"已删除 {len(found)} 条答案\n"}, ensure_ascii=False) + "\n\n"
        elif current_type == "词单":
            old_items = await read_json(get_words_path(username, subject)) or []
            found, kept = _collect_by_source(old_items, "source_file", "filename")
            if found:
                await write_json(get_words_path(username, subject), kept)
                yield "data: " + json.dumps({"type": "text", "text": f"已删除 {len(found)} 个词单\n"}, ensure_ascii=False) + "\n\n"
        elif current_type == "资料":
            old_items = await read_json(get_materials_path(username, subject)) or []
            found, kept = _collect_by_source(old_items)
            if found:
                await write_json(get_materials_path(username, subject), kept)
                yield "data: " + json.dumps({"type": "text", "text": f"已删除 {len(found)} 条资料\n"}, ensure_ascii=False) + "\n\n"

        # ---- 2. 按新类型保存 ----
        if new_type == "资料":
            materials = await read_json(get_materials_path(username, subject)) or []
            existing_fnames = {m.get("filename", "") for m in materials if m.get("filename")}
            moved_count = 0
            for item in found:
                fname = item.get("filename", "")
                if fname in existing_fnames:
                    continue
                file_id_from_item = item.get("upload_file_id", "") or item.get("id", str(uuid.uuid4())[:8])
                if current_type in ("题目", "答案"):
                    summary = (item.get("content", "") or "")[:100]
                    item_tag = item.get("tag", "未分类") if current_type == "答案" else item.get("exam", "未分类")
                elif current_type == "词单":
                    summary = f"词单 {item.get('word_count', 0)} 词"
                    item_tag = item.get("tag", "未分类")
                else:
                    summary = item.get("summary", "") or item.get("filename", "")
                    item_tag = item.get("tag", "未分类")
                # 根据 uploads 目录中的实际文件确定路径/类型/大小
                actual_ext = ".docx"
                actual_path = ""
                actual_size = 0
                for try_ext in (".docx", ".pdf", ".jpg", ".jpeg", ".png"):
                    candidate = os.path.join(UPLOAD_DIR, f"{file_id_from_item}{try_ext}")
                    if os.path.exists(candidate):
                        actual_ext = try_ext
                        actual_path = f"data/uploads/{file_id_from_item}{try_ext}"
                        actual_size = os.path.getsize(candidate)
                        break
                text_path = os.path.join(UPLOAD_DIR, f"{file_id_from_item}_text.txt")
                has_text = os.path.exists(text_path) and os.path.getsize(text_path) > 0
                materials.append({
                    "id": file_id_from_item,
                    "filename": fname or "未命名",
                    "subject": subject,
                    "time": item_tag,
                    "tag": item_tag,
                    "summary": summary,
                    "file_path": actual_path,
                    "file_type": actual_ext.lstrip("."),
                    "file_size": actual_size,
                    "has_text": has_text,
                    "created_at": now,
                })
                existing_fnames.add(fname)
                moved_count += 1
            await write_json(get_materials_path(username, subject), materials)
            yield "data: " + json.dumps({"type": "result", "message": f"已将 {moved_count} 条从「{current_type}」调整为「资料」", "count": moved_count, "type": "资料"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        # 新类型为 题目/答案/词单 时，需要 AI 重新提取
        if not full_text:
            yield "data: " + json.dumps({"type": "error", "text": "未找到文件文本内容，无法重新提取。请确保文件已上传且有 _text.txt。"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        client = create_client(api_key, DEEPSEEK_BASE_URL, timeout)

        if new_type == "词单":
            is_student = bool(re.search(r'学生版', filename))
            label_student = "学生版词单，提取模板（英文留空）\n" if is_student else "正在重新提取单词列表...\n"
            yield "data: " + json.dumps({"type": "ai_token", "text": label_student}, ensure_ascii=False) + "\n\n"
            word_text = full_text[:12000]
            max_out = 8192 if model_choice == "flash" else 16384
            stream = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "直接提取单词输出JSON，不要思考不要解释。"},
                    {"role": "user", "content": f"文件名：{filename}\n\n{word_extract_prompt}\n\n---\n{word_text}"}
                ],
                temperature=0.1, max_tokens=max_out,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}},
            )
            collected = []
            token_count = 0
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected.append(delta.content)
                    token_count += 1
                    if token_count % 30 == 0:
                        yield "data: " + json.dumps({"type": "ai_token", "text": f"⏳ 处理中（已收集 {token_count} 个片段）\n"}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"type": "ai_token", "text": "解析结果...\n"}, ensure_ascii=False) + "\n\n"
            raw = "".join(collected)
            words = _extract_words_fallback(raw, word_text)
            if words:
                for w in words[:20]:
                    en = w.get("english", "")
                    cn = w.get("chinese", "")
                    pos = w.get("pos", "")
                    label = f"{cn} [{pos}] → {en}" if pos else f"{cn} → {en}"
                    yield "data: " + json.dumps({"type": "ai_token", "text": f"{label}\n"}, ensure_ascii=False) + "\n\n"
                if len(words) > 20:
                    yield "data: " + json.dumps({"type": "ai_token", "text": f"... 等共 {len(words)} 个单词\n"}, ensure_ascii=False) + "\n\n"
                yield "data: " + json.dumps({"type": "ai_token", "text": f"✅ 共提取 {len(words)} 个单词\n"}, ensure_ascii=False) + "\n\n"
            else:
                yield "data: " + json.dumps({"type": "error", "text": "⚠ 单词格式解析失败\n"}, ensure_ascii=False) + "\n\n"
            word_count = len(words)

            file_id_new = str(uuid.uuid4())[:8]
            word_lists = await read_json(get_words_path(username, subject)) or []
            word_lists.append({
                "id": file_id_new, "filename": filename,
                "tag": resolved_tag or "未分类",
                "source_file": filename, "upload_file_id": file_id_new,
                "words": words,
                "word_count": word_count,
                "is_student": is_student,
                "created_at": now,
            })
            await write_json(get_words_path(username, subject), word_lists)
            yield "data: " + json.dumps({"type": "result", "message": f"已保存词单，共 {word_count} 个单词", "count": word_count, "type": "词单", "word_count": word_count}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        # 题目 或 答案
        chosen_prompt = answer_extract_prompt if new_type == "答案" else extract_prompt
        max_out = 12288 if model_choice == "flash" else 24576

        yield "data: " + json.dumps({"type": "ai_token", "text": f"正在重新提取{new_type}...\n"}, ensure_ascii=False) + "\n\n"

        all_items = []
        chunks = _chunk_text_for_extraction(full_text, 11000, 300)
        for chunk_idx, chunk_text in enumerate(chunks):
            if len(chunks) > 1:
                yield "data: " + json.dumps({"type": "ai_token", "text": f"处理文档片段 {chunk_idx + 1}/{len(chunks)}...\n"}, ensure_ascii=False) + "\n\n"
            stream = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "直接逐条提取输出JSON，不要思考不要解释。"},
                    {"role": "user", "content": f"文件名：{filename}\n\n{chosen_prompt}\n\n---\n{chunk_text}"}
                ],
                temperature=0.2, max_tokens=max_out,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}},
            )
            collected = []
            token_count = 0
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected.append(delta.content)
                    token_count += 1
                    if token_count % 30 == 0:
                        yield "data: " + json.dumps({"type": "ai_token", "text": f"⏳ 处理中（已收集 {token_count} 个片段）\n"}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"type": "ai_token", "text": "解析结果...\n"}, ensure_ascii=False) + "\n\n"
            raw = "".join(collected)
            extracted = _safe_extract_json(raw)
            if extracted:
                chunk_items = extracted.get("items", [])
                for item in chunk_items:
                    content = (item.get("content") or item.get("c") or "").strip()
                    if content:
                        content = _normalize_choice_options(content)
                        all_items.append({"content": content})
                        if len(all_items) <= 10:
                            yield "data: " + json.dumps({"type": "ai_token", "text": content + "\n"}, ensure_ascii=False) + "\n\n"

        # 兜底：AI 完全未提取到条目时，才使用规则保守拆分
        if not all_items:
            all_items = _split_items_by_rules(full_text, new_type)

        items = all_items
        yield "data: " + json.dumps({"type": "ai_token", "text": f"\n共提取 {len(items)} 条\n"}, ensure_ascii=False) + "\n\n"
        if not items:
            yield "data: " + json.dumps({"type": "error", "text": "✗ 未能提取到任何条目"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        if new_type == "题目":
            problems = await read_json(get_problems_path(username, subject)) or []
            existing = {_dedup_key(p.get("content", "")) for p in problems if p.get("content")}
            added = 0
            for item in items:
                content = item.get("content", "").strip()
                if not content:
                    continue
                key = _dedup_key(content)
                if key and key in existing:
                    continue
                problems.append({
                    "id": str(uuid.uuid4())[:8], "subject": subject,
                    "exam": resolved_tag or "", "source": "", "school": "",
                    "big_question": "", "small_question": "",
                    "content": content, "image_file_id": "",
                    "knowledge_point": "", "is_wrong": False,
                    "is_shared": False, "created_at": now,
                    "solved_at": None, "solution": "", "session_id": "",
                    "parent_id": "", "is_big_question": False,
                    "filename": filename, "source_file": filename,
                    "upload_file_id": file_id,
                })
                if key:
                    existing.add(key)
                added += 1
            await write_json(get_problems_path(username, subject), problems)
            yield "data: " + json.dumps({"type": "result", "message": f"已保存 {added} 道题目", "count": added, "type": "题目"}, ensure_ascii=False) + "\n\n"
        else:
            answers_list = await read_json(get_answers_path(username, subject)) or []
            existing = {_dedup_key(a.get("content", "")) for a in answers_list if a.get("content")}
            added = 0
            for item in items:
                content = item.get("content", "").strip()
                if not content:
                    continue
                key = _dedup_key(content)
                if key and key in existing:
                    continue
                answers_list.append({
                    "id": str(uuid.uuid4())[:8], "tag": resolved_tag or "未分类",
                    "content": content, "answer": item.get("answer", ""),
                    "created_at": now, "filename": filename,
                    "source_file": filename, "upload_file_id": file_id,
                })
                if key:
                    existing.add(key)
                added += 1
            await write_json(get_answers_path(username, subject), answers_list)
            yield "data: " + json.dumps({"type": "result", "message": f"已保存 {added} 条答案", "count": added, "type": "答案"}, ensure_ascii=False) + "\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/extract-known")
async def extract_with_known_type(
    data: dict,
    username: str = Depends(get_current_user),
):
    filename = data.get("filename", "")
    doc_type = data.get("type", "")
    text = data.get("text", "")
    file_id = data.get("file_id", "")
    tag = data.get("tag", "")
    semester = data.get("semester", "")

    if not doc_type:
        raise HTTPException(status_code=400, detail="需要提供 type")
    if not text and file_id:
        text_path = os.path.join(UPLOAD_DIR, f"{file_id}_text.txt")
        if os.path.exists(text_path):
            with open(text_path, "r", encoding="utf-8") as f:
                text = f.read()
    if not text:
        raise HTTPException(status_code=400, detail="需要提供 text 或有效的 file_id")
    if doc_type not in ("题目", "答案", "词单", "资料"):
        raise HTTPException(status_code=400, detail="不支持的类型")

    config = await read_json(get_user_config_path(username)) or {}
    model_choice = config.get("deepseek_model", "flash")
    model_name = _get_deepseek_model_name(model_choice)
    api_key = config.get("deepseek_api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API Key 未配置")
    timeout = max(int(config.get("deepseek_timeout", 60) or 60), 180)
    client = create_client(api_key, DEEPSEEK_BASE_URL, timeout)
    subject = await get_user_subject(username)
    now = datetime.now().isoformat()
    resolved_tag = _resolve_tag(tag, semester)

    extract_prompt = EXTRACT_PROMPT

    answer_extract_prompt = ANSWER_EXTRACT_PROMPT

    word_extract_prompt = WORD_EXTRACT_PROMPT

    async def event_generator():
        yield "data: " + json.dumps({"type": "text", "text": f"开始处理：{filename} → {doc_type}\n"}, ensure_ascii=False) + "\n\n"

        if doc_type == "资料":
            file_id_new = str(uuid.uuid4())[:8]
            materials = await read_json(get_materials_path(username, subject)) or []
            materials.append({
                "id": file_id_new,
                "filename": filename or "未命名",
                "subject": subject,
                "time": resolved_tag or "未分类",
                "tag": resolved_tag or "未分类",
                "summary": text[:200],
                "file_path": "",
                "file_type": "txt",
                "file_size": len(text),
                "has_text": True,
                "created_at": now,
            })
            await write_json(get_materials_path(username, subject), materials)
            yield "data: " + json.dumps({"type": "result", "message": "已保存为资料", "count": 1, "type": "资料"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        elif doc_type == "词单":
            is_student = bool(re.search(r'学生版', filename))
            label_student = "学生版词单，提取模板（英文留空）\n" if is_student else "正在提取单词列表...\n"
            yield "data: " + json.dumps({"type": "ai_token", "text": label_student}, ensure_ascii=False) + "\n\n"
            word_text = text[:12000]
            max_out = 8192 if model_choice == "flash" else 16384
            stream = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "直接提取单词输出JSON，不要思考不要解释。"},
                    {"role": "user", "content": f"文件名：{filename}\n\n{word_extract_prompt}\n\n---\n{word_text}"}
                ],
                temperature=0.1, max_tokens=max_out,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}},
            )
            collected = []
            token_count = 0
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected.append(delta.content)
                    token_count += 1
                    if token_count % 30 == 0:
                        yield "data: " + json.dumps({"type": "ai_token", "text": f"⏳ 处理中（已收集 {token_count} 个片段）\n"}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"type": "ai_token", "text": "解析结果...\n"}, ensure_ascii=False) + "\n\n"
            raw = "".join(collected)
            words = _extract_words_fallback(raw, word_text)
            if words:
                for w in words[:20]:
                    en = w.get("english", "")
                    cn = w.get("chinese", "")
                    pos = w.get("pos", "")
                    label = f"{cn} [{pos}] → {en}" if pos else f"{cn} → {en}"
                    yield "data: " + json.dumps({"type": "ai_token", "text": f"{label}\n"}, ensure_ascii=False) + "\n\n"
                if len(words) > 20:
                    yield "data: " + json.dumps({"type": "ai_token", "text": f"... 等共 {len(words)} 个单词\n"}, ensure_ascii=False) + "\n\n"
                yield "data: " + json.dumps({"type": "ai_token", "text": f"✅ 共提取 {len(words)} 个单词\n"}, ensure_ascii=False) + "\n\n"
            else:
                yield "data: " + json.dumps({"type": "error", "text": "⚠ 单词格式解析失败\n"}, ensure_ascii=False) + "\n\n"
            word_count = len(words)

            file_id_new = str(uuid.uuid4())[:8]
            word_lists = await read_json(get_words_path(username, subject)) or []
            word_lists.append({
                "id": file_id_new, "filename": filename,
                "tag": resolved_tag or "未分类",
                "source_file": filename, "upload_file_id": file_id_new,
                "words": words,
                "word_count": word_count,
                "is_student": is_student,
                "created_at": now,
            })
            await write_json(get_words_path(username, subject), word_lists)
            yield "data: " + json.dumps({"type": "result", "message": f"已保存词单，共 {word_count} 个单词", "count": word_count, "type": "词单", "word_count": word_count}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        else:
            # 题目 或 答案
            chosen_prompt = answer_extract_prompt if doc_type == "答案" else extract_prompt
            max_out = 12288 if model_choice == "flash" else 24576

            yield "data: " + json.dumps({"type": "ai_token", "text": f"正在逐条提取{doc_type}...\n"}, ensure_ascii=False) + "\n\n"

            all_items = []
            chunks = _chunk_text_for_extraction(text, 11000, 300)
            for chunk_idx, chunk_text in enumerate(chunks):
                if len(chunks) > 1:
                    yield "data: " + json.dumps({"type": "ai_token", "text": f"处理文档片段 {chunk_idx + 1}/{len(chunks)}...\n"}, ensure_ascii=False) + "\n\n"
                stream = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "直接逐条提取输出JSON，不要思考不要解释。"},
                        {"role": "user", "content": f"文件名：{filename}\n\n{chosen_prompt}\n\n---\n{chunk_text}"}
                    ],
                    temperature=0.2, max_tokens=max_out,
                    stream=True,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                collected = []
                token_count = 0
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        collected.append(delta.content)
                        token_count += 1
                        if token_count % 30 == 0:
                            yield "data: " + json.dumps({"type": "ai_token", "text": f"⏳ 处理中（已收集 {token_count} 个片段）\n"}, ensure_ascii=False) + "\n\n"
                yield "data: " + json.dumps({"type": "ai_token", "text": "解析结果...\n"}, ensure_ascii=False) + "\n\n"
                raw = "".join(collected)
                extracted = _safe_extract_json(raw)
                if extracted:
                    chunk_items = extracted.get("items", [])
                    for item in chunk_items:
                        content = (item.get("content") or item.get("c") or "").strip()
                        if content:
                            content = _normalize_choice_options(content)
                            all_items.append({"content": content})
                            if len(all_items) <= 10:
                                yield "data: " + json.dumps({"type": "ai_token", "text": content + "\n"}, ensure_ascii=False) + "\n\n"

            # 兜底：AI 完全未提取到条目时，才使用规则保守拆分
            if not all_items:
                all_items = _split_items_by_rules(text, doc_type)

            items = all_items
            yield "data: " + json.dumps({"type": "ai_token", "text": f"\n共提取 {len(items)} 条\n"}, ensure_ascii=False) + "\n\n"
            if not items:
                yield "data: " + json.dumps({"type": "error", "text": "✗ 未能提取到任何条目"}, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
                return

            if doc_type == "题目":
                problems = await read_json(get_problems_path(username, subject)) or []
                existing = {_dedup_key(p.get("content", "")) for p in problems if p.get("content")}
                added = 0
                for item in items:
                    content = (item.get("content", "") or item.get("c", "")).strip()
                    if not content:
                        continue
                    key = _dedup_key(content)
                    if key and key in existing:
                        continue
                    problems.append({
                        "id": str(uuid.uuid4())[:8], "subject": subject,
                        "exam": resolved_tag or "", "source": "", "school": "",
                        "big_question": "", "small_question": "",
                        "content": content, "image_file_id": "",
                        "knowledge_point": "", "is_wrong": False,
                        "is_shared": False, "created_at": now,
                        "solved_at": None, "solution": "", "session_id": "",
                        "parent_id": "", "is_big_question": False,
                        "filename": filename, "source_file": filename,
                        "upload_file_id": file_id,
                    })
                    if key:
                        existing.add(key)
                    added += 1
                await write_json(get_problems_path(username, subject), problems)
                yield "data: " + json.dumps({"type": "result", "message": f"已保存 {added} 道题目", "count": added, "type": "题目"}, ensure_ascii=False) + "\n\n"
            else:
                answers_list = await read_json(get_answers_path(username, subject)) or []
                existing = {_dedup_key(a.get("content", "")) for a in answers_list if a.get("content")}
                added = 0
                for item in items:
                    content = (item.get("content", "") or item.get("c", "")).strip()
                    if not content:
                        continue
                    key = _dedup_key(content)
                    if key and key in existing:
                        continue
                    answers_list.append({
                        "id": str(uuid.uuid4())[:8], "tag": resolved_tag or "未分类",
                        "content": content, "answer": item.get("answer", ""),
                        "created_at": now, "filename": filename,
                        "source_file": filename, "upload_file_id": file_id,
                    })
                    if key:
                        existing.add(key)
                    added += 1
                await write_json(get_answers_path(username, subject), answers_list)
                yield "data: " + json.dumps({"type": "result", "message": f"已保存 {added} 条答案", "count": added, "type": "答案"}, ensure_ascii=False) + "\n\n"

            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
