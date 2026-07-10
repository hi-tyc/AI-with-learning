import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.school_data import sync_student_to_classes


def test_sync_student_to_classes_adds_registered_student():
    classes = [{"id": "class_1", "students": []}]
    user = {"id": "user_1", "username": "alice", "real_name": "Alice"}

    updated, changed_count = sync_student_to_classes(classes, user, ["class_1"])

    assert changed_count == 1
    assert updated[0]["students"] == [
        {"id": "user_1", "name": "Alice", "username": "alice", "user_id": "user_1"}
    ]


def test_sync_student_to_classes_enriches_existing_roster_row():
    classes = [{"id": "class_1", "students": [{"id": "stu_1", "name": "Alice"}]}]
    user = {"id": "user_1", "username": "alice", "real_name": "Alice"}

    updated, changed_count = sync_student_to_classes(classes, user, ["class_1"])

    assert changed_count == 1
    assert updated[0]["students"] == [
        {"id": "stu_1", "name": "Alice", "username": "alice", "user_id": "user_1"}
    ]


def test_sync_student_to_classes_is_idempotent():
    classes = [{
        "id": "class_1",
        "students": [{"id": "user_1", "name": "Alice", "username": "alice", "user_id": "user_1"}],
    }]
    user = {"id": "user_1", "username": "alice", "real_name": "Alice"}

    updated, changed_count = sync_student_to_classes(classes, user, ["class_1"])

    assert changed_count == 0
    assert len(updated[0]["students"]) == 1
