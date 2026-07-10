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
        else:
            name = str(item).strip()
            sid = new_entity_id("stu")
        if not name or name in seen:
            continue
        seen.add(name)
        students.append({"id": sid, "name": name})
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
