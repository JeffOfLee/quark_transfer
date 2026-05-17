from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .models import DownloadRecord


@dataclass(frozen=True)
class DownloadPlan:
    record: DownloadRecord
    destination: Path
    part_path: Path
    skip: bool = False
    resume: bool = False


def build_download_plans(
    records: list[DownloadRecord],
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> list[DownloadPlan]:
    root = Path(output_dir)
    plans: list[DownloadPlan] = []

    for record in records:
        relative_dir = Path() if record.relative_dir == PurePosixPath(".") else Path(record.relative_dir)
        destination = root / relative_dir / record.name
        part_path = destination.with_name(destination.name + ".part")
        skip = False
        if destination.exists() and not overwrite:
            skip = destination.stat().st_size == record.size

        plans.append(
            DownloadPlan(
                record=record,
                destination=destination,
                part_path=part_path,
                skip=skip,
                resume=part_path.exists() and not skip,
            )
        )

    return plans
