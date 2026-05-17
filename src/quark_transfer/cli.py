from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .api import QuarkClient
from .auth import load_cookie
from .batch import ResourceSpec, load_csv_resources
from .config import S3Config, load_app_config
from .downloader import download_files
from .errors import ConfigError, QuarkTransferError
from .models import VipAccelMode
from .planner import build_download_plans
from .rate_limit import TokenBucket, parse_rate_limit
from .resolver import resolve_fid, resolve_path
from .s3 import S3Uploader


@dataclass(frozen=True)
class Config:
    cookie: str
    path: str | None
    fid: str | None
    resources: list[ResourceSpec]
    output: Path
    concurrency: int
    chunk_concurrency: int
    chunk_size: int
    rate_limit: int | None
    vip_accel: VipAccelMode
    overwrite: bool
    dry_run: bool
    verbose: bool
    s3_upload: bool
    s3_config: S3Config | None
    delete_local_after_upload: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quark-download")
    parser.add_argument("--config", type=Path)
    auth = parser.add_argument_group("authentication")
    auth.add_argument("--cookie")
    auth.add_argument("--cookie-file", type=Path)

    parser.add_argument("--path")
    parser.add_argument("--fid")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--path-column")
    parser.add_argument("--fid-column")

    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--chunk-concurrency", type=int, default=4)
    parser.add_argument("--chunk-size", type=_parse_size, default=8 * 1024 * 1024)
    parser.add_argument("--rate-limit")
    parser.add_argument("--vip-accel", choices=[mode.value for mode in VipAccelMode], default=VipAccelMode.AUTO.value)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--s3-upload", action="store_true")
    parser.add_argument("--delete-local-after-upload", action="store_true")
    return parser


def build_config(argv: Sequence[str] | None = None) -> Config:
    args = build_parser().parse_args(argv)
    app_config = load_app_config(args.config)
    resources = _load_resources(args)
    cookie = _load_cookie(args.cookie, args.cookie_file, app_config.quark_cookie)
    if args.s3_upload and app_config.s3 is None:
        raise ConfigError("--s3-upload requires [s3] settings in --config.")
    return Config(
        cookie=cookie,
        path=args.path,
        fid=args.fid,
        resources=resources,
        output=args.output,
        concurrency=args.concurrency,
        chunk_concurrency=args.chunk_concurrency,
        chunk_size=args.chunk_size,
        rate_limit=parse_rate_limit(args.rate_limit),
        vip_accel=VipAccelMode(args.vip_accel),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        verbose=args.verbose,
        s3_upload=args.s3_upload,
        s3_config=app_config.s3,
        delete_local_after_upload=args.delete_local_after_upload,
    )


def run(config: Config) -> None:
    failures: list[str] = []
    s3_uploader = S3Uploader(config.s3_config) if config.s3_upload and config.s3_config else None

    with ThreadPoolExecutor(max_workers=max(1, config.concurrency)) as executor:
        futures = [
            executor.submit(_run_resource, config, resource, s3_uploader)
            for resource in config.resources
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except QuarkTransferError as exc:
                failures.append(str(exc))

    if failures:
        raise QuarkTransferError("; ".join(failures))


def _run_resource(config: Config, resource: ResourceSpec, s3_uploader: S3Uploader | None) -> None:
    client = QuarkClient(config.cookie)
    records = resolve_path(client, resource.path) if resource.path else resolve_fid(client, resource.fid or "")
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
        concurrency=1,
        chunk_concurrency=config.chunk_concurrency,
        chunk_size=config.chunk_size,
    )
    if s3_uploader is not None:
        for plan in plans:
            if plan.skip and not plan.destination.exists():
                continue
            if plan.destination.exists():
                s3_uploader.upload_file(plan.destination, relative_to=config.output)
                if config.delete_local_after_upload:
                    plan.destination.unlink()


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


def _load_cookie(cookie: str | None, cookie_file: Path | None, config_cookie: str | None) -> str:
    if cookie or cookie_file:
        return load_cookie(cookie, cookie_file)
    if config_cookie:
        return config_cookie
    return load_cookie(None, None)


def _load_resources(args: argparse.Namespace) -> list[ResourceSpec]:
    single_count = sum(bool(value) for value in [args.path, args.fid])
    if single_count > 1:
        raise SystemExit(2)
    if args.csv:
        if single_count:
            raise ConfigError("--csv cannot be combined with --path or --fid.")
        return load_csv_resources(args.csv, path_column=args.path_column, fid_column=args.fid_column)

    if args.path_column or args.fid_column:
        raise ConfigError("--path-column and --fid-column require --csv.")
    if single_count != 1:
        raise ConfigError("Exactly one of --path, --fid, or --csv is required.")
    return [ResourceSpec(path=args.path, fid=args.fid)]


if __name__ == "__main__":
    raise SystemExit(main())
