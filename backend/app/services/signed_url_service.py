from __future__ import annotations

from app.core.config import settings
from app.services.object_storage import build_s3_client


def generate_download_signed_url(
    *,
    key: str,
    expires_seconds: int | None = None,
    filename: str | None = None,
) -> str:
    client = build_s3_client()

    params = {
        "Bucket": settings.s3_bucket_name,
        "Key": key,
    }

    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params=params,
        ExpiresIn=expires_seconds or settings.signed_url_expires_seconds,
    )


def generate_upload_signed_url(
    *,
    key: str,
    content_type: str,
    expires_seconds: int | None = None,
) -> str:
    client = build_s3_client()

    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_seconds or settings.signed_url_expires_seconds,
    )