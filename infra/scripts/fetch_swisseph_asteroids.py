#!/usr/bin/env python3
"""Fetch Swiss Ephemeris asteroid files required for Chiron calculations.

Downloads `seas_*.se1` files from the official Swiss Ephemeris GitHub mirror:
https://github.com/aloistr/swisseph/tree/master/ephe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

GITHUB_API = "https://api.github.com"
REPO_OWNER = "aloistr"
REPO_NAME = "swisseph"
EPHE_DIR = "ephe"
SEAS_FILE_RE = re.compile(r"^seas_\d+\.se1$")
MANIFEST_NAME = ".swisseph-asteroids-manifest.json"


def _get_json(url: str) -> object:
    request = Request(url, headers={"User-Agent": "voidwire-swiss-fetcher/1.0"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_file(url: str, destination: Path) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "voidwire-swiss-fetcher/1.0"})
    hasher = hashlib.sha256()
    total = 0
    with urlopen(request, timeout=120) as response:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
                hasher.update(chunk)
                total += len(chunk)
    return total, hasher.hexdigest()


def _latest_commit_sha(ref: str) -> str:
    encoded_ref = quote(ref, safe="")
    url = (
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/commits"
        f"?sha={encoded_ref}&path={quote(EPHE_DIR, safe='')}&per_page=1"
    )
    payload = _get_json(url)
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Could not resolve latest Swiss ephe commit SHA")
    head = payload[0]
    if not isinstance(head, dict) or not head.get("sha"):
        raise RuntimeError("Invalid commit payload from GitHub API")
    return str(head["sha"])


def _list_seas_files(ref: str) -> list[dict]:
    encoded_ref = quote(ref, safe="")
    url = (
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/"
        f"{quote(EPHE_DIR, safe='')}?ref={encoded_ref}"
    )
    payload = _get_json(url)
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected response while listing Swiss ephe directory")

    files: list[dict] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        if not SEAS_FILE_RE.match(name):
            continue
        download_url = str(entry.get("download_url") or "").strip()
        if not download_url:
            continue
        files.append({"name": name, "download_url": download_url})
    files.sort(key=lambda item: str(item["name"]))
    if not files:
        raise RuntimeError("No seas_*.se1 files found in Swiss ephe source")
    return files


def _read_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def fetch(dest_dir: Path, ref: str, if_newer: bool) -> int:
    latest_sha = _latest_commit_sha(ref)
    manifest_path = dest_dir / MANIFEST_NAME
    previous_manifest = _read_manifest(manifest_path)
    previous_sha = str(previous_manifest.get("commit_sha", "")).strip()

    if if_newer and previous_sha == latest_sha:
        print(f"Swiss asteroid files already up to date at {latest_sha[:12]}")
        return 0

    files = _list_seas_files(ref)
    staged_dir = Path(tempfile.mkdtemp(prefix="swisseph-asteroids-"))
    download_count = 0
    total_bytes = 0
    manifest_files: list[dict] = []

    try:
        for item in files:
            name = str(item["name"])
            url = str(item["download_url"])
            target = staged_dir / name
            size, sha256 = _download_file(url, target)
            manifest_files.append({"name": name, "size": size, "sha256": sha256, "url": url})
            download_count += 1
            total_bytes += size
            print(f"Fetched {name} ({size} bytes)")

        dest_dir.mkdir(parents=True, exist_ok=True)
        for existing in dest_dir.glob("seas_*.se1"):
            existing.unlink()
        for item in files:
            name = str(item["name"])
            shutil.move(str(staged_dir / name), str(dest_dir / name))

        manifest_payload = {
            "source": f"{REPO_OWNER}/{REPO_NAME}",
            "source_ref": ref,
            "commit_sha": latest_sha,
            "updated_at_utc": datetime.now(UTC).isoformat(),
            "file_count": download_count,
            "total_bytes": total_bytes,
            "files": manifest_files,
        }
        _write_manifest(manifest_path, manifest_payload)
    finally:
        shutil.rmtree(staged_dir, ignore_errors=True)

    print(
        "Swiss asteroid sync complete:",
        f"files={download_count}",
        f"bytes={total_bytes}",
        f"commit={latest_sha[:12]}",
        f"dest={dest_dir}",
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Swiss Ephemeris asteroid files.")
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("/opt/swisseph/ephe"),
        help="Destination directory for seas_*.se1 files (default: /opt/swisseph/ephe).",
    )
    parser.add_argument(
        "--ref",
        type=str,
        default="master",
        help="Git ref (branch/tag/sha) in aloistr/swisseph (default: master).",
    )
    parser.add_argument(
        "--if-newer",
        action="store_true",
        help="Skip download if destination manifest commit matches latest source commit.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        return fetch(dest_dir=args.dest, ref=str(args.ref).strip() or "master", if_newer=bool(args.if_newer))
    except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        print(f"Failed to sync Swiss asteroid files: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
