# Quark Download CLI Design

Date: 2026-05-17

## Goal

Build a Python command-line downloader that downloads resources from the user's own Quark cloud drive into a target directory. The tool authenticates with the user's existing Quark Cookie, accepts either cloud-drive paths or Quark file IDs, resolves folders recursively, and downloads files with concurrent workers, resumable partial files, optional VIP acceleration, and configurable bandwidth limits.

## Non-Goals

- Do not bypass Quark authorization, quotas, membership checks, or server-side speed limits.
- Do not implement account-password login, QR login, browser Cookie extraction, or CAPTCHA handling.
- Do not download resources outside the authenticated user's accessible drive.
- Do not build a GUI.

## User Interface

The CLI will run inside a Python virtual environment and expose a console command such as `quark-download`.

Example commands:

```bash
quark-download --cookie "$QUARK_COOKIE" --path "/资料/课程" --output ./downloads
quark-download --cookie-file cookie.txt --fid abc123 --output ./downloads --concurrency 8
quark-download --path "/电影/big.mkv" --output ./downloads --rate-limit 5M
quark-download --fid abc123 --output ./downloads --vip-accel auto
```

Core options:

- `--cookie`: Quark Cookie string.
- `--cookie-file`: File containing the Quark Cookie.
- `QUARK_COOKIE`: Environment fallback when no Cookie flag is provided.
- `--path`: Cloud-drive path to a file or folder.
- `--fid`: Quark file or folder ID.
- `--output`: Required local destination directory.
- `--concurrency`: Number of files downloaded concurrently.
- `--chunk-concurrency`: Number of byte-range chunks per large file.
- `--chunk-size`: Size of each ranged chunk.
- `--rate-limit`: Global bandwidth cap such as `500K`, `5M`, or `0` for unlimited.
- `--vip-accel`: `auto`, `on`, or `off`. Default is `auto`.
- `--overwrite`: Replace complete destination files.
- `--dry-run`: Resolve resources and print the planned downloads without downloading.
- `--verbose`: More detailed logs.

Exactly one of `--path` or `--fid` is required for each invocation.

## Architecture

The implementation will be split into small modules with clear boundaries:

- `cli`: Parses arguments, loads configuration, validates inputs, configures logging, and maps exceptions to user-facing exit codes.
- `auth`: Loads Cookie values from CLI, file, or environment and validates that an auth source exists.
- `api`: Wraps Quark HTTP endpoints. It will expose methods for listing folders, looking up paths, retrieving file metadata, and requesting download URLs.
- `resolver`: Converts a `--path` or `--fid` into a deterministic list of downloadable file records. Folder resolution is recursive.
- `planner`: Converts resolved file records into local download plans, handling destination paths, existing files, `.part` files, and overwrite policy.
- `downloader`: Executes plans with file-level concurrency, optional range chunking, retry handling, resume support, progress reporting, and rate limiting.
- `throttle`: Implements a shared token-bucket limiter used by all download workers.

The API layer is intentionally isolated so Quark endpoint changes can be fixed without rewriting CLI or downloader logic.

## Authentication

Authentication uses the user's Cookie only. Precedence is:

1. `--cookie`
2. `--cookie-file`
3. `QUARK_COOKIE`

The Cookie is passed only to Quark API and download URL requests. Logs must not print the Cookie or complete signed download URLs.

## Resource Resolution

For `--fid`, the resolver fetches metadata for that ID. If it is a file, it creates one download record. If it is a folder, it recursively lists children.

For `--path`, the resolver splits the path into segments and walks the user's drive tree through the API wrapper. The final node may be either a file or folder. Resolution errors include clear messages for missing paths, ambiguous names if Quark returns duplicates, and permission/auth failures.

Resolved file records include:

- Quark file ID
- Name
- Size
- Parent path relative to the requested root
- Hash or revision metadata when available
- Download URL metadata request parameters

## Download Behavior

Downloads write to temporary `.part` files first and atomically rename to the final path after validation. Existing complete files are skipped when size matches unless `--overwrite` is set.

Large files can use HTTP Range requests. The planner will create chunk tasks when the download URL supports ranges and the file is above the configured threshold. Chunks are written into the correct offsets in the `.part` file.

Resume behavior:

- If a `.part` file exists and the expected size is known, the downloader resumes missing ranges when possible.
- If range support is unavailable, it restarts the incomplete file.
- A small sidecar state file may record completed chunks to avoid rechecking the whole file on restart.

Retries use bounded exponential backoff for transient network, 429, and 5xx failures. Authentication failures, missing resources, and invalid arguments fail fast.

## VIP Acceleration

`--vip-accel` controls how download URL requests ask Quark for accelerated URLs when the authenticated account is eligible.

- `auto`: Prefer accelerated URLs if Quark returns them; fall back to normal URLs if not available.
- `on`: Require accelerated URL support. If Quark does not return an accelerated URL, fail with a clear message.
- `off`: Request and use normal download URLs only.

The tool will not claim to bypass Quark speed limits. VIP acceleration means using official download URL fields or request parameters available to the authenticated user's account. The API wrapper will keep this decision explicit so tests can verify fallback and failure behavior.

## Rate Limiting

`--rate-limit` applies a global cap across all concurrent files and chunks. It is implemented in the downloader through a shared token bucket, not by reducing worker counts. This keeps concurrency useful for latency while respecting the configured throughput.

Accepted units:

- `K` or `KB`: kibibytes per second
- `M` or `MB`: mebibytes per second
- `0`, `none`, or omitted: unlimited

Invalid values fail before any network requests are made.

## Error Handling

The CLI will use stable non-zero exit codes:

- `1`: General runtime failure.
- `2`: Invalid CLI arguments or configuration.
- `3`: Authentication expired or unauthorized.
- `4`: Resource not found.
- `5`: Download failed after retries.

Errors should include actionable messages. Sensitive auth data must be redacted.

## Testing Strategy

Development will follow test-driven development. Unit tests will cover:

- Cookie source precedence and missing-auth errors.
- Path splitting and path-to-file resolution using a fake API.
- Recursive folder expansion using a fake API.
- Download planning for existing files, `.part` files, and overwrite behavior.
- Rate-limit parsing and token-bucket behavior.
- VIP acceleration modes: auto fallback, on failure, off normal URL selection.
- Retry classification for transient and fatal errors.

Downloader tests will avoid real Quark traffic by using local fake HTTP responses or injected transport adapters. Real-account integration tests, if added, will be opt-in and skipped unless `QUARK_COOKIE` is present.

## Packaging

The project will use a Python virtual environment and a standard package layout:

```text
pyproject.toml
README.md
src/quark_transfer/
tests/
```

The package will define a console script entry point:

```text
quark-download = quark_transfer.cli:main
```

Runtime dependencies should stay small. The first implementation should prefer `requests` plus the Python standard library unless tests or endpoint behavior justify `httpx`.

## Open Implementation Risks

- Quark private API endpoints and request parameters may change, so the API wrapper must be isolated and covered by tests around expected request/response shapes.
- VIP acceleration fields may vary by account status or resource type; `auto` must degrade gracefully.
- Some signed download URLs may not support HTTP Range. The downloader must detect this and fall back to whole-file downloads.
- Very high concurrency can trigger Quark throttling. Defaults should be conservative, with user-configurable limits.
