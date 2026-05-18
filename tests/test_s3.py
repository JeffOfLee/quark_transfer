import hashlib
from pathlib import Path

from quark_transfer.config import S3Config
from quark_transfer.s3 import S3Uploader


class FakeS3Client:
    def __init__(self):
        self.uploads = []

    def upload_file(self, filename, bucket, key, **kwargs):
        self.uploads.append((filename, bucket, key))


def test_s3_uploader_uploads_with_prefix_hash_key_and_metrics(tmp_path: Path):
    file_path = tmp_path / "downloads" / "nested" / "movie.mp4"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"video")
    client = FakeS3Client()
    uploader = S3Uploader(
        S3Config(bucket="bucket", prefix="videos/"),
        client=client,
    )

    result = uploader.upload_file(
        file_path,
        hash_source="films_download_temp/赵子龙_tt13575948/nested/movie.mp4",
        clock=iter([100.0, 102.0]).__next__,
    )

    expected_hash = hashlib.sha256("films_download_temp/赵子龙_tt13575948/nested/movie.mp4".encode("utf-8")).hexdigest()
    assert result.key == f"videos/{expected_hash}.mp4"
    assert result.bytes_uploaded == 5
    assert result.duration_seconds == 2.0
    assert result.bytes_per_second == 2.5
    assert client.uploads == [(str(file_path), "bucket", f"videos/{expected_hash}.mp4")]


def test_s3_uploader_normalizes_empty_prefix(tmp_path: Path):
    file_path = tmp_path / "movie.mp4"
    file_path.write_bytes(b"video")
    client = FakeS3Client()
    uploader = S3Uploader(S3Config(bucket="bucket", prefix=""), client=client)

    result = uploader.upload_file(file_path, hash_source="movie.mp4")

    expected_hash = hashlib.sha256("movie.mp4".encode("utf-8")).hexdigest()
    assert result.key == f"{expected_hash}.mp4"
