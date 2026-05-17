from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .config import S3Config


class S3Client(Protocol):
    def upload_file(self, filename: str, bucket: str, key: str) -> None: ...


class S3Uploader:
    def __init__(self, config: S3Config, *, client: S3Client | None = None):
        self.config = config
        self.client = client or self._build_client(config)

    def upload_file(self, file_path: str | Path, *, relative_to: str | Path) -> str:
        path = Path(file_path)
        relative_path = path.relative_to(relative_to).as_posix()
        key = _join_key(self.config.prefix, relative_path)
        self.client.upload_file(str(path), self.config.bucket, key)
        return key

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
