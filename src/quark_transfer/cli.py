from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .api import QuarkClient
from .auth import load_cookie
from .batch import ResourceSpec, load_csv_resources
from .config import S3Config, load_app_config
from .downloader import download_files
from .errors import ConfigError, QuarkTransferError
from .meta import MetaRow, write_meta_csv
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
    meta_path: Path | None
    meta_row_factory: type[MetaRow] = MetaRow


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
    parser.add_argument(
        "--delete-local-after-upload",
        "--delete",
        dest="delete_local_after_upload",
        action="store_true",
        help="Delete local video files after successful S3 upload.",
    )
    parser.add_argument("--meta", dest="meta_path", type=Path)
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
        meta_path=args.meta_path,
    )


def run(config: Config) -> None:
    failures: list[str] = []
    meta_rows: list[MetaRow] = []
    s3_uploader = S3Uploader(config.s3_config) if config.s3_upload and config.s3_config else None

    with ThreadPoolExecutor(max_workers=max(1, config.concurrency)) as executor:
        futures = {
            executor.submit(_run_resource, config, resource, s3_uploader): resource
            for resource in config.resources
        }
        for future in as_completed(futures):
            resource = futures[future]
            try:
                meta_rows.extend(future.result() or [])
            except QuarkTransferError as exc:
                failures.append(str(exc))
                meta_rows.append(
                    config.meta_row_factory(
                        path=resource.path or "",
                        fid=resource.fid or "",
                        video_size=0,
                        video_format="",
                        key="",
                        upload_start_time="",
                        upload_end_time="",
                        transfer_status="failed",
                        error_message=str(exc),
                    )
                )

    if config.meta_path is not None:
        write_meta_csv(config.meta_path, meta_rows)
    if failures:
        raise QuarkTransferError("; ".join(failures))


def _run_resource(config: Config, resource: ResourceSpec, s3_uploader: S3Uploader | None) -> list[MetaRow]:
    _log(config, f"resource start path={resource.path or ''} fid={resource.fid or ''}")
    client = QuarkClient(config.cookie)
    records = resolve_path(client, resource.path) if resource.path else resolve_fid(client, resource.fid or "")
    plans = build_download_plans(records, config.output, overwrite=config.overwrite)
    meta_rows: list[MetaRow] = []

    if config.dry_run:
        for plan in plans:
            status = "skip" if plan.skip else "download"
            print(f"{status}\t{plan.record.size}\t{plan.destination}")
            meta_rows.append(_meta_row(config, resource, plan, transfer_status=status))
        return meta_rows

    bucket = TokenBucket(config.rate_limit)
    download_files(
        plans,
        lambda record: client.get_download_url(record.fid, config.vip_accel),
        bucket=bucket,
        concurrency=1,
        chunk_concurrency=config.chunk_concurrency,
        chunk_size=config.chunk_size,
    )
    for plan in plans:
        _log(config, f"download complete path={plan.destination} size={plan.record.size}")

    if s3_uploader is not None:
        for plan in plans:
            if plan.skip and not plan.destination.exists():
                continue
            if plan.destination.exists():
                _log(config, f"s3 upload start path={plan.destination}")
                upload_result = s3_uploader.upload_file(
                    plan.destination,
                    hash_source=_hash_source(resource, plan, config.output),
                )
                _log(
                    config,
                    "s3 upload complete "
                    f"key={upload_result.key} size={upload_result.bytes_uploaded} "
                    f"duration={upload_result.duration_seconds:.2f}s "
                    f"rate={_mib_per_second(upload_result.bytes_per_second):.2f} MiB/s",
                )
                meta_rows.append(
                    _meta_row(
                        config,
                        resource,
                        plan,
                        key=upload_result.key,
                        upload_start_time=_iso_time(upload_result.start_time),
                        upload_end_time=_iso_time(upload_result.end_time),
                        transfer_status="uploaded",
                    )
                )
                if config.delete_local_after_upload:
                    plan.destination.unlink()
    else:
        meta_rows.extend(_meta_row(config, resource, plan, transfer_status="downloaded") for plan in plans)
    _log(config, f"resource complete path={resource.path or ''} fid={resource.fid or ''}")
    return meta_rows


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


def _hash_source(resource: ResourceSpec, plan, output: Path | None = None) -> str:
    base = resource.path or resource.fid or plan.record.fid
    if output is not None:
        try:
            relative = plan.destination.relative_to(output).as_posix()
            return f"{base}/{relative}"
        except ValueError:
            pass
    relative = plan.destination.name
    try:
        # Preserve nested paths below output when available.
        parts = plan.destination.parts
        if not plan.destination.is_absolute() and len(parts) >= 2:
            relative = "/".join(parts[1:])
    except Exception:
        relative = plan.destination.name
    return f"{base}/{relative}"


def _meta_row(
    config: Config,
    resource: ResourceSpec,
    plan,
    *,
    key: str = "",
    upload_start_time: str = "",
    upload_end_time: str = "",
    transfer_status: str,
    error_message: str = "",
) -> MetaRow:
    suffix = plan.destination.suffix[1:]
    return config.meta_row_factory(
        path=resource.path or "",
        fid=plan.record.fid,
        video_size=plan.record.size,
        video_format=suffix,
        key=key,
        upload_start_time=upload_start_time,
        upload_end_time=upload_end_time,
        transfer_status=transfer_status,
        error_message=error_message,
    )


def _iso_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def _mib_per_second(bytes_per_second: float) -> float:
    return bytes_per_second / 1024 / 1024


def _log(config: Config, message: str) -> None:
    if config.verbose:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
