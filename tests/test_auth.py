from pathlib import Path

import pytest

from quark_transfer.auth import load_cookie
from quark_transfer.errors import ConfigError


def test_explicit_cookie_takes_precedence_over_file_and_env(tmp_path: Path):
    cookie_file = tmp_path / "cookie.txt"
    cookie_file.write_text("file-cookie\n", encoding="utf-8")

    cookie = load_cookie(
        cookie=" explicit-cookie ",
        cookie_file=cookie_file,
        env={"QUARK_COOKIE": "env-cookie"},
    )

    assert cookie == "explicit-cookie"


def test_cookie_file_takes_precedence_over_env(tmp_path: Path):
    cookie_file = tmp_path / "cookie.txt"
    cookie_file.write_text(" file-cookie \n", encoding="utf-8")

    cookie = load_cookie(cookie=None, cookie_file=cookie_file, env={"QUARK_COOKIE": "env-cookie"})

    assert cookie == "file-cookie"


def test_environment_cookie_is_used_when_no_flag_or_file():
    cookie = load_cookie(cookie=None, cookie_file=None, env={"QUARK_COOKIE": " env-cookie "})

    assert cookie == "env-cookie"


def test_missing_cookie_raises_config_error():
    with pytest.raises(ConfigError, match="Cookie"):
        load_cookie(cookie=None, cookie_file=None, env={})


def test_empty_cookie_file_raises_config_error(tmp_path: Path):
    cookie_file = tmp_path / "cookie.txt"
    cookie_file.write_text(" \n", encoding="utf-8")

    with pytest.raises(ConfigError, match="empty"):
        load_cookie(cookie=None, cookie_file=cookie_file, env={})

