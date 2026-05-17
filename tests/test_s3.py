from pathlib import Path

from quark_transfer.config import S3Config
from quark_transfer.s3 import S3Uploader


class FakeS3Client:
    def __init__(self):
        self.uploads = []

    def upload_file(self, filename, bucket, key):
        self.uploads.append((filename, bucket, key))


def test_s3_uploader_uploads_with_prefix_and_posix_key(tmp_path: Path):
    file_path = tmp_path / "downloads" / "nested" / "movie.mp4"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"video")
    client = FakeS3Client()
    uploader = S3Uploader(
        S3Config(bucket="bucket", prefix="videos/"),
        client=client,
    )

    key = uploader.upload_file(file_path, relative_to=tmp_path / "downloads")

    assert key == "videos/nested/movie.mp4"
    assert client.uploads == [(str(file_path), "bucket", "videos/nested/movie.mp4")]


def test_s3_uploader_normalizes_empty_prefix(tmp_path: Path):
    file_path = tmp_path / "movie.mp4"
    file_path.write_bytes(b"video")
    client = FakeS3Client()
    uploader = S3Uploader(S3Config(bucket="bucket", prefix=""), client=client)

    key = uploader.upload_file(file_path, relative_to=tmp_path)

    assert key == "movie.mp4"
