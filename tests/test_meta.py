from pathlib import Path

from quark_transfer.meta import MetaRow, write_meta_csv


def test_write_meta_csv_outputs_requested_columns(tmp_path: Path):
    meta_path = tmp_path / "result.csv"
    rows = [
        MetaRow(
            path="/movies/a",
            fid="fid-1",
            video_size=123,
            video_format="MP4",
            key="videos/hash.MP4",
            upload_start_time="2026-05-18T10:00:00+08:00",
            upload_end_time="2026-05-18T10:01:00+08:00",
            transfer_status="uploaded",
            error_message="",
        ),
        MetaRow(
            path="/movies/b",
            fid="fid-2",
            video_size=456,
            video_format="mkv",
            key="",
            upload_start_time="",
            upload_end_time="",
            transfer_status="failed",
            error_message="network error",
        ),
    ]

    write_meta_csv(meta_path, rows)

    assert meta_path.read_text(encoding="utf-8").splitlines() == [
        "path,fid,video_size,video_format,key,upload_start_time,upload_end_time,transfer_status,error_message",
        "/movies/a,fid-1,123,MP4,videos/hash.MP4,2026-05-18T10:00:00+08:00,2026-05-18T10:01:00+08:00,uploaded,",
        "/movies/b,fid-2,456,mkv,,,,failed,network error",
    ]
