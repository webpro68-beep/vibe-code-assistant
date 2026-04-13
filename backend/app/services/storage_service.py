from __future__ import annotations

import mimetypes
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# Optional SDK imports. Chỉ cần cài khi dùng thật.
try:
    import boto3
except Exception:  # pragma: no cover
    boto3 = None

try:
    from google.cloud import storage as gcs_storage
except Exception:  # pragma: no cover
    gcs_storage = None


@dataclass
class StorageUploadResult:
    storage_key: str
    url: str | None
    content_type: str | None = None
    size_bytes: int | None = None


class StorageAdapter(Protocol):
    def upload_file(
        self,
        *,
        local_path: str,
        object_key: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        ...


class LocalStorageAdapter:
    def __init__(
        self,
        *,
        storage_root: str = "storage",
        public_base_url: str = "http://localhost:8000",
    ) -> None:
        self.storage_root = Path(storage_root)
        self.public_base_url = public_base_url.rstrip("/")
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def upload_file(
        self,
        *,
        local_path: str,
        object_key: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        src = Path(local_path)
        if not src.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        dst = self.storage_root / object_key
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        guessed_content_type = content_type or mimetypes.guess_type(str(dst))[0]
        relative_path = dst.relative_to(self.storage_root).as_posix()

        result = StorageUploadResult(
            storage_key=object_key,
            url=f"{self.public_base_url}/storage/{relative_path}",
            content_type=guessed_content_type,
            size_bytes=dst.stat().st_size,
        )
        return result.__dict__


class S3StorageAdapter:
    def __init__(
        self,
        *,
        bucket: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        if boto3 is None:
            raise RuntimeError("boto3 is required for S3/MinIO storage")

        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def upload_file(
        self,
        *,
        local_path: str,
        object_key: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        guessed_content_type = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"

        extra_args = {"ContentType": guessed_content_type}
        self.client.upload_file(str(path), self.bucket, object_key, ExtraArgs=extra_args)

        if self.public_base_url:
            url = f"{self.public_base_url}/{object_key}"
        elif self.endpoint_url:
            url = f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{object_key}"
        else:
            region_part = f".{self.region}" if self.region else ""
            url = f"https://{self.bucket}.s3{region_part}.amazonaws.com/{object_key}"

        result = StorageUploadResult(
            storage_key=object_key,
            url=url,
            content_type=guessed_content_type,
            size_bytes=path.stat().st_size,
        )
        return result.__dict__


class GCSStorageAdapter:
    def __init__(
        self,
        *,
        bucket: str,
        public_base_url: str | None = None,
    ) -> None:
        if gcs_storage is None:
            raise RuntimeError("google-cloud-storage is required for GCS storage")

        self.bucket_name = bucket
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.client = gcs_storage.Client()
        self.bucket = self.client.bucket(bucket)

    def upload_file(
        self,
        *,
        local_path: str,
        object_key: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        guessed_content_type = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"

        blob = self.bucket.blob(object_key)
        blob.upload_from_filename(str(path), content_type=guessed_content_type)

        if self.public_base_url:
            url = f"{self.public_base_url}/{object_key}"
        else:
            url = f"https://storage.googleapis.com/{self.bucket_name}/{object_key}"

        result = StorageUploadResult(
            storage_key=object_key,
            url=url,
            content_type=guessed_content_type,
            size_bytes=path.stat().st_size,
        )
        return result.__dict__


def get_storage_service() -> StorageAdapter:
    """
    ENV:
    - STORAGE_BACKEND=local|s3|minio|gcs
    """
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()

    if backend == "local":
        return LocalStorageAdapter(
            storage_root=os.getenv("STORAGE_ROOT", "storage"),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000"),
        )

    if backend in {"s3", "minio"}:
        return S3StorageAdapter(
            bucket=os.getenv("STORAGE_BUCKET", ""),
            region=os.getenv("AWS_REGION"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            public_base_url=os.getenv("STORAGE_PUBLIC_BASE_URL"),
        )

    if backend == "gcs":
        return GCSStorageAdapter(
            bucket=os.getenv("GCS_BUCKET", ""),
            public_base_url=os.getenv("STORAGE_PUBLIC_BASE_URL"),
        )

    raise ValueError(f"Unsupported STORAGE_BACKEND: {backend}")