from pathlib import Path

import pytest

from quark_transfer.batch import ResourceSpec
from quark_transfer.cli import Config, _hash_source, _run_resource, build_config, build_parser, main, run
from quark_transfer.errors import ConfigError, QuarkTransferError
from quark_transfer.models import DownloadRecord, VipAccelMode
from quark_transfer.planner import DownloadPlan
from quark_transfer.s3 import UploadResult


def test_build_config_rejects_both_path_and_fid():
    with pytest.raises(SystemExit) as exc:
        build_config(["--path", "/a", "--fid", "fid", "--output", "out"])

    assert exc.value.code == 2


def test_build_config_requires_output():
    with pytest.raises(SystemExit) as exc:
        build_config(["--path", "/a"])

    assert exc.value.code == 2


def test_build_config_parses_vip_and_rate_limit(tmp_path: Path):
    config = build_config(
        [
            "--cookie",
            "cookie-value",
            "--fid",
            "fid",
            "--output",
            str(tmp_path),
            "--vip-accel",
            "on",
            "--rate-limit",
            "5M",
        ]
    )

    assert config.cookie == "cookie-value"
    assert config.fid == "fid"
    assert config.output == tmp_path
    assert config.vip_accel == VipAccelMode.ON
    assert config.rate_limit == 5 * 1024 * 1024
    assert len(config.resources) == 1
    assert config.resources[0].fid == "fid"


