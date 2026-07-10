from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import io
import re
from datetime import datetime
from urllib.parse import quote

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from app.api.endpoints.auth import get_current_user
from app.core.user_data import get_user_subject, get_materials_path, get_library_trash_path
from app.core.paths import UPLOAD_DIR
from app.utils.file_lock import read_json, write_json
from app.utils.doc_converter import convert_docx_to_pdf, _convert_sync
import logging

router = APIRouter()


MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89\x50\x4e\x47"
MAGIC_PDF = b"%PDF"
MAGIC_ZIP = b"PK\x03\x04"


def _material_tree_node(name: str = "") -> dict:
    return {
        "name": name,
        "path": name,
        "count": 0,
        "children": {},
        "items": [],
    }


def _build_tag_tree(materials: list[dict]) -> list[dict]:
    root = _material_tree_node("")
    for material in materials:
        tag = (material.get("tag") or material.get("time") or "未分类").strip("/")
        parts = [part.strip() for part in tag.split("/") if part.strip()] or ["未分类"]
        cursor = root
        prefix = []
        for part in parts:
            prefix.append(part)
            if part not in cursor["children"]:
                cursor["children"][part] = {
                    "name": part,
                    "path": "/".join(prefix),
                    "count": 0,
                    "children": {},
                    "items": [],
                }
            cursor = cursor["children"][part]
            cursor["count"] += 1
        cursor["items"].append({
            "id": material["id"],
            "filename": material["filename"],
            "file_type": material.get("file_type", "pdf"),
            "created_at": material.get("created_at", ""),
            "file_size": material.get("file_size", 0),
        })

    def serialize(node: dict) -> dict:
        return {
            "name": node["name"],
            "path": node["path"],
            "count": node["count"],
            "items": node["items"],
            "children": [serialize(child) for child in sorted(node["children"].values(), key=lambda item: item["name"])],
        }

    return [serialize(child) for child in sorted(root["children"].values(), key=lambda item: item["name"])]


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
        import io
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False


def _run_to_html(run) -> str:
    text = run.text or ""
    if not text:
        return ""

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r' {2,}', lambda m: '\xa0' * len(m.group()), text)

    font = run.font
    styles = []

    if font and font.size:
        try:
            styles.append(f"font-size:{font.size.pt}pt")
        except Exception:
            pass
    if font and font.name:
        styles.append(f"font-family:{font.name}")
    if font and font.color and font.color.rgb:
        styles.append(f"color:#{font.color.rgb}")

    style_attr = f' style="{";".join(styles)}"' if styles else ""

    if run.bold:
        text = f"<strong>{text}</strong>"
    if run.italic:
        text = f"<em>{text}</em>"
    if run.underline:
        text = f"<u>{text}</u>"
    if font and font.strike:
        text = f"<s>{text}</s>"
    if font and (font.subscript or font.superscript):
        tag = "sub" if font.subscript else "sup"
        text = f"<{tag}>{text}</{tag}>"

    if style_attr:
        text = f'<span{style_attr}>{text}</span>'

    text = text.replace("\n", "<br>").replace("\x0b", "<br>")
    return text


def _para_inner_html(para) -> str:
    return "".join(_run_to_html(run) for run in para.runs)


def _para_to_html(para) -> str:
    pf = para.paragraph_format
    styles = []

    if para.alignment == WD_ALIGN_PARAGRAPH.CENTER:
        styles.append("text-align:center")
    elif para.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
        styles.append("text-align:right")
    elif para.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
        styles.append("text-align:justify")

    if pf.left_indent:
        try:
            styles.append(f"margin-left:{pf.left_indent.pt}pt")
        except Exception:
            pass
    if pf.right_indent:
        try:
            styles.append(f"margin-right:{pf.right_indent.pt}pt")
        except Exception:
            pass
    if pf.first_line_indent:
        try:
            styles.append(f"text-indent:{pf.first_line_indent.pt}pt")
        except Exception:
            pass
    if pf.space_before:
        try:
            styles.append(f"margin-top:{pf.space_before.pt}pt")
        except Exception:
            pass
    if pf.space_after:
        try:
            styles.append(f"margin-bottom:{pf.space_after.pt}pt")
        except Exception:
            pass
    if pf.line_spacing and isinstance(pf.line_spacing, (int, float)):
        styles.append(f"line-height:{pf.line_spacing}")

    ppr = para._p.get_or_add_pPr()
    br = ppr.find(qn('w:pageBreakBefore'))
    page_break = br is not None and br.get(qn('w:val')) != '0'

    style_attr = f' style="{";".join(styles)}"' if styles else ""

    heading_level = 0
    try:
        style_name = para.style.name if para.style else ""
        if style_name.startswith("Heading "):
            heading_level = int(style_name.split()[-1])
    except Exception:
        pass

    content = _para_inner_html(para)
    if not content.strip():
        content = "&nbsp;"

    num_pr = ppr.find(qn('w:numPr'))
    is_list = num_pr is not None

    if is_list:
        return f"<li{style_attr}>{content}</li>"

    tag = f"h{heading_level}" if 1 <= heading_level <= 6 else "p"
    pb_attr = ' class="page-break"' if page_break else ""
    return f"<{tag}{pb_attr}{style_attr}>{content}</{tag}>"


