from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR / ".env.dev")
except Exception:
    pass

from app.db.base import Base

# import all models explicitly
from app.models.provider_webhook_event import ProviderWebhookEvent
from app.models.render_job import RenderJob
from app.models.render_scene_task import RenderSceneTask


target_metadata = Base.metadata

def include_object(object_, name, type_, reflected, compare_to):
    return True


def process_revision_directives(context, revision, directives):
    if getattr(config.cmd_opts, "autogenerate", False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            print("No schema changes detected.")


def get_database_url() -> str:
    return os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")


def include_object(object_, name, type_, reflected, compare_to):
    # bỏ qua bảng Alembic nội bộ thì không cần filter
    return True


def run_migrations_offline() -> None:
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
            render_as_batch=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    context.configure(
    url=url,
    target_metadata=target_metadata,
    literal_binds=True,
    compare_type=True,
    compare_server_default=True,
    include_object=include_object,
    process_revision_directives=process_revision_directives,
)
    run_migrations_offline()
else:
    context.configure(
    connection=connection,
    target_metadata=target_metadata,
    compare_type=True,
    compare_server_default=True,
    include_object=include_object,
    process_revision_directives=process_revision_directives,
    render_as_batch=False,
)
    run_migrations_online()