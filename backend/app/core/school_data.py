import os
import uuid
from datetime import datetime

from app.core.paths import SHARED_DIR
from app.utils.file_lock import read_json, write_json


CLASS_TYPES_PATH = os.path.join(SHARED_DIR, "class_types.json")
CLASSES_PATH = os.path.join(SHARED_DIR, "classes.json")
DISTRIBUTIONS_PATH = os.path.join(SHARED_DIR, "material_distributions.json")


def new_entity_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now().isoformat()


async def load_class_types() -> list[dict]:
    data = await read_json(CLASS_TYPES_PATH)
    return data if isinstance(data, list) else []


async def save_class_types(items: list[dict]) -> None:
    await write_json(CLASS_TYPES_PATH, items)


async def load_classes() -> list[dict]:
    data = await read_json(CLASSES_PATH)
    return data if isinstance(data, list) else []


async def save_classes(items: list[dict]) -> None:
    await write_json(CLASSES_PATH, items)


async def load_distributions() -> list[dict]:
    data = await read_json(DISTRIBUTIONS_PATH)
    return data if isinstance(data, list) else []


async def save_distributions(items: list[dict]) -> None:
    await write_json(DISTRIBUTIONS_PATH, items)


def normalize_students(raw_students) -> list[dict]:
    students = []
    seen = set()
    for item in raw_students or []:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
            sid = (item.get("id") or new_entity_id("stu")).strip()
            username = (item.get("username") or "").strip()
            user_id = (item.get("user_id") or "").strip()
        else:
            name = str(item).strip()
            sid = new_entity_id("stu")
            username = ""
            user_id = ""
        key = username or name
        if not name or key in seen:
            continue
        seen.add(key)
        row = {"id": sid, "name": name}
        if username:
            row["username"] = username
        if user_id:
            row["user_id"] = user_id
        students.append(row)
    return students


def parse_roster_text(roster_text: str) -> list[dict]:
    if not roster_text:
        return []
    names = []
    for line in roster_text.replace("，", ",").splitlines():
        for part in line.split(","):
            name = part.strip()
            if name:
                names.append(name)
    return normalize_students(names)


def sync_student_to_classes(classes: list[dict], student_user: dict, class_ids: list[str]) -> tuple[list[dict], int]:
    """Add an approved registered student to selected class rosters.

    Existing hand-entered roster rows are preserved. If a row already matches the
    student's username or display name, it is enriched with the account identity
    instead of adding a duplicate.
    """
    target_ids = set(class_ids or [])
    if not target_ids:
        return classes, 0

    username = (student_user.get("username") or "").strip()
    real_name = (student_user.get("real_name") or username).strip()
    user_id = (student_user.get("id") or "").strip()
    if not username or not real_name:
        return classes, 0

    changed_count = 0
    for class_item in classes:
        if class_item.get("id") not in target_ids:
            continue

        students = normalize_students(class_item.get("students") or [])
        matched = None
        for row in students:
            row_username = (row.get("username") or "").strip()
            row_name = (row.get("name") or "").strip()
            if row_username == username or row_name == real_name:
                matched = row
                break

        if matched is None:
            students.append({
                "id": user_id or new_entity_id("stu"),
                "name": real_name,
                "username": username,
                "user_id": user_id,
            })
            changed_count += 1
        else:
            before = dict(matched)
            matched["name"] = matched.get("name") or real_name
            matched["username"] = username
            if user_id:
                matched["user_id"] = user_id
            if matched != before:
                changed_count += 1

        class_item["students"] = students

    return classes, changed_count
