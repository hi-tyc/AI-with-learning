import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.endpoints.school import _collect_wrong_book_entries


def sample_distribution():
    return {
        "id": "dist_1",
        "tag_path": "初一南外/周四下午",
        "note": "课堂讲义",
        "assigned_at": "2026-07-10T10:00:00",
        "students": [{"name": "Alice"}, {"name": "Bob"}],
        "wrong_book_records": [
            {"student_name": "Alice", "problem_ref": "阅读理解第 2 题", "is_wrong": True, "note": "定位错误"},
            {"student_name": "Bob", "problem_ref": "阅读理解第 2 题", "is_wrong": True, "note": "选项混淆"},
            {"student_name": "Bob", "problem_ref": "完形第 5 题", "is_wrong": True, "note": ""},
        ],
        "explanations": {
            "阅读理解第 2 题": {"content": "先定位关键词，再排除干扰项。"},
        },
    }


def test_collect_wrong_book_entries_groups_class_book_by_problem():
    entries = _collect_wrong_book_entries([sample_distribution()])

    assert len(entries) == 2
    reading = next(item for item in entries if item["problem_ref"] == "阅读理解第 2 题")
    assert reading["students"] == ["Alice", "Bob"]
    assert reading["wrong_students"] == ["Alice", "Bob"]
    assert reading["correct_rate"] == 0
    assert reading["notes"] == ["Alice: 定位错误", "Bob: 选项混淆"]
    assert reading["explanation"] == "先定位关键词，再排除干扰项。"


def test_collect_wrong_book_entries_filters_personal_book():
    entries = _collect_wrong_book_entries([sample_distribution()], "Alice")

    assert len(entries) == 1
    assert entries[0]["problem_ref"] == "阅读理解第 2 题"
    assert entries[0]["students"] == ["Alice"]
    assert entries[0]["notes"] == ["定位错误"]
