"""
File storage — local disk (dev), Azure Blob (production), or S3-compatible.
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Optional

import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "text/plain", "text/csv",
    "application/json",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE_MB = 50


# Magic-byte signatures for the formats we accept. Used to verify the
# client-supplied mime_type matches the actual file contents and to prevent
# extension/MIME-type spoofing (e.g. an HTML payload masquerading as PNG).
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # additionally requires "WEBP" at offset 8
    "application/pdf": (b"%PDF-",),
    "application/zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (b"PK\x03\x04",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
}

# Map sniffed magic bytes back to canonical extension to prevent
# `evil.png.html`-style filename tricks.
_MIME_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/json": ".json",
}


def sniff_mime(content: bytes, declared: str) -> Optional[str]:
    """Return the verified mime type if `content` matches `declared`'s magic
    bytes. Text-ish formats (text/plain, text/csv, application/json) are not
    sniffable and are accepted as declared.
    """
    if declared in ("text/plain", "text/csv", "application/json"):
        return declared
    sigs = _MAGIC_SIGNATURES.get(declared)
    if not sigs:
        return None
    if not any(content.startswith(sig) for sig in sigs):
        return None
    if declared == "image/webp":
        # RIFF<size>WEBP — the "WEBP" tag must appear at offset 8.
        if len(content) < 12 or content[8:12] != b"WEBP":
            return None
    return declared


async def read_upload_capped(file, max_bytes: int) -> bytes:
    """Stream a Starlette UploadFile in chunks and abort once `max_bytes` is
    exceeded. Prevents memory exhaustion from clients that omit Content-Length
    or send chunked transfer encoding.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB maximum size.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


class StorageService:
    """Abstract file storage — local or cloud-backed."""

    def __init__(self):
        self._backend = settings.file_storage_backend  # "local" | "azure" | "s3"
        self._local_root = Path(settings.local_storage_path)
        self._local_root.mkdir(parents=True, exist_ok=True)
        self._base_url = settings.app_url

    def _local_path(self, tenant_id: str, filename: str) -> Path:
        tenant_dir = self._local_root / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir / filename

    def _public_url(self, tenant_id: str, filename: str) -> str:
        return f"{self._base_url}/uploads/{tenant_id}/{filename}"

    async def save_file(
        self,
        content: bytes,
        original_filename: str,
        mime_type: str,
        tenant_id: str,
    ) -> dict:
        """Store a file and return its metadata."""
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"File type '{mime_type}' is not allowed.")
        size_mb = len(content) / 1_048_576
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"File too large ({size_mb:.1f} MB). Max {MAX_FILE_SIZE_MB} MB.")

        # Verify the declared mime_type against the file's magic bytes. This
        # blocks extension/MIME spoofing where a script payload is uploaded
        # under an image MIME and later served back inline.
        verified = sniff_mime(content, mime_type)
        if verified is None:
            raise ValueError("File contents do not match the declared file type.")

        # Force-derive the extension from the verified type rather than trust
        # whatever the client sent in `original_filename`.
        ext = _MIME_EXTENSIONS.get(verified, Path(original_filename).suffix.lower() or "")
        unique_name = f"{uuid.uuid4().hex}{ext}"

        if self._backend == "azure":
            url = await self._save_azure(content, tenant_id, unique_name, mime_type)
        elif self._backend == "s3":
            url = await self._save_s3(content, tenant_id, unique_name, mime_type)
        else:
            path = self._local_path(tenant_id, unique_name)
            await asyncio.to_thread(path.write_bytes, content)
            url = self._public_url(tenant_id, unique_name)

        return {
            "filename": unique_name,
            "original_filename": original_filename,
            "url": url,
            "mime_type": mime_type,
            "size_bytes": len(content),
        }

    async def delete_file(self, tenant_id: str, filename: str) -> None:
        if self._backend == "local":
            path = self._local_path(tenant_id, filename)
            if path.exists():
                path.unlink()
        elif self._backend == "azure":
            await self._delete_azure(tenant_id, filename)
        elif self._backend == "s3":
            await self._delete_s3(tenant_id, filename)

    async def _save_azure(
        self, content: bytes, tenant_id: str, filename: str, mime_type: str
    ) -> str:
        from azure.storage.blob.aio import BlobServiceClient

        conn_str = settings.azure_storage_connection_string
        container = settings.azure_storage_container_name
        blob_path = f"{tenant_id}/{filename}"
        async with BlobServiceClient.from_connection_string(conn_str) as client:
            container_client = client.get_container_client(container)
            blob_client = container_client.get_blob_client(blob_path)
            await blob_client.upload_blob(content, overwrite=True, content_settings={"content_type": mime_type})
        account_name = settings.azure_storage_account_name
        return f"https://{account_name}.blob.core.windows.net/{container}/{blob_path}"

    async def _delete_azure(self, tenant_id: str, filename: str) -> None:
        from azure.storage.blob.aio import BlobServiceClient

        conn_str = settings.azure_storage_connection_string
        container = settings.azure_storage_container_name
        async with BlobServiceClient.from_connection_string(conn_str) as client:
            await client.get_blob_client(container, f"{tenant_id}/{filename}").delete_blob()

    async def _save_s3(
        self, content: bytes, tenant_id: str, filename: str, mime_type: str
    ) -> str:
        import boto3

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        bucket = settings.s3_bucket_name
        key = f"{tenant_id}/{filename}"
        s3.put_object(Bucket=bucket, Key=key, Body=content, ContentType=mime_type)
        return f"https://{bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"

    async def _delete_s3(self, tenant_id: str, filename: str) -> None:
        import boto3

        s3 = boto3.client("s3", aws_access_key_id=settings.aws_access_key_id,
                          aws_secret_access_key=settings.aws_secret_access_key,
                          region_name=settings.aws_region)
        s3.delete_object(Bucket=settings.s3_bucket_name, Key=f"{tenant_id}/{filename}")


# Singleton
storage_service = StorageService()
