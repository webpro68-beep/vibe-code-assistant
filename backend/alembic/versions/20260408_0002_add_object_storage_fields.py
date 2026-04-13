"""add object storage fields

Revision ID: 20260408_0002
Revises: 20260408_0001
Create Date: 2026-04-08 00:02:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260408_0002"
down_revision = "20260408_0001"
branch_labels = None
depends_on = None


OBJECT_STORAGE_COLUMNS = [
    sa.Column("storage_provider", sa.Text(), nullable=True),
    sa.Column("storage_bucket", sa.Text(), nullable=True),
    sa.Column("storage_key", sa.Text(), nullable=True),
    sa.Column("storage_region", sa.Text(), nullable=True),
    sa.Column("storage_url", sa.Text(), nullable=True),
    sa.Column("storage_etag", sa.Text(), nullable=True),
    sa.Column("storage_version_id", sa.Text(), nullable=True),
    sa.Column("content_type", sa.Text(), nullable=True),
    sa.Column("content_length_bytes", sa.BigInteger(), nullable=True),
    sa.Column("checksum_sha256", sa.Text(), nullable=True),
]


def _has_table(bind, table_name: str) -> bool:
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _get_column_names(bind, table_name: str) -> set[str]:
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _add_columns_if_missing(table_name: str) -> None:
    bind = op.get_bind()
    if not _has_table(bind, table_name):
        return

    existing = _get_column_names(bind, table_name)

    with op.batch_alter_table(table_name) as batch_op:
        for col in OBJECT_STORAGE_COLUMNS:
            if col.name not in existing:
                batch_op.add_column(col)


def _drop_columns_if_exist(table_name: str) -> None:
    bind = op.get_bind()
    if not _has_table(bind, table_name):
        return

    existing = _get_column_names(bind, table_name)

    with op.batch_alter_table(table_name) as batch_op:
        for col in reversed(OBJECT_STORAGE_COLUMNS):
            if col.name in existing:
                batch_op.drop_column(col.name)


def upgrade() -> None:
    # Các bảng thường chứa artifact/output trong Render Core
    # Có thể tồn tại hoặc không tùy phiên bản repo hiện tại.
    target_tables = [
        "scene_tasks",
        "render_jobs",
        "exports",
        "uploads",
        "project_assets",
        "scene_assets",
    ]

    for table_name in target_tables:
        _add_columns_if_missing(table_name)

    bind = op.get_bind()

    # Index có điều kiện: chỉ tạo nếu bảng/cột tồn tại
    if _has_table(bind, "scene_tasks"):
        cols = _get_column_names(bind, "scene_tasks")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.create_index(
                "ix_scene_tasks_storage_bucket_key",
                "scene_tasks",
                ["storage_bucket", "storage_key"],
                unique=False,
            )

    if _has_table(bind, "render_jobs"):
        cols = _get_column_names(bind, "render_jobs")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.create_index(
                "ix_render_jobs_storage_bucket_key",
                "render_jobs",
                ["storage_bucket", "storage_key"],
                unique=False,
            )

    if _has_table(bind, "exports"):
        cols = _get_column_names(bind, "exports")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.create_index(
                "ix_exports_storage_bucket_key",
                "exports",
                ["storage_bucket", "storage_key"],
                unique=False,
            )

    if _has_table(bind, "uploads"):
        cols = _get_column_names(bind, "uploads")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.create_index(
                "ix_uploads_storage_bucket_key",
                "uploads",
                ["storage_bucket", "storage_key"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "uploads"):
        cols = _get_column_names(bind, "uploads")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.drop_index("ix_uploads_storage_bucket_key", table_name="uploads")

    if _has_table(bind, "exports"):
        cols = _get_column_names(bind, "exports")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.drop_index("ix_exports_storage_bucket_key", table_name="exports")

    if _has_table(bind, "render_jobs"):
        cols = _get_column_names(bind, "render_jobs")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.drop_index("ix_render_jobs_storage_bucket_key", table_name="render_jobs")

    if _has_table(bind, "scene_tasks"):
        cols = _get_column_names(bind, "scene_tasks")
        if {"storage_bucket", "storage_key"}.issubset(cols):
            op.drop_index("ix_scene_tasks_storage_bucket_key", table_name="scene_tasks")

    target_tables = [
        "scene_assets",
        "project_assets",
        "uploads",
        "exports",
        "render_jobs",
        "scene_tasks",
    ]

    for table_name in target_tables:
        _drop_columns_if_exist(table_name)