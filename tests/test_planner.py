from pathlib import Path, PurePosixPath

from quark_transfer.models import DownloadRecord
from quark_transfer.planner import build_download_plans


def record(fid="fid-1", name="file.txt", size=10, relative_dir=PurePosixPath(".")):
    return DownloadRecord(fid=fid, name=name, size=size, relative_dir=relative_dir)


def test_planner_builds_output_paths(tmp_path: Path):
    plans = build_download_plans([record()], tmp_path)

    assert plans[0].destination == tmp_path / "file.txt"
    assert plans[0].part_path == tmp_path / "file.txt.part"
    assert plans[0].skip is False
    assert plans[0].resume is False


def test_planner_preserves_nested_relative_directory(tmp_path: Path):
    plans = build_download_plans([record(relative_dir=PurePosixPath("sub/dir"))], tmp_path)

    assert plans[0].destination == tmp_path / "sub" / "dir" / "file.txt"


def test_planner_skips_existing_same_size_file(tmp_path: Path):
    destination = tmp_path / "file.txt"
    destination.write_bytes(b"0123456789")

    plans = build_download_plans([record(size=10)], tmp_path)

    assert plans[0].skip is True


def test_planner_overwrite_disables_skip_for_existing_same_size_file(tmp_path: Path):
    destination = tmp_path / "file.txt"
    destination.write_bytes(b"0123456789")

    plans = build_download_plans([record(size=10)], tmp_path, overwrite=True)

    assert plans[0].skip is False


def test_planner_detects_resume_part_file(tmp_path: Path):
    part_path = tmp_path / "file.txt.part"
    part_path.write_bytes(b"partial")

    plans = build_download_plans([record(size=10)], tmp_path)

    assert plans[0].resume is True
