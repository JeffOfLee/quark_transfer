from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError


@dataclass(frozen=True)
class ResourceSpec:
    path: str | None = None
    fid: str | None = None


def load_csv_resources(
    csv_path: str | Path,
    *,
    path_column: str | None,
    fid_column: str | None,
) -> list[ResourceSpec]:
    if bool(path_column) == bool(fid_column):
        raise ConfigError("CSV input requires exactly one of --path-column or --fid-column.")

    selected_column = path_column or fid_column
    assert selected_column is not None

    with Path(csv_path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or selected_column not in reader.fieldnames:
            raise ConfigError(f"CSV column not found: {selected_column}")

        resources: list[ResourceSpec] = []
        for row_number, row in enumerate(reader, start=2):
            value = (row.get(selected_column) or "").strip()
            if not value:
                raise ConfigError(f"CSV row {row_number} has empty value for column: {selected_column}")
            resources.append(ResourceSpec(path=value if path_column else None, fid=value if fid_column else None))

    return resources
