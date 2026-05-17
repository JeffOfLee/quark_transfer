from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigError


@dataclass(frozen=True)
class S3Config:
    bucket: str
    prefix: str = ""
    region: str | None = None
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None


@dataclass(frozen=True)
class AppConfig:
    quark_cookie: str | None = None
    s3: S3Config | None = None


def load_app_config(path: str | Path | None) -> AppConfig:
    if path is None:
        return AppConfig()

    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    quark = _section(data, "quark")
    s3 = _section(data, "s3")

    s3_config = None
    if s3:
        bucket = _string(s3, "bucket")
        if not bucket:
            raise ConfigError("s3.bucket is required when [s3] is configured.")
        s3_config = S3Config(
            bucket=bucket,
            prefix=_string(s3, "prefix") or "",
            region=_string(s3, "region"),
            endpoint_url=_string(s3, "endpoint_url") or None,
            access_key_id=_string(s3, "access_key_id"),
            secret_access_key=_string(s3, "secret_access_key"),
        )

    return AppConfig(quark_cookie=_string(quark, "cookie"), s3=s3_config)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a TOML table.")
    return value


def _string(data: dict[str, Any], name: str) -> str | None:
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string.")
    stripped = value.strip()
    return stripped or None

