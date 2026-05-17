from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class VipAccelMode(StrEnum):
    AUTO = "auto"
    ON = "on"
    OFF = "off"


@dataclass(frozen=True)
class CloudItem:
    fid: str
    name: str
    size: int
    is_folder: bool
    parent_fid: str | None = None


@dataclass(frozen=True)
class DownloadRecord:
    fid: str
    name: str
    size: int
    relative_dir: PurePosixPath = PurePosixPath(".")


@dataclass(frozen=True)
class DownloadUrl:
    url: str
    accelerated: bool = False
    headers: dict[str, str] | None = None
