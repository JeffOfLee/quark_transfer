from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from .errors import ConfigError


def load_cookie(
    cookie: str | None,
    cookie_file: str | Path | None,
    env: Mapping[str, str] | None = None,
) -> str:
    env = os.environ if env is None else env

    if cookie and cookie.strip():
        return cookie.strip()

    if cookie_file is not None:
        path = Path(cookie_file)
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ConfigError(f"Cookie file is empty: {path}")
        return value

    env_cookie = env.get("QUARK_COOKIE", "").strip()
    if env_cookie:
        return env_cookie

    raise ConfigError("Cookie is required. Pass --cookie, --cookie-file, or QUARK_COOKIE.")

