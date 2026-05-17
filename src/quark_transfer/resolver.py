from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol

from .errors import NotFoundError, QuarkTransferError
from .models import CloudItem, DownloadRecord


class CloudClient(Protocol):
    def list_folder(self, parent_fid: str) -> list[CloudItem]: ...

    def get_item(self, fid: str) -> CloudItem: ...


def resolve_path(client: CloudClient, path: str) -> list[DownloadRecord]:
    segments = [segment for segment in PurePosixPath(path).parts if segment not in {"/", "."}]
    if not segments:
        return _expand_folder(client, "0", PurePosixPath("."))

    current_parent = "0"
    current_item: CloudItem | None = None
    traversed: list[str] = []

    for segment in segments:
        traversed.append(segment)
        matches = [item for item in client.list_folder(current_parent) if item.name == segment]
        if not matches:
            raise NotFoundError(f"Cloud path not found: /{'/'.join(traversed)}")
        if len(matches) > 1:
            raise QuarkTransferError(f"Ambiguous cloud path segment: /{'/'.join(traversed)}")
        current_item = matches[0]
        current_parent = current_item.fid

    assert current_item is not None
    return _expand_item(client, current_item, PurePosixPath("."))


def resolve_fid(client: CloudClient, fid: str) -> list[DownloadRecord]:
    return _expand_item(client, client.get_item(fid), PurePosixPath("."))


def _expand_item(client: CloudClient, item: CloudItem, relative_dir: PurePosixPath) -> list[DownloadRecord]:
    if not item.is_folder:
        return [DownloadRecord(fid=item.fid, name=item.name, size=item.size, relative_dir=relative_dir)]
    return _expand_folder(client, item.fid, relative_dir)


def _expand_folder(client: CloudClient, folder_fid: str, relative_dir: PurePosixPath) -> list[DownloadRecord]:
    records: list[DownloadRecord] = []
    for child in client.list_folder(folder_fid):
        if child.is_folder:
            child_dir = PurePosixPath(child.name) if relative_dir == PurePosixPath(".") else relative_dir / child.name
            records.extend(_expand_folder(client, child.fid, child_dir))
        else:
            records.append(
                DownloadRecord(
                    fid=child.fid,
                    name=child.name,
                    size=child.size,
                    relative_dir=relative_dir,
                )
            )
    return records
