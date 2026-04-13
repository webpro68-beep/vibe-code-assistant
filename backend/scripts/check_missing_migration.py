from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

# import app metadata
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.db.base import Base
from app.models import ProviderWebhookEvent, RenderJob, RenderSceneTask  # noqa: F401


def main() -> int:
    database_url = (
        __import__("os").environ.get("DATABASE_URL")
        or "postgresql+psycopg://postgres:postgres@localhost:5432/render_factory"
    )

    engine = create_engine(database_url)

    config = Config(str(BASE_DIR / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()
        heads = script.get_heads()

        print(f"Current DB revision: {current_rev}")
        print(f"Alembic heads: {heads}")

        if len(heads) != 1:
            print("FAIL: multiple heads detected")
            return 1

        if current_rev != heads[0]:
            print("FAIL: database is not at head revision")
            return 1

    print("Migration state looks OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())