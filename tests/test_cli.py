from pathlib import Path

import pytest

from quark_transfer.cli import build_config, main
from quark_transfer.errors import ConfigError
from quark_transfer.models import VipAccelMode


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


def test_main_redacts_cookie_like_values(monkeypatch, capsys):
    def fake_run(config):
        raise ConfigError("bad Cookie: abc=secret; other=value")

    monkeypatch.setattr("quark_transfer.cli.run", fake_run)

    code = main(["--cookie", "abc=secret; other=value", "--fid", "fid", "--output", "out"])

    captured = capsys.readouterr()
    assert code == 2
    assert "secret" not in captured.err
    assert "[REDACTED]" in captured.err
