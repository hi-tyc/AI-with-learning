import hashlib
import os
from datetime import datetime
from fastapi import HTTPException
from app.core.paths import DATA_DIR
from app.utils.file_lock import read_json, write_json

ADMIN_FILE = os.path.join(DATA_DIR, "admin.json")
DEFAULT_PASSWORD = "admin123"
SALT = "studybuddysalt_v1"


def _hash(password: str) -> str:
    return hashlib.sha256(f"{SALT}_{password}".encode()).hexdigest()


async def get_admin_config() -> dict:
    config = await read_json(ADMIN_FILE)
    if config is None:
        config = {
            "password_hash": _hash(DEFAULT_PASSWORD),
            "created_at": datetime.now().isoformat(),
            "password_changed_at": None,
        }
        await write_json(ADMIN_FILE, config)
    return config


async def verify_admin_password(password: str) -> bool:
    config = await get_admin_config()
    return config.get("password_hash") == _hash(password)


async def change_admin_password(old_password: str, new_password: str) -> bool:
    if not await verify_admin_password(old_password):
        return False
    config = await get_admin_config()
    config["password_hash"] = _hash(new_password)
    config["password_changed_at"] = datetime.now().isoformat()
    await write_json(ADMIN_FILE, config)
    return True
