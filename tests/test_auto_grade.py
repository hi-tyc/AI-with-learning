import sys
import asyncio
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import app.api.endpoints.school as school
from app.api.endpoints.school import AutoGradeRequest, _apply_auto_grade_result, _normalize_auto_grade_result


def test_normalize_auto_grade_result_keeps_only_confident_wrong_items():
    result = _normalize_auto_grade_result(
        """
        {
          "summary": "第 2 题时态错误。",
          "score": 85,
          "ungraded_count": 1,
          "items": [
            {"problem_ref": "第1题", "is_wrong": false, "confidence": 0.98},
            {"problem_ref": "第2题", "student_answer": "go", "correct_answer": "went", "is_wrong": true, "reason": "时态错误", "confidence": 0.93},
            {"problem_ref": "第3题", "is_wrong": true, "confidence": 0.4}
          ]
        }
        """
    )

    assert result["score"] == 85
    assert result["recognized_count"] == 3
    assert result["wrong_count"] == 1
    assert result["ungraded_count"] == 1
    assert result["wrong_items"][0]["problem_ref"] == "第2题"


def test_apply_auto_grade_result_replaces_matching_previous_auto_grade_only():
    target = {
        "wrong_book_records": [
            {"student_name": "Alice", "problem_ref": "人工登记", "source": "manual", "is_wrong": True},
            {
                "student_name": "Alice",
                "problem_ref": "旧 AI 错题",
                "source": "ai_auto_grade",
                "answer_material_id": "answer_1",
                "submission_material_id": "submission_1",
                "is_wrong": True,
            },
        ],
        "auto_grade_records": [],
    }
    request = AutoGradeRequest(
        student_name="Alice",
        answer_material_id="answer_1",
        submission_material_id="submission_1",
        replace_existing=True,
    )
    result = {
        "summary": "已完成",
        "score": 90,
        "recognized_count": 2,
        "wrong_count": 1,
        "ungraded_count": 0,
        "model": "kimi-k2.7-code",
        "wrong_items": [
            {
                "problem_ref": "第2题",
                "student_answer": "go",
                "correct_answer": "went",
                "reason": "时态错误",
                "confidence": 0.9,
            }
        ],
    }

    grade, created_count = _apply_auto_grade_result(target, request, result, {"username": "teacher"})

    assert created_count == 1
    assert grade["student_name"] == "Alice"
    refs = [row["problem_ref"] for row in target["wrong_book_records"]]
    assert "人工登记" in refs
    assert "旧 AI 错题" not in refs
    assert "第2题" in refs


def test_auto_grade_endpoint_writes_kimi_wrong_items_to_distribution():
    distribution = {
        "id": "dist_1",
        "assigned_by": "teacher",
        "students": [{"id": "student_1", "name": "Alice"}],
        "wrong_book_records": [],
        "auto_grade_records": [],
    }
    materials = [
        {"id": "answer_1", "filename": "答案.docx", "file_type": "docx"},
        {"id": "submission_1", "filename": "Alice.jpg", "file_type": "image"},
    ]
    saved = []

    async def fake_load_distributions():
        return [distribution]

    async def fake_save_distributions(items):
        saved.extend(items)

    async def fake_get_subject(_username):
        return "英语"

    async def fake_read_json(_path):
        return materials

    async def fake_grade(_answer, _submission, _user):
        return {
            "summary": "第 3 题拼写错误。",
            "score": 92,
            "recognized_count": 4,
            "wrong_count": 1,
            "ungraded_count": 0,
            "model": "kimi-k2.7-code",
            "wrong_items": [{
                "problem_ref": "第3题",
                "student_answer": "becuse",
                "correct_answer": "because",
                "reason": "拼写错误",
                "confidence": 0.97,
            }],
        }

    async def invoke():
        with (
            patch.object(school, "load_distributions", fake_load_distributions),
            patch.object(school, "save_distributions", fake_save_distributions),
            patch.object(school, "get_user_subject", fake_get_subject),
            patch.object(school, "read_json", fake_read_json),
            patch.object(school, "_run_kimi_auto_grade", fake_grade),
            patch.object(school, "get_materials_path", lambda *_args: "materials.json"),
        ):
            return await school.auto_grade_distribution(
                "dist_1",
                AutoGradeRequest(
                    student_name="Alice",
                    answer_material_id="answer_1",
                    submission_material_id="submission_1",
                ),
                {"username": "teacher", "role": "teacher"},
            )

    response = asyncio.run(invoke())

    assert response["grade"]["score"] == 92
    assert response["stats"]["wrong_count"] == 1
    assert distribution["wrong_book_records"][0]["problem_ref"] == "第3题"
    assert distribution["wrong_book_records"][0]["source"] == "ai_auto_grade"
    assert saved == [distribution]
