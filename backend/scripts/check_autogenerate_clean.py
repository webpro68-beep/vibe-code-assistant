from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

BASE_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    config = Config(str(BASE_DIR / "alembic.ini"))
    versions_dir = BASE_DIR / "alembic" / "versions"
    before = {p.name for p in versions_dir.glob("*.py")}

    command.revision(config, message="ci_tmp_check", autogenerate=True)

    after = {p.name for p in versions_dir.glob("*.py")}
    new_files = sorted(after - before)

    if not new_files:
        print("No autogenerate file created.")
        return 0

    latest = versions_dir / new_files[-1]
    content = latest.read_text(encoding="utf-8")

    latest.unlink(missing_ok=True)

    if "pass" in content and "def upgrade() -> None:\n    pass" in content:
        print("No schema drift detected.")
        return 0

    print("Schema drift detected. Missing migration for model changes.")
    print(content)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())