from pathlib import Path

import pytest

from quark_transfer.batch import ResourceSpec, load_csv_resources
from quark_transfer.errors import ConfigError


def test_load_csv_resources_by_path_column(tmp_path: Path):
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text("quark_path\n/a\n/b\n", encoding="utf-8")

    resources = load_csv_resources(csv_file, path_column="quark_path", fid_column=None)

    assert resources == [ResourceSpec(path="/a", fid=None), ResourceSpec(path="/b", fid=None)]


def test_load_csv_resources_by_fid_column(tmp_path: Path):
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text("fid\nabc\nxyz\n", encoding="utf-8")

    resources = load_csv_resources(csv_file, path_column=None, fid_column="fid")

    assert resources == [ResourceSpec(path=None, fid="abc"), ResourceSpec(path=None, fid="xyz")]


def test_load_csv_requires_exactly_one_column_selector(tmp_path: Path):
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text("fid,path\nabc,/a\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="exactly one"):
        load_csv_resources(csv_file, path_column="path", fid_column="fid")


def test_load_csv_missing_column_raises_config_error(tmp_path: Path):
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text("other\nvalue\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="quark_path"):
        load_csv_resources(csv_file, path_column="quark_path", fid_column=None)
