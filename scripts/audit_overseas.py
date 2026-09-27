#!/usr/bin/env python3
"""Audit HLS streams from the current network and save a location snapshot."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYLIST_PATH = ROOT / "docs" / "tv-uhf.m3u8"
OUTPUT_PATH = ROOT / "overseas_access.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
STREAM_INFO_RE = re.compile(r"(?:BANDWIDTH|AVERAGE-BANDWIDTH)=(\d+)")
URI_ATTRIBUTE_RE = re.compile(r'URI="([^"]+)"')


def playlist_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def stream_url(block: list[str]) -> str:
    return next(
        (line for line in block[1:] if line and not line.startswith("#")), ""
    )


def request_headers(block: list[str]) -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,*/*",
    }
    for line in block:
        if line.startswith("#EXTVLCOPT:http-referrer="):
            headers["Referer"] = line.split("=", 1)[1]
        elif line.startswith("#EXTVLCOPT:http-user-agent="):
            headers["User-Agent"] = line.split("=", 1)[1]
    return headers


def fetch(url: str, headers: dict[str, str], limit: int) -> tuple[bytes, str, int]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=12) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            data = data[:limit]
        return data, response.geturl(), response.status


def master_variants(manifest: str) -> list[tuple[int, str]]:
    variants: list[tuple[int, str]] = []
    lines = manifest.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF"):
            continue
        bandwidth_match = STREAM_INFO_RE.search(line)
        bandwidth = int(bandwidth_match.group(1)) if bandwidth_match else 0
        for candidate in lines[index + 1 :]:
            candidate = candidate.strip()
            if not candidate or candidate.startswith("#"):
                continue
            variants.append((bandwidth, candidate))
            break
    return sorted(variants, reverse=True)


def media_candidates(manifest: str) -> list[str]:
    candidates: list[str] = []
    for line in manifest.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#EXT-X-MAP:", "#EXT-X-PART:")):
            match = URI_ATTRIBUTE_RE.search(stripped)
            if match:
                candidates.append(match.group(1))
        elif not stripped.startswith("#"):
            candidates.append(stripped)
    return candidates


def safe_error(error: Exception) -> tuple[str, int | None]:
    if isinstance(error, urllib.error.HTTPError):
        return f"http_{error.code}", error.code
    if isinstance(error, urllib.error.URLError):
        reason = error.reason
        if isinstance(reason, socket.timeout):
            return "timeout", None
        if isinstance(reason, ssl.SSLError):
            return "tls_error", None
        if isinstance(reason, socket.gaierror):
            return "dns_error", None
        return "connection_error", None
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "timeout", None
    return type(error).__name__.lower(), None


def audit_block(block: list[str]) -> tuple[str, dict[str, object]]:
    url = stream_url(block)
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    result: dict[str, object] = {
        "reachable": False,
        "checked_at": checked_at,
    }
    if not url:
        result["error"] = "missing_url"
        return url, result

    headers = request_headers(block)
    try:
        raw, final_url, status = fetch(url, headers, 768_000)
        result["manifest_status"] = status
        manifest = raw.decode("utf-8-sig", "replace")
        if "#EXTM3U" not in manifest:
            result["error"] = "not_hls"
            return url, result

        variants = master_variants(manifest)
        if variants:
            _, variant = variants[0]
            variant_url = urllib.parse.urljoin(final_url, variant)
            raw, final_url, status = fetch(variant_url, headers, 768_000)
            result["variant_status"] = status
            manifest = raw.decode("utf-8-sig", "replace")
            if "#EXTM3U" not in manifest:
                result["error"] = "invalid_variant"
                return url, result

        candidates = media_candidates(manifest)
        if not candidates:
            result["error"] = "no_media_uri"
            return url, result

        media_url = urllib.parse.urljoin(final_url, candidates[-1])
        media_headers = dict(headers)
        media_headers["Range"] = "bytes=0-4095"
        media, _, status = fetch(media_url, media_headers, 65_536)
        result["media_status"] = status
        if not media:
            result["error"] = "empty_media"
            return url, result
        result["reachable"] = True
        result["error"] = None
        return url, result
    except Exception as error:
        reason, status = safe_error(error)
        result["error"] = reason
        if status is not None:
            result["http_status"] = status
        return url, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="Overseas")
    parser.add_argument("--workers", type=int, default=24)
    args = parser.parse_args()

    lines = PLAYLIST_PATH.read_text(encoding="utf-8").splitlines()
    blocks = playlist_blocks(lines)
    streams: dict[str, dict[str, object]] = {}
    completed = 0
    workers = max(1, min(args.workers, 32))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(audit_block, block) for block in blocks]
        for future in concurrent.futures.as_completed(futures):
            url, result = future.result()
            if url:
                streams[url] = result
            completed += 1
            if completed % 50 == 0 or completed == len(blocks):
                reachable = sum(bool(item["reachable"]) for item in streams.values())
                print(f"Audited {completed}/{len(blocks)}; reachable: {reachable}")

    host_summary: dict[str, dict[str, int]] = {}
    for url, result in streams.items():
        host = urllib.parse.urlparse(url).hostname or ""
        counts = host_summary.setdefault(host, {"reachable": 0, "unreachable": 0})
        key = "reachable" if result["reachable"] else "unreachable"
        counts[key] += 1

    reachable_count = sum(bool(item["reachable"]) for item in streams.values())
    output = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "location_label": args.label,
        "summary": {
            "streams": len(streams),
            "reachable": reachable_count,
            "unreachable": len(streams) - reachable_count,
        },
        "hosts": dict(sorted(host_summary.items())),
        "streams": dict(sorted(streams.items())),
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
