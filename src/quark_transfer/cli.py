from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .api import QuarkClient
from .auth import load_cookie
from .downloader import download_files
from .errors import QuarkTransferError
from .models import VipAccelMode
from .planner import build_download_plans
from .rate_limit import TokenBucket, parse_rate_limit
from .resolver import resolve_fid, resolve_path


@dataclass(frozen=True)
class Config:
    cookie: str
    path: str | None
    fid: str | None
    output: Path
    concurrency: int
    chunk_concurrency: int
    chunk_size: int
    rate_limit: int | None
    vip_accel: VipAccelMode
    overwrite: bool
    dry_run: bool
    verbose: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quark-download")
    auth = parser.add_argument_group("authentication")
    auth.add_argument("--cookie")
    auth.add_argument("--cookie-file", type=Path)

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--path")
    source.add_argument("--fid")

    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--chunk-concurrency", type=int, default=4)
    parser.add_argument("--chunk-size", type=_parse_size, default=8 * 1024 * 1024)
    parser.add_argument("--rate-limit")
    parser.add_argument("--vip-accel", choices=[mode.value for mode in VipAccelMode], default=VipAccelMode.AUTO.value)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def build_config(argv: Sequence[str] | None = None) -> Config:
    args = build_parser().parse_args(argv)
    cookie = load_cookie(args.cookie, args.cookie_file)
    return Config(
        cookie=cookie,
        path=args.path,
        fid=args.fid,
        output=args.output,
        concurrency=args.concurrency,
        chunk_concurrency=args.chunk_concurrency,
        chunk_size=args.chunk_size,
        rate_limit=parse_rate_limit(args.rate_limit),
        vip_accel=VipAccelMode(args.vip_accel),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def run(config: Config) -> None:
    client = QuarkClient(config.cookie)
    records = resolve_path(client, config.path) if config.path else resolve_fid(client, config.fid or "")
    plans = build_download_plans(records, config.output, overwrite=config.overwrite)

    if config.dry_run:
        for plan in plans:
            status = "skip" if plan.skip else "download"
            print(f"{status}\t{plan.record.size}\t{plan.destination}")
        return

    bucket = TokenBucket(config.rate_limit)
    download_files(
        plans,
        lambda record: client.get_download_url(record.fid, config.vip_accel),
        bucket=bucket,
        concurrency=config.concurrency,
        chunk_concurrency=config.chunk_concurrency,
        chunk_size=config.chunk_size,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = build_config(argv)
        run(config)
        return 0
    except QuarkTransferError as exc:
        print(_redact(str(exc)), file=sys.stderr)
        return exc.exit_code


def _parse_size(value: str) -> int:
    parsed = parse_rate_limit(value)
    if parsed is None:
        raise argparse.ArgumentTypeError("size must be greater than zero")
    return parsed


def _redact(message: str) -> str:
    return re.sub(r"(?i)(cookie:\s*)[^\\n]+", r"\1[REDACTED]", message)


if __name__ == "__main__":
    raise SystemExit(main())
