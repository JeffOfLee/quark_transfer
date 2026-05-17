from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Protocol

import requests

from .errors import DownloadError
from .models import DownloadRecord, DownloadUrl
from .planner import DownloadPlan


class Bucket(Protocol):
    def consume(self, size: int) -> None: ...


UrlProvider = Callable[[DownloadRecord], DownloadUrl]


def download_files(
    plans: list[DownloadPlan],
    url_provider: UrlProvider,
    *,
    session: requests.Session | None = None,
    bucket: Bucket | None = None,
    concurrency: int = 4,
    chunk_size: int = 8 * 1024 * 1024,
    chunk_concurrency: int = 4,
    range_threshold: int = 64 * 1024 * 1024,
    retries: int = 3,
) -> None:
    http = session or requests.Session()
    active_plans = [plan for plan in plans if not plan.skip]
    if not active_plans:
        return

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = [
            executor.submit(
                _download_one,
                plan,
                url_provider,
                http,
                bucket,
                chunk_size,
                chunk_concurrency,
                range_threshold,
                retries,
            )
            for plan in active_plans
        ]
        for future in as_completed(futures):
            future.result()


def _download_one(
    plan: DownloadPlan,
    url_provider: UrlProvider,
    session: requests.Session,
    bucket: Bucket | None,
    chunk_size: int,
    chunk_concurrency: int,
    range_threshold: int,
    retries: int,
) -> None:
    plan.destination.parent.mkdir(parents=True, exist_ok=True)
    download_url = url_provider(plan.record).url

    if plan.record.size >= range_threshold and plan.record.size > chunk_size:
        _download_ranges(plan, download_url, session, bucket, chunk_size, chunk_concurrency, retries)
    else:
        _download_whole(plan, download_url, session, bucket, retries)

    if plan.destination.exists():
        plan.destination.unlink()
    os.replace(plan.part_path, plan.destination)


def _download_whole(
    plan: DownloadPlan,
    url: str,
    session: requests.Session,
    bucket: Bucket | None,
    retries: int,
) -> None:
    start = plan.part_path.stat().st_size if plan.resume and plan.part_path.exists() else 0
    headers = {"Range": f"bytes={start}-"} if start else None
    expected = {206} if start else None
    response = _request_with_retries(
        session,
        url,
        retries=retries,
        stream=True,
        headers=headers,
        expected_status=expected,
    )
    mode = "ab" if start else "wb"
    try:
        with plan.part_path.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                if bucket is not None:
                    bucket.consume(len(chunk))
                handle.write(chunk)
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()


def _download_ranges(
    plan: DownloadPlan,
    url: str,
    session: requests.Session,
    bucket: Bucket | None,
    chunk_size: int,
    chunk_concurrency: int,
    retries: int,
) -> None:
    plan.part_path.parent.mkdir(parents=True, exist_ok=True)
    with plan.part_path.open("wb") as handle:
        handle.truncate(plan.record.size)

    ranges = []
    for start in range(0, plan.record.size, chunk_size):
        end = min(start + chunk_size - 1, plan.record.size - 1)
        ranges.append((start, end))

    with ThreadPoolExecutor(max_workers=max(1, chunk_concurrency)) as executor:
        futures = [
            executor.submit(_download_range, plan, url, session, bucket, start, end, retries)
            for start, end in ranges
        ]
        for future in as_completed(futures):
            future.result()


def _download_range(
    plan: DownloadPlan,
    url: str,
    session: requests.Session,
    bucket: Bucket | None,
    start: int,
    end: int,
    retries: int,
) -> None:
    response = _request_with_retries(
        session,
        url,
        retries=retries,
        stream=True,
        headers={"Range": f"bytes={start}-{end}"},
        expected_status={206},
    )
    try:
        offset = start
        with plan.part_path.open("r+b") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                if bucket is not None:
                    bucket.consume(len(chunk))
                handle.seek(offset)
                handle.write(chunk)
                offset += len(chunk)
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()


def _request_with_retries(
    session: requests.Session,
    url: str,
    *,
    retries: int,
    stream: bool,
    headers: dict[str, str] | None = None,
    expected_status: set[int] | None = None,
):
    expected = expected_status or {200, 206}
    attempts = retries + 1
    for attempt in range(attempts):
        response = session.get(url, stream=stream, headers=headers or {})
        if response.status_code in expected:
            return response
        if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
            time.sleep(min(2**attempt, 5))
            continue
        raise DownloadError(f"Download request failed with HTTP {response.status_code}")

    raise DownloadError("Download request failed after retries")
