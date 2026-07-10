#!/usr/bin/env python3
"""
Migrate legacy English data from the 7.9 data zip into the current teacher model.

Default mode is dry-run. Pass --apply to write files.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SUBJECT = "英语"
DOC_TYPE_BY_SUFFIX = {
    "materials": "资料",
    "problems": "题目",
    "answers": "答案",
    "words": "词单",
}


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def normalize_tag(value: str) -> str:
    value = (value or "").strip().replace("\\", "/")
    value = value.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    return value.strip("/") or "未分类"


def legacy_users(source_users: Path) -> list[str]:
    names = set()
    for path in source_users.glob(f"*_{DEFAULT_SUBJECT}_*.json"):
        stem = path.stem
        marker = f"_{DEFAULT_SUBJECT}_"
        if marker in stem:
            names.add(stem.split(marker, 1)[0])
    return sorted(names)


def mapped_username(username: str, user_map: dict[str, str]) -> str:
    return user_map.get(username, username)


def parse_user_map(raw_items: list[str]) -> dict[str, str]:
    result = {}
    for item in raw_items or []:
        if "=" not in item:
            raise SystemExit(f"--map-user 格式应为 old=new，收到: {item}")
        old, new = item.split("=", 1)
        old = old.strip()
        new = new.strip()
        if old and new:
            result[old] = new
    return result


def infer_file_type(filename: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".docx"):
        return "docx"
    if lower.endswith((".jpg", ".jpeg", ".png")):
        return "image"
    return "unknown"


def material_from_legacy(item: dict, doc_type: str, owner: str, class_id: str, class_type_id: str) -> dict | None:
    upload_id = item.get("upload_file_id") or item.get("id")
    filename = item.get("filename") or item.get("source_file") or ""
    if not upload_id or not filename:
        return None
    file_type = infer_file_type(filename, item.get("file_type", ""))
    return {
        "id": upload_id,
        "filename": filename,
        "subject": DEFAULT_SUBJECT,
        "time": normalize_tag(item.get("time") or item.get("tag") or item.get("exam_tag") or item.get("exam") or ""),
        "tag": normalize_tag(item.get("tag") or item.get("exam_tag") or item.get("exam") or ""),
        "summary": item.get("summary", ""),
        "doc_type": doc_type,
        "owner_teacher": owner,
        "class_id": class_id,
        "class_type_id": class_type_id,
        "file_path": f"uploads/{upload_id}.{file_type if file_type != 'image' else 'jpg'}",
        "file_type": file_type,
        "file_size": item.get("file_size", 0),
        "has_text": bool(item.get("has_text", False)),
        "created_at": item.get("created_at") or datetime.now().isoformat(),
        "legacy_source": "AI伴学 7.9",
        "legacy_item_id": item.get("id", ""),
    }


def collect_materials_for_user(source_users: Path, legacy_username: str, owner: str, class_id: str, class_type_id: str) -> list[dict]:
    by_id: dict[str, dict] = {}
    for suffix, doc_type in DOC_TYPE_BY_SUFFIX.items():
        path = source_users / f"{legacy_username}_{DEFAULT_SUBJECT}_{suffix}.json"
        rows = read_json(path, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            material = material_from_legacy(row, doc_type, owner, class_id, class_type_id)
            if not material:
                continue
            existing = by_id.get(material["id"])
            if existing:
                priority = ["资料", "题目", "答案", "词单"]
                if priority.index(material["doc_type"]) > priority.index(existing.get("doc_type", "资料")):
                    existing["doc_type"] = material["doc_type"]
                existing["tag"] = existing.get("tag") or material["tag"]
                existing["time"] = existing.get("time") or material["time"]
            else:
                by_id[material["id"]] = material
    return sorted(by_id.values(), key=lambda item: item.get("created_at", ""))


def find_upload_assets(source_uploads: Path, upload_id: str, file_type: str) -> list[Path]:
    assets = []
    preferred_exts = {
        "pdf": [".pdf"],
        "docx": [".docx"],
        "image": [".jpg", ".jpeg", ".png", "_compressed.jpg"],
        "unknown": [".pdf", ".docx", ".jpg", ".jpeg", ".png", "_compressed.jpg"],
    }.get(file_type, [".pdf", ".docx", ".jpg", ".jpeg", ".png", "_compressed.jpg"])
    for ext in preferred_exts:
        candidate = source_uploads / f"{upload_id}{ext}"
        if candidate.exists():
            assets.append(candidate)
    for suffix in ["_text.txt", "_text.html"]:
        candidate = source_uploads / f"{upload_id}{suffix}"
        if candidate.exists():
            assets.append(candidate)
    return assets


def copy_upload_assets(source_uploads: Path, target_uploads: Path, material: dict, apply: bool) -> int:
    copied = 0
    for source in find_upload_assets(source_uploads, material["id"], material.get("file_type", "unknown")):
        if source.name.endswith("_compressed.jpg"):
            target_name = f"{material['id']}.jpg"
        else:
            target_name = source.name
        target = target_uploads / target_name
        if target.exists():
            continue
        copied += 1
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return copied


def wrong_problem_ref(row: dict) -> str:
    if row.get("type") == "word":
        english = row.get("word_english") or ""
        chinese = row.get("word_chinese") or ""
        pos = row.get("word_pos") or ""
        parts = [part for part in [english, pos, chinese] if part]
        return "词单：" + " ".join(parts)
    return row.get("content") or row.get("problem_ref") or row.get("source_file") or "未命名错题"


def wrong_note(row: dict) -> str:
    notes = []
    if row.get("source_file"):
        notes.append(f"来源：{row['source_file']}")
    if row.get("answer_contents"):
        notes.append("答案：" + "；".join(str(item) for item in row["answer_contents"] if item))
    if row.get("mismatch_flag"):
        notes.append("旧系统标记：未匹配")
    if row.get("tag") or row.get("exam_tag"):
        notes.append(f"标签：{row.get('exam_tag') or row.get('tag')}")
    return "；".join(notes)


def legacy_distribution_id(username: str) -> str:
    return f"legacy_english_wrong_{uuid.uuid5(uuid.NAMESPACE_DNS, username).hex[:12]}"


def distribution_from_wrong_book(
    legacy_username: str,
    owner: str,
    display_name: str,
    wrong_rows: list[dict],
    class_id: str,
    class_type_id: str,
    assigned_by: str,
) -> dict | None:
    records = []
    for row in wrong_rows:
        if not isinstance(row, dict):
            continue
        records.append({
            "student_name": display_name,
            "problem_ref": wrong_problem_ref(row),
            "is_wrong": True,
            "note": wrong_note(row),
            "marked_by": assigned_by or owner,
            "marked_at": row.get("created_at") or datetime.now().isoformat(),
            "legacy_id": row.get("id", ""),
            "legacy_type": row.get("type", "problem"),
        })
    if not records:
        return None
    target_type = "class" if class_id else ("class_type" if class_type_id else "legacy")
    target_ids = [class_id] if class_id else ([class_type_id] if class_type_id else [])
    return {
        "id": legacy_distribution_id(legacy_username),
        "material_ids": [],
        "target_type": target_type,
        "target_ids": target_ids,
        "tag_path": "旧数据/英语错题本",
        "note": f"从 AI伴学 7.9 迁移：{legacy_username}",
        "students": [{"id": owner, "name": display_name, "username": owner}],
        "completion_records": [],
        "wrong_book_records": records,
        "explanations": {},
        "assigned_by": assigned_by or owner,
        "assigned_at": datetime.now().isoformat(),
        "legacy_source": "AI伴学 7.9",
        "legacy_username": legacy_username,
    }


def merge_by_id(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int]:
    by_id = {item.get("id"): item for item in existing if isinstance(item, dict) and item.get("id")}
    added = 0
    for item in incoming:
        if item.get("id") in by_id:
            current = by_id[item["id"]]
            for key, value in item.items():
                if key not in current or current.get(key) in ("", None, [], {}):
                    current[key] = value
        else:
            existing.append(item)
            by_id[item["id"]] = item
            added += 1
    return existing, added


def default_user(username: str, real_name: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "username": username,
        "real_name": real_name or username,
        "role": "teacher",
        "status": "active",
        "approval_status": "approved",
        "class_type_ids": [],
        "class_ids": [],
        "expires_at": None,
        "password_hash": "",
        "registration": {},
        "school": "",
        "preferences": "",
        "created_at": datetime.now().isoformat(),
    }


def default_config(username: str) -> dict:
    return {
        "username": username,
        "subject": DEFAULT_SUBJECT,
        "kimi_api_type": "platform",
        "kimi_api_key": "",
        "kimi_model": "kimi-k2.7-code",
        "daily_cost_limit": 10.0,
        "image_max_size_mb": 10,
        "image_compress_quality": 40,
        "image_max_long_edge": 800,
        "kimi_timeout": 120,
        "retry_count": 2,
        "retry_interval": 3,
    }


def migrate(args) -> dict:
    source = args.source.resolve()
    target = args.target.resolve()
    source_users = source / "users"
    source_uploads = source / "uploads"
    target_users = target / "users"
    target_uploads = target / "uploads"
    target_shared = target / "shared"
    user_map = parse_user_map(args.map_user)
    usernames = args.users or legacy_users(source_users)
    report = {
        "users_seen": 0,
        "users_created": 0,
        "materials_added": 0,
        "upload_assets_copied": 0,
        "legacy_distributions_added": 0,
        "legacy_distributions_updated": 0,
        "skipped_users": [],
    }

    distributions_path = target_shared / "material_distributions.json"
    distributions = read_json(distributions_path, [])
    if not isinstance(distributions, list):
        distributions = []

    for legacy_username in usernames:
        report["users_seen"] += 1
        owner = mapped_username(legacy_username, user_map)
        user_profile_path = source_users / f"{legacy_username}.json"
        legacy_profile = read_json(user_profile_path, {})
        display_name = legacy_profile.get("real_name") or legacy_username

        if args.create_users:
            target_user_path = target_users / f"{owner}.json"
            target_config_path = target_users / f"{owner}_config.json"
            if not target_user_path.exists():
                report["users_created"] += 1
                if args.apply:
                    write_json(target_user_path, default_user(owner, display_name))
            if not target_config_path.exists() and args.apply:
                write_json(target_config_path, default_config(owner))

        materials = collect_materials_for_user(source_users, legacy_username, owner, args.class_id, args.class_type_id)
        if not materials:
            report["skipped_users"].append(legacy_username)
            continue

        target_materials_path = target_users / f"{owner}_{DEFAULT_SUBJECT}_materials.json"
        existing_materials = read_json(target_materials_path, [])
        if not isinstance(existing_materials, list):
            existing_materials = []
        merged_materials, added_materials = merge_by_id(existing_materials, materials)
        report["materials_added"] += added_materials
        if args.copy_files:
            for material in materials:
                report["upload_assets_copied"] += copy_upload_assets(source_uploads, target_uploads, material, args.apply)
        if args.apply:
            write_json(target_materials_path, merged_materials)

        wrong_path = source_users / f"{legacy_username}_{DEFAULT_SUBJECT}_wrong_english.json"
        wrong_rows = read_json(wrong_path, [])
        if isinstance(wrong_rows, list):
            distribution = distribution_from_wrong_book(
                legacy_username,
                owner,
                display_name,
                wrong_rows,
                args.class_id,
                args.class_type_id,
                args.assigned_by or owner,
            )
            if distribution:
                before_len = len(distributions)
                distributions, added = merge_by_id(distributions, [distribution])
                if added:
                    report["legacy_distributions_added"] += 1
                elif len(distributions) == before_len:
                    report["legacy_distributions_updated"] += 1

    if args.apply:
        write_json(distributions_path, distributions)
    return report


def build_parser():
    parser = argparse.ArgumentParser(description="Migrate legacy AI伴学 7.9 English data into current data files.")
    parser.add_argument("--source", type=Path, default=Path("AI伴学数据 7.9/AI伴学数据"), help="旧数据目录")
    parser.add_argument("--target", type=Path, default=Path("../AI伴学数据"), help="当前数据目录")
    parser.add_argument("--users", nargs="*", default=[], help="只迁移指定旧用户名；默认迁移所有含英语数据的用户")
    parser.add_argument("--map-user", action="append", default=[], help="用户名映射，格式 old=new，可重复")
    parser.add_argument("--class-id", default="", help="给导入资料和 legacy 错题分发绑定班级")
    parser.add_argument("--class-type-id", default="", help="给导入资料和 legacy 错题分发绑定班型")
    parser.add_argument("--assigned-by", default="", help="legacy 错题分发的 assigned_by，默认使用目标用户名")
    parser.add_argument("--create-users", action="store_true", help="目标用户不存在时创建教师账号骨架")
    parser.add_argument("--copy-files", action="store_true", help="复制旧 uploads 中的原文件和文本缓存")
    parser.add_argument("--apply", action="store_true", help="实际写入；不加时只 dry-run")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.source.exists():
        parser.error(f"旧数据目录不存在: {args.source}")
    report = migrate(args)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] legacy English migration report")
    for key, value in report.items():
        print(f"{key}: {value}")
    if not args.apply:
        print("未写入任何文件；确认报告后加 --apply 执行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
