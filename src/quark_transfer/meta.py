from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class MetaRow:
    path: str
    fid: str
    video_size: int
    video_format: str
    key: str
    upload_start_time: str
    upload_end_time: str
    transfer_status: str
    error_message: str


FIELDNAMES = [
    "path",
    "fid",
    "video_size",
    "video_format",
    "key",
    "upload_start_time",
    "upload_end_time",
    "transfer_status",
    "error_message",
]


def write_meta_csv(path: str | Path, rows: Iterable[MetaRow]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