def _table_to_html(table) -> str:
    rows = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cell_html = "".join(f"<p style=\"margin:2px 0;line-height:1.5;\">{_para_inner_html(p)}</p>" for p in cell.paragraphs if _para_inner_html(p).strip())
            cells.append(f'<td style="border:1px solid #bbb;padding:5px 8px;vertical-align:top;">{cell_html or "&nbsp;"}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table style="border-collapse:collapse;width:100%;margin:12px 0;font-size:10.5pt;">{"".join(rows)}</table>'


def _docx_to_html(data: bytes) -> str:
    try:
        doc = Document(io.BytesIO(data))
    except Exception:
        return ""

    html_parts = [
        '<div class="docx-content" style="font-family:Calibri,Microsoft YaHei,SimSun,sans-serif;font-size:11pt;line-height:1.7;color:#1e293b;">'
    ]

    para_idx = 0
    tbl_idx = 0
    list_open = None

    for element in doc.element.body:
        tag = element.tag.split('}')[-1]
        if tag == 'p':
            if para_idx < len(doc.paragraphs):
                para = doc.paragraphs[para_idx]
                para_html = _para_to_html(para)
                if para_html.startswith('<li'):
                    if list_open is None:
                        list_open = 'ul'
                        html_parts.append('<ul style="margin:4px 0;padding-left:28px;">')
                    html_parts.append(para_html)
                else:
                    if list_open is not None:
                        html_parts.append(f'</{list_open}>')
                        list_open = None
                    html_parts.append(para_html)
                para_idx += 1
        elif tag == 'tbl':
            if list_open is not None:
                html_parts.append(f'</{list_open}>')
                list_open = None
            if tbl_idx < len(doc.tables):
                html_parts.append(_table_to_html(doc.tables[tbl_idx]))
                tbl_idx += 1

    if list_open is not None:
        html_parts.append(f'</{list_open}>')

    html_parts.append('</div>')
    return "\n".join(html_parts)


async def _extract_docx_text(data: bytes) -> str:
    html = _docx_to_html(data)
    if not html:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|li|tr|h[1-6]|td)>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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
            try:
                parts.append(page.get_text("markdown"))
            except ValueError:
                parts.append(page.get_text())
        doc.close()
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return "\n\n".join(parts).strip()
    except Exception:
        return ""


