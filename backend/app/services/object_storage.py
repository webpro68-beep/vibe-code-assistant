from __future__ import annotations

import mimetypes
from pathlib import Path

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import settings
from app.schemas.storage import StoredObject


def build_s3_client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def guess_content_type(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def build_public_url(key: str) -> str | None:
    if not settings.s3_public_base_url:
        return None
    return f"{settings.s3_public_base_url.rstrip('/')}/{key}"


def upload_file_to_object_storage(
    *,
    local_path: str,
    key: str,
    content_type: str | None = None,
) -> StoredObject:
    client = build_s3_client()
    path = Path(local_path)

    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    else:
        extra_args["ContentType"] = guess_content_type(local_path)

    client.upload_file(
        Filename=str(path),
        Bucket=settings.s3_bucket_name,
        Key=key,
        ExtraArgs=extra_args,
    )

    head = client.head_object(Bucket=settings.s3_bucket_name, Key=key)

    return StoredObject(
        bucket=settings.s3_bucket_name,
        key=key,
        etag=(head.get("ETag") or "").replace('"', "") or None,
        public_url=build_public_url(key),
        content_type=head.get("ContentType"),
        size_bytes=head.get("ContentLength"),
    )