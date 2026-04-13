from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]
    config = Config(str(base_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()
    if len(heads) != 1:
        print(f"Expected exactly 1 Alembic head, found {len(heads)}: {heads}")
        return 1

    print(f"Alembic head OK: {heads[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())