# Quark Transfer

Python CLI for downloading resources from the authenticated user's own Quark cloud drive.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

After installation, the console command is:

```bash
quark-download --help
```

## Usage

```bash
quark-download --cookie "$QUARK_COOKIE" --path "/资料/课程" --output ./downloads
quark-download --cookie-file cookie.txt --fid abc123 --output ./downloads --concurrency 8
quark-download --path "/电影/big.mkv" --output ./downloads --rate-limit 5M
quark-download --fid abc123 --output ./downloads --vip-accel auto
```

Exactly one of `--path` or `--fid` is required.

## Cookie Sources

Cookie lookup order:

1. `--cookie`
2. `--cookie-file`
3. `QUARK_COOKIE`

The tool redacts Cookie-like values from user-facing error output. Avoid committing Cookie files.

## Concurrency

`--concurrency` controls how many files download at the same time.

`--chunk-concurrency` controls how many byte ranges a large file may download concurrently.

`--chunk-size` accepts byte sizes with optional `K`, `KB`, `M`, or `MB` suffixes.

## VIP Acceleration

`--vip-accel` supports:

- `auto`: prefer an accelerated URL when Quark returns one, otherwise use the normal URL.
- `on`: require an accelerated URL and fail if it is unavailable.
- `off`: always use the normal URL.

VIP acceleration only uses download URL fields returned for the authenticated account. The tool does not bypass Quark authorization, membership checks, quotas, or server-side speed limits.

## Rate Limiting

`--rate-limit` applies a global bandwidth cap across all file and chunk workers.

Examples:

```bash
quark-download --fid abc123 --output ./downloads --rate-limit 500K
quark-download --fid abc123 --output ./downloads --rate-limit 5M
quark-download --fid abc123 --output ./downloads --rate-limit 0
```

`0`, `none`, or an omitted value means unlimited.

## Resume Behavior

Downloads write to `*.part` files and rename them after success. If a `.part` file already exists, the downloader requests the remaining bytes with HTTP Range when possible.

Existing complete files with the expected size are skipped unless `--overwrite` is set.

## Notes

Quark's web APIs are private and may change. Endpoint-specific behavior is isolated in `quark_transfer.api.QuarkClient` to keep future fixes contained.
