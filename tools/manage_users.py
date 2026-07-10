#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("STUDYBUDDY_PROJECT_ROOT", str(ROOT_DIR))
os.environ.setdefault("STUDYBUDDY_BACKEND_DIR", str(BACKEND_DIR))

from app.api.endpoints.auth import _default_user  # noqa: E402
from app.core.paths import USERS_DIR  # noqa: E402


def load_user(username: str):
    path = Path(USERS_DIR) / f"{username}.json"
    if not path.exists():
        return path, None
    return path, json.loads(path.read_text(encoding="utf-8"))


def save_user(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_promote_admin(args):
    path, data = load_user(args.username)
    if data is None:
        data = _default_user(args.username, role="admin", real_name=args.username)
    data["role"] = "admin"
    data["status"] = "active"
    data["approval_status"] = "approved"
    save_user(path, data)
    print(f"已将 {args.username} 设置为管理员")


def cmd_set_role(args):
    path, data = load_user(args.username)
    if data is None:
        data = _default_user(args.username, role=args.role, real_name=args.real_name or args.username)
    data["role"] = args.role
    if args.real_name:
        data["real_name"] = args.real_name
    if args.activate:
        data["status"] = "active"
        data["approval_status"] = "approved"
    save_user(path, data)
    print(f"已将 {args.username} 设置为 {args.role}")


def build_parser():
    parser = argparse.ArgumentParser(description="StudyBuddy 用户管理工具")
    sub = parser.add_subparsers(dest="command", required=True)

    promote = sub.add_parser("promote-admin", help="将用户提升为管理员")
    promote.add_argument("username")
    promote.set_defaults(func=cmd_promote_admin)

    role = sub.add_parser("set-role", help="设置用户角色")
    role.add_argument("username")
    role.add_argument("role", choices=["admin", "teacher", "student"])
    role.add_argument("--real-name", default="")
    role.add_argument("--activate", action="store_true")
    role.set_defaults(func=cmd_set_role)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
