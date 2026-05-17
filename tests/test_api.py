import pytest

from quark_transfer.api import QuarkClient
from quark_transfer.errors import AuthError, ConfigError
from quark_transfer.models import VipAccelMode


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)


def test_list_folder_paginates_and_sends_cookie_header():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "list": [{"fid": "a", "file_name": "a.txt", "size": 10, "file_type": 0}],
                        "total": 2,
                    },
                }
            ),
            FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "list": [{"fid": "b", "file_name": "b", "size": 0, "dir": True}],
                        "total": 2,
                    },
                }
            ),
        ]
    )
    client = QuarkClient("cookie-value", session=session, page_size=1)

    items = client.list_folder("folder-id")

    assert [item.fid for item in items] == ["a", "b"]
    assert session.calls[0][1] == "https://drive-pc.quark.cn/1/clouddrive/file/sort"
    assert session.calls[0][2]["headers"]["Cookie"] == "cookie-value"
    assert "quark-cloud-drive" in session.calls[0][2]["headers"]["User-Agent"]
    assert session.calls[0][2]["params"]["pdir_fid"] == "folder-id"
    assert session.calls[0][2]["timeout"] == 30
    assert session.calls[1][2]["params"]["_page"] == "2"


def test_list_folder_uses_metadata_total_for_pagination():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "code": 0,
                    "data": {"list": [{"fid": "a", "file_name": "a.txt", "size": 10, "file_type": 0}]},
                    "metadata": {"_total": 2},
                }
            ),
            FakeResponse(
                {
                    "code": 0,
                    "data": {"list": [{"fid": "b", "file_name": "b.txt", "size": 10, "file_type": 0}]},
                    "metadata": {"_total": 2},
                }
            ),
        ]
    )
    client = QuarkClient("cookie-value", session=session, page_size=1)

    items = client.list_folder("folder-id")

    assert [item.fid for item in items] == ["a", "b"]


def test_list_folder_treats_video_file_type_one_as_file_when_dir_false():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "list": [
                            {
                                "fid": "video",
                                "file_name": "movie.mp4",
                                "size": 3088299229,
                                "file_type": 1,
                                "format_type": "video/mp4",
                                "obj_category": "video",
                                "dir": False,
                            }
                        ],
                        "total": 1,
                    },
                }
            )
        ]
    )
    client = QuarkClient("cookie-value", session=session)

    items = client.list_folder("folder-id")

    assert items[0].is_folder is False


def test_list_folder_raises_auth_error_for_unauthorized_response():
    session = FakeSession([FakeResponse({"code": 401, "message": "not login"})])
    client = QuarkClient("cookie-value", session=session)

    with pytest.raises(AuthError, match="not login"):
        client.list_folder("0")


def test_download_url_auto_prefers_vip_url_and_falls_back_to_normal_url():
    session = FakeSession(
        [
            FakeResponse({"code": 0, "data": [{"download_url": "normal", "vip_download_url": "vip"}]}),
            FakeResponse({"code": 0, "data": [{"download_url": "normal-only"}]}),
        ]
    )
    client = QuarkClient("cookie-value", session=session)

    vip_url = client.get_download_url("fid-1", VipAccelMode.AUTO)
    normal_url = client.get_download_url("fid-2", VipAccelMode.AUTO)

    assert vip_url.url == "vip"
    assert vip_url.accelerated is True
    assert normal_url.url == "normal-only"
    assert normal_url.accelerated is False
    assert session.calls[0][1] == "https://drive.quark.cn/1/clouddrive/file/download?pr=ucpro&fr=pc"
    assert session.calls[0][2]["json"] == {"fids": ["fid-1"]}
    assert session.calls[0][2]["timeout"] == 30


def test_download_url_on_requires_vip_url():
    session = FakeSession([FakeResponse({"code": 0, "data": [{"download_url": "normal"}]})])
    client = QuarkClient("cookie-value", session=session)

    with pytest.raises(ConfigError, match="VIP"):
        client.get_download_url("fid-1", VipAccelMode.ON)


def test_download_url_off_uses_normal_url_even_when_vip_exists():
    session = FakeSession(
        [FakeResponse({"code": 0, "data": [{"download_url": "normal", "vip_download_url": "vip"}]})]
    )
    client = QuarkClient("cookie-value", session=session)

    url = client.get_download_url("fid-1", VipAccelMode.OFF)

    assert url.url == "normal"
    assert url.accelerated is False
