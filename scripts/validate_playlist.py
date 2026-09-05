#!/usr/bin/env python3
"""Validate the generated UHF playlist before publishing it."""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYLIST_PATH = ROOT / "docs" / "tv-uhf.m3u8"
STATUS_PATH = ROOT / "docs" / "status.json"
LOGO_PREFIX = "https://carlosciller.github.io/uhf-playlist/logos/"
ATTRIBUTE_RE = re.compile(r'([\w-]+)="([^"]*)"')


def fail(message: str) -> None:
    raise SystemExit(f"Playlist validation failed: {message}")


def main() -> None:
    lines = PLAYLIST_PATH.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("#EXTM3U "):
        fail("missing extended M3U header")
    if 'url-tvg="https://' not in lines[0]:
        fail("missing HTTPS EPG URL")

    channel_count = 0
    pending_channel = False
    channel_keys: set[str] = set()
    logo_urls: set[str] = set()
    for line_number, line in enumerate(lines[1:], start=2):
        if not line:
            continue
        if line.startswith("#EXTINF"):
            if pending_channel:
                fail(f"channel at line {line_number - 1} has no stream URL")
            channel_count += 1
            pending_channel = True
            attrs = dict(ATTRIBUTE_RE.findall(line))
            display_name = line.rsplit(",", 1)[-1].strip()
            channel_keys.add(attrs.get("tvg-id") or attrs.get("tvg-name") or display_name)
            logo_url = attrs.get("tvg-logo")
            if logo_url:
                if not logo_url.startswith(LOGO_PREFIX):
                    fail(f"channel at line {line_number} uses an external logo")
                logo_name = urllib.parse.unquote(logo_url.removeprefix(LOGO_PREFIX))
                logo_path = ROOT / "docs" / "logos" / logo_name
                if not logo_path.is_file() or logo_path.stat().st_size <= 100:
                    fail(f"missing cached logo: {logo_name}")
                logo_urls.add(logo_url)
            continue
        if line.startswith("#"):
            continue
        if not line.startswith(("https://", "http://")):
            fail(f"invalid stream URL at line {line_number}")
        if not pending_channel:
            fail(f"orphan stream URL at line {line_number}")
        pending_channel = False

    if pending_channel:
        fail("last channel has no stream URL")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    extras = json.loads((ROOT / "extra_channels.json").read_text(encoding="utf-8"))
    extra_count = len(extras)
    expected = {
        "channels": channel_count,
        "source_channels": channel_count - extra_count,
        "curated_extra_channels": extra_count,
        "curated_uhd_channels": sum(
            str(channel.get("quality", "")).lower() in {"2160p", "4k", "uhd"}
            for channel in extras
        ),
        "curated_hdr_channels": sum(
            str(channel.get("dynamic_range", "")).upper()
            in {"HDR", "HLG", "PQ", "HDR10"}
            for channel in extras
        ),
        "unique_channels": len(channel_keys),
        "self_hosted_logos": len(logo_urls),
        "uncached_logos": len(channel_keys) - len(logo_urls),
    }
    for field, value in expected.items():
        if status.get(field) != value:
            fail(f"status field {field!r} is {status.get(field)!r}, expected {value!r}")
    expected_coverage = round(len(logo_urls) * 100 / len(channel_keys), 1)
    if status.get("logo_coverage_percent") != expected_coverage:
        fail("logo coverage does not match the generated playlist")

    print(
        f"Validated {channel_count} streams, {len(channel_keys)} channels, "
        f"and {len(logo_urls)} self-hosted logos."
    )


if __name__ == "__main__":
    main()
