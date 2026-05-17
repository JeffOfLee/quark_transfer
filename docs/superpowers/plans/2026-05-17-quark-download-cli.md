# Quark Download CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python venv-friendly CLI that downloads the authenticated user's Quark cloud-drive files or folders by path or fid with concurrency, resumable `.part` files, VIP URL selection, and global rate limiting.

**Architecture:** Use a focused package under `src/quark_transfer/`. Keep Quark private API calls in `api.py`, resource traversal in `resolver.py`, local-file decisions in `planner.py`, and byte transfer behavior in `downloader.py`. CLI code composes these pieces and keeps auth data redacted.

**Tech Stack:** Python 3.11+, `requests`, `pytest`, standard-library `argparse`, `concurrent.futures`, `dataclasses`, and `pathlib`.

---

## File Structure

- `pyproject.toml`: package metadata, console script, pytest config.
- `README.md`: setup and usage instructions.
- `src/quark_transfer/__init__.py`: package version.
- `src/quark_transfer/errors.py`: typed exceptions and CLI exit codes.
- `src/quark_transfer/models.py`: shared dataclasses and enums.
- `src/quark_transfer/auth.py`: Cookie source loading.
- `src/quark_transfer/rate_limit.py`: rate-limit parser and token bucket.
- `src/quark_transfer/api.py`: Quark HTTP API wrapper.
- `src/quark_transfer/resolver.py`: path/fid resolution and recursive folder expansion.
- `src/quark_transfer/planner.py`: local destination planning and resume metadata.
- `src/quark_transfer/downloader.py`: concurrent downloads, retries, range support, and atomic completion.
- `src/quark_transfer/cli.py`: command-line parser and orchestration.
- `tests/`: unit tests using fakes and local HTTP-free behavior.

## Task 1: Package Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/quark_transfer/__init__.py`

- [ ] **Step 1: Write the failing packaging check**

Run: `python -m pytest -q`

Expected: FAIL because `pytest` is not configured and no package files exist.

- [ ] **Step 2: Create package metadata**

Add `pyproject.toml` with project metadata, `requests` dependency, `pytest` dev extra, and `quark-download = quark_transfer.cli:main`.

- [ ] **Step 3: Add minimal package and README**

Add `src/quark_transfer/__init__.py` with `__version__ = "0.1.0"` and `README.md` with venv setup plus CLI examples.

- [ ] **Step 4: Verify package discovery**

Run: `python -m pytest -q`

Expected: PASS with no tests collected or test suite ready once later tests exist.

## Task 2: Auth and Rate-Limit Foundation

**Files:**
- Create: `src/quark_transfer/errors.py`
- Create: `src/quark_transfer/auth.py`
- Create: `src/quark_transfer/rate_limit.py`
- Test: `tests/test_auth.py`
- Test: `tests/test_rate_limit.py`

- [ ] **Step 1: Write failing auth tests**

Test Cookie precedence: explicit Cookie, Cookie file, environment, and missing auth raising `ConfigError`.

- [ ] **Step 2: Implement auth loading**

Implement `load_cookie(cookie, cookie_file, env=os.environ)` with whitespace trimming and no logging.

- [ ] **Step 3: Write failing rate-limit parser tests**

Test `None`, `0`, `none`, `500K`, `5M`, invalid strings, and lowercase units.

- [ ] **Step 4: Implement parser and token bucket**

Implement `parse_rate_limit(value) -> int | None` and `TokenBucket.consume(size)` with a monotonic-clock wait loop.

- [ ] **Step 5: Verify**

Run: `python -m pytest tests/test_auth.py tests/test_rate_limit.py -q`

Expected: PASS.

## Task 3: Data Models and API Wrapper

**Files:**
- Create: `src/quark_transfer/models.py`
- Create: `src/quark_transfer/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Use a fake session to verify file listing calls `https://drive-pc.quark.cn/1/clouddrive/file/sort`, passes Cookie headers, paginates until all files are returned, and raises `AuthError` for auth failures.

- [ ] **Step 2: Implement models**

Define `CloudItem`, `DownloadRecord`, `DownloadUrl`, and `VipAccelMode`.