def test_build_config_loads_cookie_from_config_file(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[quark]\ncookie = "config-cookie"\n', encoding="utf-8")

    config = build_config(["--config", str(config_file), "--fid", "fid", "--output", str(tmp_path)])

    assert config.cookie == "config-cookie"


def test_build_config_loads_csv_resources(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[quark]\ncookie = "config-cookie"\n', encoding="utf-8")
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text("quark_path\n/a\n/b\n", encoding="utf-8")

    config = build_config(
        [
            "--config",
            str(config_file),
            "--csv",
            str(csv_file),
            "--path-column",
            "quark_path",
            "--output",
            str(tmp_path),
            "--concurrency",
            "3",
        ]
    )

    assert [resource.path for resource in config.resources] == ["/a", "/b"]
    assert config.concurrency == 3


def test_build_config_requires_s3_config_when_s3_upload_enabled(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[quark]\ncookie = "config-cookie"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="s3"):
        build_config(["--config", str(config_file), "--fid", "fid", "--output", str(tmp_path), "--s3-upload"])


def test_build_config_delete_alias_enables_delete_local_after_upload(tmp_path: Path):
    config = build_config(
        [
            "--cookie",
            "cookie-value",
            "--fid",
            "fid",
            "--output",
            str(tmp_path),
            "--delete",
        ]
    )

    assert config.delete_local_after_upload is True


def test_help_includes_delete_alias():
    assert "--delete-local-after-upload, --delete" in build_parser().format_help()


def test_build_config_parses_meta_path(tmp_path: Path):
    config = build_config(
        [
            "--cookie",
            "cookie-value",
            "--fid",
            "fid",
            "--output",
            str(tmp_path),
            "--meta",
            str(tmp_path / "result.csv"),
        ]
    )

    assert config.meta_path == tmp_path / "result.csv"


def test_main_redacts_cookie_like_values(monkeypatch, capsys):
    def fake_run(config):
        raise ConfigError("bad Cookie: abc=secret; other=value")

    monkeypatch.setattr("quark_transfer.cli.run", fake_run)

    code = main(["--cookie", "abc=secret; other=value", "--fid", "fid", "--output", "out"])

    captured = capsys.readouterr()
    assert code == 2
    assert "secret" not in captured.err
    assert "[REDACTED]" in captured.err


def test_run_attempts_all_batch_resources_before_raising(monkeypatch, tmp_path: Path):
    attempted = []

    def fake_run_resource(config, resource, s3_uploader):
        attempted.append(resource.path)
        if resource.path == "/bad":
            raise QuarkTransferError("bad resource")

    monkeypatch.setattr("quark_transfer.cli._run_resource", fake_run_resource)
    config = _config(tmp_path, resources=[ResourceSpec(path="/ok"), ResourceSpec(path="/bad")])

    with pytest.raises(QuarkTransferError, match="bad resource"):
        run(config)

    assert sorted(attempted) == ["/bad", "/ok"]


def test_run_writes_meta_rows_for_success_and_failure(monkeypatch, tmp_path: Path):
    def fake_run_resource(config, resource, s3_uploader):
        if resource.path == "/bad":
            raise QuarkTransferError("bad resource")
        return [
            config.meta_row_factory(
                path="/ok",
                fid="fid-ok",
                video_size=5,
                video_format="mp4",
                key="videos/key.mp4",
                upload_start_time="start",
                upload_end_time="end",
                transfer_status="uploaded",
                error_message="",
            )
        ]

    monkeypatch.setattr("quark_transfer.cli._run_resource", fake_run_resource)
    meta_path = tmp_path / "meta.csv"
    config = _config(
        tmp_path,
        resources=[ResourceSpec(path="/ok"), ResourceSpec(path="/bad")],
        meta_path=meta_path,
    )

    with pytest.raises(QuarkTransferError):
        run(config)

    lines = meta_path.read_text(encoding="utf-8").splitlines()
    assert "uploaded" in lines[1]
    assert "/bad" in lines[2]
    assert "failed" in lines[2]
    assert "bad resource" in lines[2]


def test_run_resource_uploads_to_s3_logs_result_and_deletes_local_file(monkeypatch, tmp_path: Path, capsys):
    record = DownloadRecord(fid="fid", name="movie.mp4", size=5)
    destination = tmp_path / "movie.mp4"
    plan = DownloadPlan(record=record, destination=destination, part_path=tmp_path / "movie.mp4.part")
    uploads = []

    class FakeUploader:
        def upload_file(self, path, *, hash_source):
            uploads.append((path, hash_source))
            return UploadResult(
                key="videos/hash.mp4",
                bytes_uploaded=5,
                start_time=100.0,
                end_time=102.0,
            )

    monkeypatch.setattr("quark_transfer.cli.QuarkClient", lambda cookie: object())
    monkeypatch.setattr("quark_transfer.cli.resolve_fid", lambda client, fid: [record])
    monkeypatch.setattr("quark_transfer.cli.build_download_plans", lambda records, output, overwrite=False: [plan])

    def fake_download_files(plans, url_provider, **kwargs):
        destination.write_bytes(b"video")

    monkeypatch.setattr("quark_transfer.cli.download_files", fake_download_files)
    config = _config(
        tmp_path,
        resources=[ResourceSpec(fid="fid")],
        delete_local_after_upload=True,
        verbose=True,
    )

    rows = _run_resource(config, config.resources[0], FakeUploader())

    captured = capsys.readouterr()
    assert "s3 upload complete" in captured.err
    assert "videos/hash.mp4" in captured.err
    assert "rate=0.00 MiB/s" in captured.err
    assert uploads == [(destination, "fid/movie.mp4")]
    assert not destination.exists()
    assert rows[0].key == "videos/hash.mp4"
    assert rows[0].transfer_status == "uploaded"
    assert rows[0].upload_start_time
    assert rows[0].upload_end_time


def test_hash_source_prefers_path_and_includes_nested_filename():
    record = DownloadRecord(fid="fid", name="movie.mp4", size=5)
    plan = DownloadPlan(
        record=record,
        destination=Path("out") / "nested" / "movie.mp4",
        part_path=Path("out") / "nested" / "movie.mp4.part",
    )

    assert _hash_source(ResourceSpec(path="/folder"), plan) == "/folder/nested/movie.mp4"
    assert _hash_source(ResourceSpec(fid="fid"), plan) == "fid/nested/movie.mp4"


def _config(tmp_path: Path, *, resources, delete_local_after_upload=False, meta_path=None, verbose=False):
    return Config(
        cookie="cookie-value",
        path=None,
        fid=None,
        resources=resources,
        output=tmp_path,
        concurrency=2,
        chunk_concurrency=4,
        chunk_size=8 * 1024 * 1024,
        rate_limit=None,
        vip_accel=VipAccelMode.AUTO,
        overwrite=False,
        dry_run=False,
        verbose=verbose,
        s3_upload=False,
        s3_config=None,
        delete_local_after_upload=delete_local_after_upload,
        meta_path=meta_path,
        meta_row_factory=__import__("quark_transfer.meta", fromlist=["MetaRow"]).MetaRow,
    )
