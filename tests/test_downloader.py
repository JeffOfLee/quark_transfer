from pathlib import Path, PurePosixPath

import pytest

from quark_transfer.downloader import download_files
from quark_transfer.errors import DownloadError
from quark_transfer.models import DownloadRecord, DownloadUrl
from quark_transfer.planner import DownloadPlan


class FakeResponse:
    def __init__(self, body=b"", status_code=200):
        self.body = body
        self.status_code = status_code

    def iter_content(self, chunk_size=8192):
        yield self.body

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class RecordingBucket:
    def __init__(self):
        self.consumed = []

    def consume(self, size):
        self.consumed.append(size)


def make_plan(tmp_path: Path, *, skip=False, size=5):
    record = DownloadRecord("fid-1", "file.bin", size, PurePosixPath("."))
    destination = tmp_path / "file.bin"
    return DownloadPlan(
        record=record,
        destination=destination,
        part_path=tmp_path / "file.bin.part",
        skip=skip,
        resume=False,
    )


def test_download_writes_part_then_renames(tmp_path: Path):
    session = FakeSession([FakeResponse(b"hello")])
    bucket = RecordingBucket()
    plan = make_plan(tmp_path)

    download_files(
        [plan],
        lambda record: DownloadUrl("https://download/file", headers={"Cookie": "cookie-value", "Referer": "ref"}),
        session=session,
        bucket=bucket,
    )

    assert plan.destination.read_bytes() == b"hello"
    assert not plan.part_path.exists()
    assert bucket.consumed == [5]
    assert session.calls[0][1]["timeout"] == 30
    assert "quark-cloud-drive" in session.calls[0][1]["headers"]["User-Agent"]
    assert session.calls[0][1]["headers"]["Cookie"] == "cookie-value"
    assert session.calls[0][1]["headers"]["Referer"] == "ref"


def test_download_skips_marked_plan_without_request(tmp_path: Path):
    session = FakeSession([])
    plan = make_plan(tmp_path, skip=True)

    download_files([plan], lambda record: DownloadUrl("https://download/file"), session=session)

    assert session.calls == []


def test_download_retries_transient_errors(tmp_path: Path):
    session = FakeSession([FakeResponse(b"bad", status_code=500), FakeResponse(b"hello")])
    plan = make_plan(tmp_path)

    download_files([plan], lambda record: DownloadUrl("https://download/file"), session=session, retries=1)

    assert plan.destination.read_bytes() == b"hello"
    assert len(session.calls) == 2


def test_download_resumes_existing_part_file_with_range_request(tmp_path: Path):
    session = FakeSession([FakeResponse(b"lo", status_code=206)])
    plan = make_plan(tmp_path, size=5)
    plan.part_path.write_bytes(b"hel")
    plan = DownloadPlan(
        record=plan.record,
        destination=plan.destination,
        part_path=plan.part_path,
        skip=False,
        resume=True,
    )

    download_files([plan], lambda record: DownloadUrl("https://download/file"), session=session)

    assert plan.destination.read_bytes() == b"hello"
    assert session.calls[0][1]["headers"]["Range"] == "bytes=3-"


def test_download_fatal_status_raises_download_error(tmp_path: Path):
    session = FakeSession([FakeResponse(b"missing", status_code=404)])
    plan = make_plan(tmp_path)

    with pytest.raises(DownloadError, match="404"):
        download_files([plan], lambda record: DownloadUrl("https://download/file"), session=session)


def test_range_download_writes_chunks_at_offsets(tmp_path: Path):
    session = FakeSession([FakeResponse(b"abc", status_code=206), FakeResponse(b"def", status_code=206)])
    plan = make_plan(tmp_path, size=6)

    download_files(
        [plan],
        lambda record: DownloadUrl("https://download/file"),
        session=session,
        chunk_size=3,
        chunk_concurrency=1,
        range_threshold=1,
    )

    assert plan.destination.read_bytes() == b"abcdef"
    assert [call[1]["headers"]["Range"] for call in session.calls] == ["bytes=0-2", "bytes=3-5"]