- [ ] **Step 3: Implement QuarkClient listing**

Implement `list_folder(parent_fid)` and `_request_json()`, with response-code validation and pagination.

- [ ] **Step 4: Write failing download URL tests**

Verify `vip_accel=auto` prefers accelerated fields and falls back, `on` requires accelerated fields, and `off` chooses normal fields.

- [ ] **Step 5: Implement download URL selection**

Implement `get_download_url(fid, vip_accel)` using `POST https://drive.quark.cn/1/clouddrive/file/download?pr=ucpro&fr=pc` and response field selection.

- [ ] **Step 6: Verify**

Run: `python -m pytest tests/test_api.py -q`

Expected: PASS.

## Task 4: Resolver

**Files:**
- Create: `src/quark_transfer/resolver.py`
- Test: `tests/test_resolver.py`

- [ ] **Step 1: Write failing resolver tests**

Use a fake client tree to test path splitting, root traversal, file result, recursive folder expansion, not found, and ambiguous duplicate names.

- [ ] **Step 2: Implement resolver**

Implement `resolve_path(client, path)` and `resolve_fid(client, fid)` returning ordered `DownloadRecord` values.

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/test_resolver.py -q`

Expected: PASS.

## Task 5: Planner

**Files:**
- Create: `src/quark_transfer/planner.py`
- Test: `tests/test_planner.py`

- [ ] **Step 1: Write failing planner tests**

Test output paths, nested folder preservation, skip existing same-size files, overwrite behavior, and `.part` resume detection.

- [ ] **Step 2: Implement planner**

Implement `build_download_plans(records, output_dir, overwrite=False)` with `DownloadPlan` dataclass.

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/test_planner.py -q`

Expected: PASS.

## Task 6: Downloader

**Files:**
- Create: `src/quark_transfer/downloader.py`
- Test: `tests/test_downloader.py`

- [ ] **Step 1: Write failing downloader tests**

Use fake HTTP responses to test complete download writes `.part` then renames, skipped plans are ignored, transient errors retry, and fatal errors raise `DownloadError`.

- [ ] **Step 2: Implement minimal downloader**

Implement whole-file streaming first with file-level concurrency and token bucket consumption.

- [ ] **Step 3: Write failing range tests**

Test range-supported large files create chunk headers and write correct offsets.

- [ ] **Step 4: Implement range downloads**

Implement chunk planning, `Range` header requests, and fallback to whole-file when range is not supported.

- [ ] **Step 5: Verify**

Run: `python -m pytest tests/test_downloader.py -q`

Expected: PASS.

## Task 7: CLI Integration

**Files:**
- Create: `src/quark_transfer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Test parser rejects both `--path` and `--fid`, requires output, maps `--vip-accel`, parses `--rate-limit`, and redacts Cookie in errors.

- [ ] **Step 2: Implement CLI parser and orchestration**

Implement `main(argv=None)` and `run(config)` to compose auth, client, resolver, planner, and downloader.

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/test_cli.py -q`

Expected: PASS.

## Task 8: Docs and Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Document venv creation, installation, Cookie sources, path/fid examples, VIP acceleration modes, rate limiting, resume behavior, and safety constraints.

- [ ] **Step 2: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 3: Commit implementation**

Run:

```bash
git add pyproject.toml README.md src tests docs/superpowers/plans/2026-05-17-quark-download-cli.md
git commit -m "Implement Quark download CLI"
```

Expected: commit succeeds.

## Self-Review

Spec coverage:

- Cookie auth: Task 2 and Task 7.
- Path and fid resolution: Task 4 and Task 7.
- Concurrent/resumable downloads: Task 5 and Task 6.
- VIP acceleration: Task 3 and Task 7.
- Rate limiting: Task 2 and Task 6.
- Packaging and venv usage: Task 1 and Task 8.

Placeholder scan: no TBD/TODO placeholders are intentionally left in this plan.

Type consistency: `CloudItem`, `DownloadRecord`, `DownloadUrl`, `DownloadPlan`, `VipAccelMode`, `QuarkClient`, `ConfigError`, `AuthError`, `NotFoundError`, and `DownloadError` are introduced before downstream usage.
