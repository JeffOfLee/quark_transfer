from __future__ import annotations

from typing import Any

import requests

from .errors import AuthError, ConfigError, QuarkTransferError
from .models import CloudItem, DownloadUrl, VipAccelMode


class QuarkClient:
    LIST_URL = "https://drive-pc.quark.cn/1/clouddrive/file/sort"
    DOWNLOAD_URL = "https://drive.quark.cn/1/clouddrive/file/download?pr=ucpro&fr=pc"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
        "Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch"
    )
    VIP_FIELDS = (
        "vip_download_url",
        "download_url_vip",
        "accelerate_url",
        "accelerated_url",
        "high_speed_download_url",
    )

    def __init__(
        self,
        cookie: str,
        *,
        session: requests.Session | None = None,
        page_size: int = 50,
        timeout: int = 30,
    ):
        self.cookie = cookie
        self.session = session or requests.Session()
        self.page_size = page_size
        self.timeout = timeout

    def list_folder(self, parent_fid: str = "0") -> list[CloudItem]:
        page = 1
        items: list[CloudItem] = []

        while True:
            payload = self._get_json(
                self.LIST_URL,
                params={
                    "pr": "ucpro",
                    "fr": "pc",
                    "pdir_fid": parent_fid,
                    "_page": str(page),
                    "_size": str(self.page_size),
                    "_fetch_total": "1",
                    "_fetch_sub_dirs": "0",
                    "_sort": "file_type:asc,updated_at:desc",
                },
            )
            data = payload.get("data") or {}
            batch = data.get("list") or []
            items.extend(self._parse_item(raw, parent_fid) for raw in batch)

            metadata = payload.get("metadata") or {}
            total = int(data.get("total") or metadata.get("_total") or len(items))
            if len(items) >= total or not batch:
                return items
            page += 1

    def get_item(self, fid: str) -> CloudItem:
        payload = self._post_json(
            "https://drive-pc.quark.cn/1/clouddrive/file/info?pr=ucpro&fr=pc",
            json={"fids": [fid]},
        )
        data = payload.get("data") or []
        if isinstance(data, dict):
            data = data.get("list") or data.get("items") or []
        if not data:
            raise QuarkTransferError(f"Resource not found: {fid}")
        return self._parse_item(data[0], None)

    def get_download_url(self, fid: str, vip_accel: VipAccelMode) -> DownloadUrl:
        payload = self._post_json(self.DOWNLOAD_URL, json={"fids": [fid]})
        data = payload.get("data") or []
        if not data:
            raise QuarkTransferError(f"No download URL returned for fid: {fid}")
        entry = data[0]
        normal_url = entry.get("download_url") or entry.get("url")
        vip_url = self._pick_vip_url(entry)

        if vip_accel == VipAccelMode.OFF:
            if not normal_url:
                raise QuarkTransferError(f"No normal download URL returned for fid: {fid}")
            return DownloadUrl(normal_url, accelerated=False)

        if vip_url:
            return DownloadUrl(vip_url, accelerated=True)

        if vip_accel == VipAccelMode.ON:
            raise ConfigError("VIP accelerated download URL is not available for this resource/account.")

        if not normal_url:
            raise QuarkTransferError(f"No download URL returned for fid: {fid}")
        return DownloadUrl(normal_url, accelerated=False)

    def _get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.session.get(url, headers=self._headers(), timeout=self.timeout, **kwargs)
        return self._validate_response(response)

    def _post_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.session.post(url, headers=self._headers(), timeout=self.timeout, **kwargs)
        return self._validate_response(response)

    def _headers(self) -> dict[str, str]:
        return {
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.USER_AGENT,
            "Referer": "https://pan.quark.cn/",
        }

    def _validate_response(self, response: Any) -> dict[str, Any]:
        if getattr(response, "status_code", 200) in {401, 403}:
            raise AuthError("Quark authentication failed.")

        payload = response.json()
        code = payload.get("code", 0)
        if code in {401, 403, 40101, 41017}:
            raise AuthError(payload.get("message") or "Quark authentication failed.")
        if code not in {0, "0"}:
            raise QuarkTransferError(payload.get("message") or f"Quark API error: {code}")
        return payload

    def _parse_item(self, raw: dict[str, Any], parent_fid: str | None) -> CloudItem:
        is_folder = bool(raw.get("dir") or raw.get("is_dir"))
        return CloudItem(
            fid=str(raw.get("fid") or raw.get("file_id")),
            name=str(raw.get("file_name") or raw.get("name")),
            size=int(raw.get("size") or 0),
            is_folder=is_folder,
            parent_fid=parent_fid,
        )

    def _pick_vip_url(self, entry: dict[str, Any]) -> str | None:
        for field in self.VIP_FIELDS:
            value = entry.get(field)
            if value:
                return str(value)
        return None
