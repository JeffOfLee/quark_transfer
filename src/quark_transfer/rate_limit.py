from __future__ import annotations

import re
import time

from .errors import ConfigError

_RATE_RE = re.compile(r"^(?P<number>\d+)(?P<unit>k|kb|m|mb)?$", re.IGNORECASE)


def parse_rate_limit(value: str | None) -> int | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized or normalized.lower() == "none" or normalized == "0":
        return None

    match = _RATE_RE.match(normalized)
    if not match:
        raise ConfigError(f"Invalid rate limit: {value}")

    amount = int(match.group("number"))
    unit = (match.group("unit") or "").lower()
    if unit in {"k", "kb"}:
        return amount * 1024
    if unit in {"m", "mb"}:
        return amount * 1024 * 1024
    return amount


class TokenBucket:
    def __init__(self, rate_bytes_per_second: int | None, *, clock=time.monotonic, sleeper=time.sleep):
        self.rate = rate_bytes_per_second
        self._clock = clock
        self._sleeper = sleeper
        self._tokens = float(rate_bytes_per_second or 0)
        self._last_refill = clock()

    def consume(self, size: int) -> None:
        if self.rate is None or size <= 0:
            return

        while True:
            self._refill()
            if self._tokens >= size:
                self._tokens -= size
                return

            missing = size - self._tokens
            self._sleeper(missing / self.rate)

    def _refill(self) -> None:
        assert self.rate is not None
        now = self._clock()
        elapsed = max(0.0, now - self._last_refill)
        self._last_refill = now
        self._tokens = min(float(self.rate), self._tokens + elapsed * self.rate)
