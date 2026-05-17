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
quark-download --config config.toml --csv tasks.csv --path-column quark_path --output ./downloads --concurrency 4
quark-download --config config.toml --csv tasks.csv --fid-column fid --output ./downloads --s3-upload
quark-download --config config.toml --csv tasks.csv --path-column quark_path --output ./downloads --s3-upload --meta result.csv --verbose
```

Exactly one of `--path`, `--fid`, or `--csv` is required.

## Config File

Use `--config config.toml` to load Quark Cookie and S3 settings.

```toml
[quark]
cookie = "b-user-id=...; __uid=...; __puus=..."

[s3]
bucket = "my-bucket"
prefix = "videos/"
region = "ap-southeast-1"
endpoint_url = ""
access_key_id = "..."
secret_access_key = "..."
```

`endpoint_url` can be empty for AWS S3. Set it for S3-compatible services such as MinIO, R2, or other object storage endpoints.

## Cookie Sources

Cookie lookup order:

1. `--cookie`
2. `--cookie-file`
3. `[quark].cookie` from `--config`
4. `QUARK_COOKIE`

The tool redacts Cookie-like values from user-facing error output. Avoid committing Cookie files.

## Concurrency

`--concurrency` controls how many top-level resources download at the same time. With `--csv`, each row is one resource.

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

## CSV Batch Input

CSV files must have a header row. Select the resource column explicitly:

```csv
quark_path
films_download_temp/赵子龙_tt13575948
films_download_temp/另一个资源
```

```bash
quark-download --config config.toml --csv tasks.csv --path-column quark_path --output ./downloads
```

For file IDs:

```csv
fid
2e327817fefb4c20ad89f27ad3fbead5
```

```bash
quark-download --config config.toml --csv tasks.csv --fid-column fid --output ./downloads
```

If any row fails, remaining rows continue. The command exits non-zero after the batch if one or more resources failed.

## S3 Upload

Add `--s3-upload` to upload each successfully downloaded file to the configured S3 bucket.

```bash
quark-download --config config.toml --csv tasks.csv --path-column quark_path --output ./downloads --s3-upload
```

S3 object keys use this rule:

```text
{prefix}/{sha256(path)}.{ext}
```

For path-based tasks, the hash input is the Quark path plus the expanded nested filename. For fid-based tasks, the hash input uses the fid plus the expanded nested filename. The extension is preserved from the local filename.

Add `--delete-local-after-upload` to remove the local file after a successful upload:

```bash
quark-download --config config.toml --fid abc123 --output ./downloads --s3-upload --delete-local-after-upload
```

With `--verbose`, uploads log the S3 key, file size, duration, upload rate, and result.

## Metadata CSV

Use `--meta result.csv` to write transfer metadata:

```bash
quark-download --config config.toml --csv tasks.csv --path-column quark_path --output ./downloads --s3-upload --meta result.csv
```

Columns:

```csv
path,fid,video_size,video_format,key,upload_start_time,upload_end_time,transfer_status,error_message
```

`transfer_status` is values such as `downloaded`, `uploaded`, `skip`, or `failed`. `error_message` is populated for failed resources.

## Resume Behavior

Downloads write to `*.part` files and rename them after success. If a `.part` file already exists, the downloader requests the remaining bytes with HTTP Range when possible.

Existing complete files with the expected size are skipped unless `--overwrite` is set.

## Notes

Quark's web APIs are private and may change. Endpoint-specific behavior is isolated in `quark_transfer.api.QuarkClient` to keep future fixes contained.
