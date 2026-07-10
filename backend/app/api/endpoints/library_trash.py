from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import os

from app.api.endpoints.auth import get_current_user
from app.api.endpoints.match_answers import cleanup_matches_after_deletion
from app.core.user_data import get_user_subject, get_materials_path, get_answers_path, get_library_trash_path
from app.core.paths import UPLOAD_DIR
from app.utils.file_lock import read_json, write_json

router = APIRouter()


@router.get("")
async def list_trash(
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    trash = await read_json(get_library_trash_path(username, subject)) or []
    trash.reverse()
    return {"items": trash, "total": len(trash)}


@router.post("/restore")
async def restore_from_trash(
    data: dict,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="未指定ID")
    trash_path = get_library_trash_path(username, subject)
    trash = await read_json(trash_path) or []
    ids_set = set(ids)
    restored = [t for t in trash if t["id"] in ids_set]
    trash = [t for t in trash if t["id"] not in ids_set]
    if not restored:
        raise HTTPException(status_code=404, detail="未找到要恢复的项目")
    await write_json(trash_path, trash)
    for r in restored:
        r.pop("trashed_at", None)
        origin = r.pop("_origin_type", "material")
        if origin == "material":
            materials = await read_json(get_materials_path(username, subject)) or []
            materials.append(r)
            await write_json(get_materials_path(username, subject), materials)
        elif origin == "answer":
            answers = await read_json(get_answers_path(username, subject)) or []
            answers.append(r)
            await write_json(get_answers_path(username, subject), answers)
    return {"message": f"已恢复 {len(restored)} 项"}


@router.post("/empty")
async def empty_trash(
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    trash = await read_json(get_library_trash_path(username, subject)) or []
    await write_json(get_library_trash_path(username, subject), [])
    # Also clean up files for permanently deleted materials
    for item in trash:
        if item.get("_origin_type") == "material":
            fp = item.get("file_path", "")
            if fp and os.path.exists(fp):
                try:
                    os.unlink(fp)
                except Exception:
                    pass
            text_fp = os.path.join(UPLOAD_DIR, f"{item['id']}_text.txt")
            if os.path.exists(text_fp):
                try:
                    os.unlink(text_fp)
                except Exception:
                    pass
    await cleanup_matches_after_deletion(username, subject)
    return {"message": f"已永久删除 {len(trash)} 项"}


@router.delete("/{item_id}")
async def delete_trash_item(
    item_id: str,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    trash_path = get_library_trash_path(username, subject)
    trash = await read_json(trash_path) or []
    target = None
    for t in trash:
        if t["id"] == item_id:
            target = t
            break
    if not target:
        raise HTTPException(status_code=404, detail="废纸篓中未找到该项目")
    trash = [t for t in trash if t["id"] != item_id]
    await write_json(trash_path, trash)
    if target.get("_origin_type") == "material":
        fp = target.get("file_path", "")
        if fp and os.path.exists(fp):
            try:
                os.unlink(fp)
            except Exception:
                pass
        text_fp = os.path.join(UPLOAD_DIR, f"{item_id}_text.txt")
        if os.path.exists(text_fp):
            try:
                os.unlink(text_fp)
            except Exception:
                pass
    await cleanup_matches_after_deletion(username, subject)
    return {"message": "已永久删除"}
