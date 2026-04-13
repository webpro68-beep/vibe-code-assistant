from __future__ import annotations

from pydantic import BaseModel


class StoredObject(BaseModel):
    bucket: str
    key: str
    etag: str | None = None
    public_url: str | None = None
    signed_url: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None