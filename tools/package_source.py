#!/usr/bin/env python3
"""Create a clean source-only zip from the committed Git revision."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a source-only StudyBuddy zip archive.")
    parser.add_argument("--output-dir", default="build/source", help="Output directory relative to the repository root")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow creating an archive from HEAD when tracked changes are uncommitted")
    args = parser.parse_args()

    try:
        dirty = git_output("status", "--porcelain", "--untracked-files=no")
        commit = git_output("rev-parse", "--short", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Git repository is required: {error}", file=sys.stderr)
        return 1

    if dirty and not args.allow_dirty:
        print("Tracked changes are uncommitted. Commit them before packaging, or pass --allow-dirty.", file=sys.stderr)
        return 1

    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now().strftime("%Y%m%d")
    archive_name = f"StudyBuddy-source-{date_stamp}-{commit}.zip"
    archive_path = output_dir / archive_name
    prefix = f"StudyBuddy-source-{commit}/"

    try:
        subprocess.run(
            ["git", "archive", "--format=zip", f"--prefix={prefix}", "-o", str(archive_path), "HEAD"],
            cwd=ROOT,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Could not create source archive: {error}", file=sys.stderr)
        return 1

    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
