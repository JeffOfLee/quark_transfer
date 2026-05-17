from pathlib import PurePosixPath

import pytest

from quark_transfer.errors import NotFoundError, QuarkTransferError
from quark_transfer.models import CloudItem
from quark_transfer.resolver import resolve_fid, resolve_path


class FakeClient:
    def __init__(self):
        self.items = {
            "file-root": CloudItem("file-root", "root.txt", 10, False),
            "docs": CloudItem("docs", "docs", 0, True),
            "sub": CloudItem("sub", "sub", 0, True),
            "a": CloudItem("a", "a.txt", 1, False),
            "b": CloudItem("b", "b.txt", 2, False),
        }
        self.children = {
            "0": [self.items["docs"], self.items["file-root"]],
            "docs": [self.items["a"], self.items["sub"]],
            "sub": [self.items["b"]],
        }

    def list_folder(self, fid):
        return list(self.children.get(fid, []))

    def get_item(self, fid):
        return self.items[fid]


def test_resolve_path_to_file():
    records = resolve_path(FakeClient(), "/root.txt")

    assert len(records) == 1
    assert records[0].fid == "file-root"
    assert records[0].relative_dir == PurePosixPath(".")


def test_resolve_path_to_folder_recursively():
    records = resolve_path(FakeClient(), "/docs")

    assert [(record.fid, record.relative_dir) for record in records] == [
        ("a", PurePosixPath(".")),
        ("b", PurePosixPath("sub")),
    ]


def test_resolve_fid_to_folder_recursively():
    records = resolve_fid(FakeClient(), "docs")

    assert [(record.name, record.relative_dir) for record in records] == [
        ("a.txt", PurePosixPath(".")),
        ("b.txt", PurePosixPath("sub")),
    ]


def test_resolve_missing_path_raises_not_found():
    with pytest.raises(NotFoundError, match="/missing"):
        resolve_path(FakeClient(), "/missing")


def test_resolve_ambiguous_duplicate_path_segment_raises_error():
    client = FakeClient()
    client.children["0"] = [CloudItem("one", "dupe", 0, True), CloudItem("two", "dupe", 0, True)]

    with pytest.raises(QuarkTransferError, match="Ambiguous"):
        resolve_path(client, "/dupe")
