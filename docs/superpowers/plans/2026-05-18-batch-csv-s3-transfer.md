# Batch CSV S3 Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CSV batch input, config-file secrets, resource-level concurrency, and optional upload of downloaded videos to S3.

**Architecture:** Add focused modules for TOML config loading, CSV task loading, batch orchestration, and S3 uploading. Keep existing single-resource download behavior intact by converting all inputs into resource specs and reusing resolver/planner/downloader boundaries.

**Tech Stack:** Python 3.11+ standard library `csv`, `tomllib`, `concurrent.futures`; optional runtime dependency `boto3` for S3 uploads; existing `pytest` suite.

---

## Tasks

- [ ] Add config loader tests and `config.py` for `[quark]` and `[s3]`.
- [ ] Add CSV loader tests and `batch.py` resource specs.
- [ ] Add S3 uploader tests and `s3.py` using injectable boto3 clients.
- [ ] Refactor CLI config parsing to accept `--config`, `--csv`, `--path-column`, `--fid-column`, `--s3-upload`, and `--delete-local-after-upload`.
- [ ] Add batch orchestration tests for per-resource success/failure and non-zero aggregate failure.
- [ ] Update README and run full verification.
