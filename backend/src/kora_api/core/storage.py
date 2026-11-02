"""Object storage for task files: S3-compatible, reached only through short-lived presigned URLs.

Files never pass through the API (serverless request bodies are small); clients upload and download
straight to the bucket. The signing is plain AWS Signature V4 (query authentication) written with
the standard library, so no SDK is added. The bucket must be private.
"""

import asyncio
import hashlib
import hmac
import urllib.error
import urllib.request
from datetime import datetime
from typing import Protocol
from urllib.parse import quote, urlsplit

from fastapi import Request

from kora_api.core import clock
from kora_api.core.config import Settings

UPLOAD_URL_SECONDS = 600
DOWNLOAD_URL_SECONDS = 120


class ObjectStorage(Protocol):
    def upload_url(self, key: str) -> str:
        """A presigned PUT URL for the object."""
        ...

    def download_url(self, key: str, *, filename: str) -> str:
        """A presigned GET URL that forces a download (never rendered in the browser)."""
        ...

    async def size_of(self, key: str) -> int | None:
        """The stored object's size, or None when it does not exist."""
        ...


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def _encode(value: str) -> str:
    return quote(value, safe="-_.~")


class S3Storage:
    """Path-style S3-compatible storage (AWS S3, Cloudflare R2, MinIO, Neon object storage)."""

    def __init__(
        self, *, endpoint: str, bucket: str, region: str, access_key_id: str, secret_access_key: str
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._host = urlsplit(self._endpoint).netloc
        self._bucket = bucket
        self._region = region
        self._access_key_id = access_key_id
        self._secret = secret_access_key

    def _presign(
        self,
        method: str,
        key: str,
        expires: int,
        extra: dict[str, str] | None = None,
        at: datetime | None = None,
    ) -> str:
        now = at or clock.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        day = now.strftime("%Y%m%d")
        scope = f"{day}/{self._region}/s3/aws4_request"
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self._access_key_id}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": "host",
            **(extra or {}),
        }
        path = f"/{self._bucket}/" + "/".join(_encode(part) for part in key.split("/"))
        canonical_query = "&".join(f"{_encode(k)}={_encode(v)}" for k, v in sorted(query.items()))
        canonical = "\n".join(
            [method, path, canonical_query, f"host:{self._host}\n", "host", "UNSIGNED-PAYLOAD"]
        )
        to_sign = "\n".join(
            ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()]
        )
        signing_key = _hmac(
            _hmac(_hmac(_hmac(f"AWS4{self._secret}".encode(), day), self._region), "s3"),
            "aws4_request",
        )
        signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
        return f"{self._endpoint}{path}?{canonical_query}&X-Amz-Signature={signature}"

    def upload_url(self, key: str) -> str:
        return self._presign("PUT", key, UPLOAD_URL_SECONDS)

    def download_url(self, key: str, *, filename: str) -> str:
        safe = filename.replace('"', "").replace("\\", "")
        return self._presign(
            "GET",
            key,
            DOWNLOAD_URL_SECONDS,
            {
                "response-content-disposition": f"attachment; filename*=UTF-8''{_encode(safe)}",
                "response-content-type": "application/octet-stream",
            },
        )

    async def size_of(self, key: str) -> int | None:
        url = self._presign("HEAD", key, 60)

        def _head() -> int | None:
            request = urllib.request.Request(url, method="HEAD")
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    return int(response.headers.get("Content-Length", "0"))
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 404):
                    return None
                raise

        return await asyncio.to_thread(_head)


def build_storage(settings: Settings) -> ObjectStorage | None:
    """None when storage is not configured: file endpoints then answer 503."""
    if not settings.storage_configured:
        return None
    assert settings.storage_endpoint and settings.storage_bucket
    assert settings.storage_access_key_id and settings.storage_secret_access_key
    return S3Storage(
        endpoint=settings.storage_endpoint,
        bucket=settings.storage_bucket,
        region=settings.storage_region,
        access_key_id=settings.storage_access_key_id.get_secret_value(),
        secret_access_key=settings.storage_secret_access_key.get_secret_value(),
    )


def get_storage(request: Request) -> ObjectStorage | None:
    storage: ObjectStorage | None = request.app.state.storage
    return storage
