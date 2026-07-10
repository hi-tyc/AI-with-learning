import os
from app.core.paths import USERS_DIR, MEMORY_DIR
from app.utils.file_lock import read_json, write_json


def _upath(username: str, *suffixes: str) -> str:
    """构建用户数据文件路径（字符串拼接避免 Path 编码 bug）。"""
    return os.path.join(USERS_DIR, f"{username}_{'_'.join(suffixes)}.json")


def get_user_path(username: str) -> str:
    return os.path.join(USERS_DIR, f"{username}.json")


def get_user_config_path(username: str) -> str:
    return os.path.join(USERS_DIR, f"{username}_config.json")


async def get_user_subject(username: str) -> str:
    config = await read_json(get_user_config_path(username)) or {}
    return config.get("subject", "英语")


async def set_user_subject(username: str, subject: str) -> None:
    config = await read_json(get_user_config_path(username)) or {}
    config["subject"] = subject
    await write_json(get_user_config_path(username), config)


def user_data_path(username: str, subject: str, suffix: str) -> str:
    return _upath(username, subject, suffix)


def get_problems_path(username: str, subject: str) -> str:
    return _upath(username, subject, "problems")


def get_wrong_path(username: str, subject: str) -> str:
    return _upath(username, subject, "wrong")


def get_sessions_path(username: str, subject: str) -> str:
    return _upath(username, subject, "sessions")


def get_usage_path(username: str, subject: str) -> str:
    return _upath(username, subject, "usage")


def get_solve_sessions_path(username: str, subject: str) -> str:
    return _upath(username, subject, "solve_sessions")


def get_materials_path(username: str, subject: str) -> str:
    return _upath(username, subject, "materials")


def get_answers_path(username: str, subject: str) -> str:
    return _upath(username, subject, "answers")

def get_words_path(username: str, subject: str) -> str:
    return _upath(username, subject, "words")


def get_trash_path(username: str, subject: str) -> str:
    return _upath(username, subject, "trash")

def get_library_trash_path(username: str, subject: str) -> str:
    return _upath(username, subject, "library_trash")

def get_wrong_english_path(username: str, subject: str) -> str:
    return _upath(username, subject, "wrong_english")

def get_problem_answer_map_path(username: str, subject: str) -> str:
    return _upath(username, subject, "problem_answer_map")


def get_memory_path(username: str) -> str:
    return os.path.join(MEMORY_DIR, f"{username}_daily.json")


# 旧格式兼容
async def read_user_data(username: str, subject: str, suffix: str) -> list | None:
    new_path = user_data_path(username, subject, suffix)
    data = await read_json(new_path)
    if data is not None:
        return data
    old_path = os.path.join(USERS_DIR, f"{username}_{suffix}.json")
    return await read_json(old_path)


async def migrate_old_user_data(username: str, subject: str, suffix: str) -> None:
    old_path = os.path.join(USERS_DIR, f"{username}_{suffix}.json")
    new_path = user_data_path(username, subject, suffix)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        data = await read_json(old_path)
        if data:
            await write_json(new_path, data)
