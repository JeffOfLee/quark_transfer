import pytest

from quark_transfer.errors import ConfigError
from quark_transfer.rate_limit import parse_rate_limit


@pytest.mark.parametrize("value", [None, "", "0", "none", "NONE"])
def test_unlimited_rate_limit_values(value):
    assert parse_rate_limit(value) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("500K", 500 * 1024),
        ("500kb", 500 * 1024),
        ("5M", 5 * 1024 * 1024),
        ("5mb", 5 * 1024 * 1024),
        ("2G", 2 * 1024 * 1024 * 1024),
        ("2gb", 2 * 1024 * 1024 * 1024),
        ("42", 42),
    ],
)
def test_parse_rate_limit_units(value, expected):
    assert parse_rate_limit(value) == expected


@pytest.mark.parametrize("value", ["abc", "-1", "1.5M"])
def test_invalid_rate_limit_values_raise_config_error(value):
    with pytest.raises(ConfigError, match="rate limit"):
        parse_rate_limit(value)
