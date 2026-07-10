import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.endpoints.materials import classify_material_locally, _normalize_doc_type


def test_classify_material_locally_detects_word_list_from_filename():
    result = classify_material_locally("学生版 E1 U13-U14 单词.docx", "")

    assert result["doc_type"] == "词单"
    assert result["confidence"] >= 0.8


def test_classify_material_locally_detects_answer_from_content():
    result = classify_material_locally("课堂练习.docx", "1. The old bridge c____.\n答案：collapsed")

    assert result["doc_type"] == "答案"


def test_normalize_doc_type_accepts_english_aliases():
    assert _normalize_doc_type("question") == "题目"
    assert _normalize_doc_type("answers") == "答案"
    assert _normalize_doc_type("vocabulary") == "词单"
