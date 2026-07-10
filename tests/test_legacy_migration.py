import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.migrate_legacy_english import (
    collect_materials_for_user,
    distribution_from_wrong_book,
    merge_by_id,
    write_json,
)


def test_collect_materials_for_user_merges_doc_types_by_upload_id(tmp_path):
    users_dir = tmp_path / "users"
    users_dir.mkdir(parents=True)
    write_json(users_dir / "old_英语_materials.json", [
        {
            "id": "file_1",
            "filename": "练习.docx",
            "tag": "期末 / 25-26 第二学期",
            "file_type": "docx",
            "created_at": "2026-01-01T00:00:00",
        }
    ])
    write_json(users_dir / "old_英语_answers.json", [
        {
            "id": "answer_1",
            "upload_file_id": "file_1",
            "filename": "练习.docx",
            "tag": "期末",
            "file_type": "docx",
        }
    ])

    materials = collect_materials_for_user(users_dir, "old", "teacher", "class_1", "ctype_1")

    assert len(materials) == 1
    assert materials[0]["id"] == "file_1"
    assert materials[0]["doc_type"] == "答案"
    assert materials[0]["owner_teacher"] == "teacher"
    assert materials[0]["class_id"] == "class_1"
    assert materials[0]["class_type_id"] == "ctype_1"


def test_distribution_from_wrong_book_converts_problem_and_word_rows():
    distribution = distribution_from_wrong_book(
        "old",
        "teacher",
        "张三",
        [
            {"id": "w1", "type": "problem", "content": "阅读第 2 题", "answer_contents": ["答案 A"], "created_at": "2026-01-01T00:00:00"},
            {"id": "w2", "type": "word", "word_english": "accept", "word_chinese": "接受", "created_at": "2026-01-02T00:00:00"},
        ],
        "class_1",
        "",
        "teacher",
    )

    assert distribution is not None
    assert distribution["target_type"] == "class"
    assert distribution["target_ids"] == ["class_1"]
    assert len(distribution["wrong_book_records"]) == 2
    assert distribution["wrong_book_records"][0]["problem_ref"] == "阅读第 2 题"
    assert distribution["wrong_book_records"][1]["problem_ref"] == "词单：accept 接受"


def test_merge_by_id_is_idempotent():
    existing = [{"id": "a", "filename": "old"}]
    merged, added = merge_by_id(existing, [{"id": "a", "filename": "new"}, {"id": "b", "filename": "b"}])

    assert added == 1
    assert len(merged) == 2
    assert merged[0]["filename"] == "old"
