from pathlib import Path

import pytest

from quark_transfer.config import S3Config, load_app_config
from quark_transfer.errors import ConfigError


def test_load_config_reads_quark_cookie_and_s3_settings(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[quark]
cookie = "cookie-value"

[s3]
bucket = "video-bucket"
prefix = "videos/"
region = "ap-southeast-1"
endpoint_url = "https://s3.example.test"
access_key_id = "access"
secret_access_key = "secret"
""",
        encoding="utf-8",
    )

    config = load_app_config(config_file)

    assert config.quark_cookie == "cookie-value"
    assert config.s3 == S3Config(
        bucket="video-bucket",
        prefix="videos/",
        region="ap-southeast-1",
        endpoint_url="https://s3.example.test",
        access_key_id="access",
        secret_access_key="secret",
    )


def test_load_config_allows_missing_s3_section(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[quark]\ncookie = "cookie-value"\n', encoding="utf-8")

    config = load_app_config(config_file)

    assert config.quark_cookie == "cookie-value"
    assert config.s3 is None


def test_load_config_requires_s3_bucket_when_s3_section_exists(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[s3]\nprefix = 'videos/'\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="bucket"):
        load_app_config(config_file)