@router.post("")
async def upload_material(
    file: UploadFile = File(...),
    subject: str = Form(...),
    time: str = Form(...),
    tag: str = Form(""),
    username: str = Depends(get_current_user),
):
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    file_id = str(uuid.uuid4())
    file_type = "unknown"
    ext = ""
    filename = file.filename or ""

    if _is_pdf(data):
        file_type = "pdf"
        ext = ".pdf"
    elif _is_image(data):
        file_type = "image"
        ext = ".jpg"
    elif _is_docx(data, filename):
        file_type = "docx"
        ext = ".docx"
    else:
        raise HTTPException(status_code=400, detail="仅支持 PDF、Word（docx）、JPG、PNG 文件")

    save_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    with open(save_path, "wb") as f:
        f.write(data)

    text_content = ""
    html_content = ""
    if file_type == "pdf":
        text_content = await _extract_pdf_text(data)
    elif file_type == "docx":
        html_content = _docx_to_html(data)
        text_content = await _extract_docx_text(data)

    if html_content and file_type == "docx":
        html_path = os.path.join(UPLOAD_DIR, f"{file_id}_text.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    if text_content:
        text_path = os.path.join(UPLOAD_DIR, f"{file_id}_text.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text_content)

    material = {
        "id": file_id,
        "filename": filename or f"未命名{ext}",
        "subject": subject,
        "time": time,
        "tag": tag or time,
        "file_path": save_path,
        "file_type": file_type,
        "file_size": len(data),
        "has_text": bool(text_content),
        "created_at": datetime.now().isoformat(),
    }

    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    materials.append(material)
    await write_json(get_materials_path(username, config_subject), materials)

    return material


@router.get("")
async def list_materials(
    subject: Optional[str] = None,
    time: Optional[str] = None,
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    if subject:
        materials = [m for m in materials if m.get("subject") == subject]
    if time:
        materials = [m for m in materials if m.get("time") == time]
    return {"items": materials}


@router.get("/tree")
async def get_materials_tree(
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    tree = {}
    for m in materials:
        tag = m.get("tag") or m.get("time", "未分类")
        if tag not in tree:
            tree[tag] = {"count": 0, "items": []}
        tree[tag]["count"] += 1
        tree[tag]["items"].append({
            "id": m["id"],
            "filename": m["filename"],
            "file_type": m.get("file_type", "pdf"),
            "has_text": m.get("has_text", False),
            "file_size": m.get("file_size", 0),
            "created_at": m.get("created_at", ""),
        })
    return tree


@router.get("/tag-tree")
async def get_materials_tag_tree(
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    return {"items": _build_tag_tree(materials)}


@router.get("/tags")
async def get_tags(
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    tags = sorted(set((m.get("tag") or m.get("time", "")) for m in materials if (m.get("tag") or m.get("time"))))
    return {"tags": tags}


@router.get("/tree_by_time")
async def get_materials_tree_by_time(
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    tree = {}
    for m in materials:
        sub = m.get("subject", "未分类")
        t = m.get("time", "未分类")
        if sub not in tree:
            tree[sub] = {}
        if t not in tree[sub]:
            tree[sub][t] = {"count": 0, "items": []}
        tree[sub][t]["count"] += 1
        tree[sub][t]["items"].append({
            "id": m["id"],
            "filename": m["filename"],
            "file_type": m.get("file_type", "pdf"),
            "has_text": m.get("has_text", False),
        })
    return tree


@router.get("/subjects")
async def get_subjects(
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    subjects = sorted(set(m.get("subject", "未分类") for m in materials if m.get("subject")))
    return {"subjects": subjects}


@router.get("/{material_id}")
async def get_material(
    material_id: str,
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    for m in materials:
        if m["id"] == material_id:
            return m
    raise HTTPException(status_code=404, detail="资料不存在")


@router.get("/{material_id}/text")
async def get_material_text(
    material_id: str,
    username: str = Depends(get_current_user),
):
    # Try cached _text.txt first
    text_path = os.path.join(UPLOAD_DIR, f"{material_id}_text.txt")
    if os.path.exists(text_path):
        with open(text_path, "r", encoding="utf-8") as f:
            content = f.read()
            if content.strip():
                return {"text": content}

    # Fallback: extract text from original file on-the-fly
    for ext in (".pdf", ".docx", ".jpg", ".jpeg", ".png"):
        candidate = os.path.join(UPLOAD_DIR, f"{material_id}{ext}")
        if not os.path.exists(candidate):
            continue
        try:
            if ext == ".pdf":
                text = await _extract_pdf_text(open(candidate, "rb").read())
            elif ext == ".docx":
                text = await _extract_docx_text(open(candidate, "rb").read())
            else:
                text = ""
            if text and text.strip():
                # Cache for next time
                try:
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(text)
                except Exception:
                    pass
                return {"text": text}
        except Exception:
            continue
        break

    return {"text": ""}


@router.get("/{material_id}/html")
async def get_material_html(
    material_id: str,
    username: str = Depends(get_current_user),
):
    """Return rich HTML for docx files.

    1. Use already-cached ``{material_id}_text.html`` if present.
    2. Regenerate from original ``.docx`` on the fly and cache.
    3. Return empty — frontend will fall back to client-side mammoth.
    """
    html_path = os.path.join(UPLOAD_DIR, f"{material_id}_text.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return {"html": f.read(), "type": "html"}

    candidate = os.path.join(UPLOAD_DIR, f"{material_id}.docx")
    if os.path.exists(candidate):
        try:
            with open(candidate, "rb") as f:
                data = f.read()
            html_content = _docx_to_html(data)
            if html_content:
                try:
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                except Exception:
                    pass
                return {"html": html_content, "type": "html"}
        except Exception:
            pass

    # Fallback: show _text.txt content as plain pre-formatted text
    text_path = os.path.join(UPLOAD_DIR, f"{material_id}_text.txt")
    if os.path.exists(text_path):
        try:
            with open(text_path, "r", encoding="utf-8") as f:
                raw = f.read()
            # Strip common markdown formatting so users don't see raw syntax
            cleaned = raw.replace('***', '').replace('**', '').replace('*', '')
            cleaned = re.sub(r'^#+\s*', '', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r'^\s*\|[\s\-|]+\|\s*$', '', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
            escaped = cleaned.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            return {
                "html": f'<div class="docx-content" style="white-space:pre-wrap;font-family:Calibri,Microsoft YaHei,SimSun,sans-serif;line-height:1.7;padding:20px;color:#334155;">{escaped}</div>',
                "type": "text",
            }
        except Exception:
            pass

    return {"html": "", "type": "none"}


@router.get("/{material_id}/file")
async def download_material_file(
    material_id: str,
    download: bool = False,
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    target = None
    for m in materials:
        if m["id"] == material_id:
            target = m
            break

    file_path = ""
    filename = ""
    if target:
        file_path = target.get("file_path", "")
        filename = target.get("filename", "")

    if not file_path or not os.path.exists(file_path):
        for ext in (".pdf", ".docx", ".jpg", ".jpeg", ".png"):
            candidate = os.path.join(UPLOAD_DIR, f"{material_id}{ext}")
            if os.path.exists(candidate):
                file_path = candidate
                if not filename:
                    filename = os.path.basename(candidate)
                break

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="原始文件不存在")

    if not filename:
        filename = os.path.basename(file_path)

    return await _serve_file(file_path, filename, download)


@router.get("/{material_id}/pdf")
async def get_material_pdf(
    material_id: str,
    username: str = Depends(get_current_user),
):
    """Convert docx to PDF using LibreOffice and serve the PDF inline."""
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    target = None
    for m in materials:
        if m["id"] == material_id:
            target = m
            break

    if not target:
        raise HTTPException(status_code=404, detail="资料不存在")

    file_type = (target.get("file_type") or "").lower()
    if file_type != "docx":
        if file_type == "pdf":
            file_path = target.get("file_path", "")
            if not file_path or not os.path.exists(file_path):
                for ext in (".pdf",):
                    candidate = os.path.join(UPLOAD_DIR, f"{material_id}{ext}")
                    if os.path.exists(candidate):
                        file_path = candidate
                        break
            if file_path and os.path.exists(file_path):
                return await _serve_file(file_path, target.get("filename", ""), False)
        raise HTTPException(status_code=400, detail="仅支持 docx 文件转换 PDF")

    from app.core.paths import BASE_DIR

    docx_path = ""
    docx_path = target.get("file_path", "")
    if not docx_path or not os.path.exists(docx_path):
        candidate = os.path.join(UPLOAD_DIR, f"{material_id}.docx")
        if os.path.exists(candidate):
            docx_path = candidate

    # Try resolving relative paths against BASE_DIR
    if not docx_path or not os.path.exists(docx_path):
        relative = target.get("file_path", "")
        if relative and not os.path.isabs(relative):
            abs_path = os.path.normpath(os.path.join(BASE_DIR, relative))
            if os.path.exists(abs_path):
                docx_path = abs_path

    if not docx_path or not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="原始文件不存在")

    logger = logging.getLogger("materials")
    logger.info(f"Converting to PDF: docx_path={docx_path} UPLOAD_DIR={UPLOAD_DIR}")
    pdf_path = await convert_docx_to_pdf(docx_path, UPLOAD_DIR)
    if not pdf_path or not os.path.exists(pdf_path):
        logger.error(f"PDF conversion failed: docx_path={docx_path} UPLOAD_DIR={UPLOAD_DIR}")
        from app.utils.doc_converter import _soffice_exists, SOFFICE
        logger.error(f"soffice_exists={_soffice_exists()} SOFFICE={SOFFICE}")
        # Try sync fallback
        pdf_path = _convert_sync(docx_path, UPLOAD_DIR)
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="PDF 转换失败，请检查 LibreOffice 是否正常安装")

    pdf_filename = os.path.splitext(target.get("filename", "document"))[0] + ".pdf"
    return await _serve_file(pdf_path, pdf_filename, False)


@router.get("/{material_id}/print")
async def print_material(
    material_id: str,
    username: str = Depends(get_current_user),
):
    """Return an HTML page that embeds the PDF and auto-prints once loaded."""
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    target = None
    for m in materials:
        if m["id"] == material_id:
            target = m
            break

    if not target:
        raise HTTPException(status_code=404, detail="资料不存在")

    file_type = (target.get("file_type") or "").lower()
    pdf_id = material_id
    if file_type == "docx":
        # Trigger conversion first
        from app.core.paths import BASE_DIR
        docx_path = target.get("file_path", "")
        if not docx_path or not os.path.exists(docx_path):
            candidate = os.path.join(UPLOAD_DIR, f"{material_id}.docx")
            if os.path.exists(candidate):
                docx_path = candidate
        if docx_path and os.path.exists(docx_path):
            await convert_docx_to_pdf(docx_path, UPLOAD_DIR)

    pdf_url = f"/api/materials/{material_id}/pdf"
    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
body {{ margin: 0; }}
iframe {{ width: 100vw; height: 100vh; border: none; }}
@media print {{ .no-print {{ display: none; }} }}
</style>
</head><body>
<div id="toolbar" style="position:fixed;top:0;right:0;z-index:999;padding:10px;background:rgba(255,255,255,0.9);">
<button onclick="window.print()" style="padding:8px 20px;font-size:14px;cursor:pointer;border:1px solid #ccc;border-radius:4px;background:#2563eb;color:#fff;">打印</button>
</div>
<iframe id="pdf-frame" src="{pdf_url}" loading="lazy"></iframe>
<script>
var iframe = document.getElementById('pdf-frame');
if (iframe) {{
  var attemptPrint = function(attempts) {{
    attempts = attempts || 0;
    if (attempts > 20) return;
    try {{
      window.print();
    }} catch(e) {{
      setTimeout(function() {{ attemptPrint(attempts + 1); }}, 500);
    }}
  }};
  iframe.onload = function() {{
    setTimeout(function() {{ attemptPrint(); }}, 1500);
  }};
}}
</script>
</body></html>"""
    return HTMLResponse(content=html)


async def _serve_file(file_path: str, filename: str, download: bool):
    """Helper to serve a file with proper content type and disposition."""
    ext = os.path.splitext(file_path)[1].lower()
    media_type = "application/octet-stream"
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"

    disposition_type = "attachment" if download else "inline"
    encoded_name = quote(filename, safe="")
    ascii_safe = ''.join(c if 32 <= ord(c) < 127 else '_' for c in filename)
    ascii_safe = ascii_safe.replace('\\', '\\\\').replace('"', '\\"')
    cd_header = f'{disposition_type}; filename="{ascii_safe}"; filename*=UTF-8\'\'{encoded_name}'

    headers = {
        "Content-Disposition": cd_header,
        "Content-Length": str(os.path.getsize(file_path)),
    }

    def file_iterator():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=media_type,
        headers=headers,
    )


@router.delete("/{material_id}")
async def delete_material(
    material_id: str,
    username: str = Depends(get_current_user),
):
    config_subject = await get_user_subject(username)
    materials = await read_json(get_materials_path(username, config_subject)) or []
    target = None
    for m in materials:
        if m["id"] == material_id:
            target = m
            break
    if not target:
        raise HTTPException(status_code=404, detail="资料不存在")
    target["trashed_at"] = datetime.now().isoformat()
    target["_origin_type"] = "material"
    new_materials = [x for x in materials if x["id"] != material_id]
    await write_json(get_materials_path(username, config_subject), new_materials)
    trash = await read_json(get_library_trash_path(username, config_subject)) or []
    trash.append(target)
    await write_json(get_library_trash_path(username, config_subject), trash)
    return {"message": "已移入废纸篓"}
