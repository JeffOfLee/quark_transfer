from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import S3Config


class S3Client(Protocol):
    def upload_file(self, filename: str, bucket: str, key: str) -> None: ...


@dataclass(frozen=True)
class UploadResult:
    key: str
    bytes_uploaded: int
    start_time: float
    end_time: float

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def bytes_per_second(self) -> float:
        duration = self.duration_seconds
        if duration <= 0:
            return 0.0
        return self.bytes_uploaded / duration


class S3Uploader:
    def __init__(self, config: S3Config, *, client: S3Client | None = None):
        self.config = config
        self.client = client or self._build_client(config)

    def upload_file(self, file_path: str | Path, *, hash_source: str, clock=time.time) -> UploadResult:
        path = Path(file_path)
        key = _join_key(self.config.prefix, _hashed_name(hash_source, path.suffix))
        start_time = clock()
        self.client.upload_file(str(path), self.config.bucket, key)
        end_time = clock()
        return UploadResult(
            key=key,
            bytes_uploaded=path.stat().st_size,
            start_time=start_time,
            end_time=end_time,
        )

    def _build_client(self, config: S3Config) -> S3Client:
        import boto3

        kwargs = {}
        if config.region:
            kwargs["region_name"] = config.region
        if config.endpoint_url:
            kwargs["endpoint_url"] = config.endpoint_url
        if config.access_key_id:
            kwargs["aws_access_key_id"] = config.access_key_id
        if config.secret_access_key:
            kwargs["aws_secret_access_key"] = config.secret_access_key
        return boto3.client("s3", **kwargs)


def _join_key(prefix: str, relative_path: str) -> str:
    clean_prefix = prefix.strip("/")
    if not clean_prefix:
        return relative_path
    return f"{clean_prefix}/{relative_path}"


def _hashed_name(hash_source: str, suffix: str) -> str:
    digest = hashlib.sha256(hash_source.encode("utf-8")).hexdigest()
    return f"{digest}{suffix}"
