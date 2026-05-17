# Quark Transfer

Python CLI for downloading resources from the authenticated user's own Quark cloud drive.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Usage

```bash
quark-download --cookie "$QUARK_COOKIE" --path "/资料/课程" --output ./downloads
quark-download --cookie-file cookie.txt --fid abc123 --output ./downloads --concurrency 8
quark-download --path "/电影/big.mkv" --output ./downloads --rate-limit 5M
quark-download --fid abc123 --output ./downloads --vip-accel auto
```

The tool only uses the authenticated user's Cookie and does not bypass Quark authorization, membership checks, quotas, or server-side speed limits.

