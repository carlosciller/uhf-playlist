#!/usr/bin/env python3
"""Build a location-tested UHF playlist from the full published playlist."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
SOURCE_PATH = DOCS_DIR / "tv-uhf.m3u8"
ACCESS_PATH = ROOT / "overseas_access.json"
OUTPUT_PATH = DOCS_DIR / "tv-uhf-overseas.m3u8"
STATUS_PATH = DOCS_DIR / "overseas-status.json"
ATTRIBUTE_RE = re.compile(r'([\w-]+)="([^"]*)"')


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


def channel_key(block: list[str]) -> str:
    attrs = dict(ATTRIBUTE_RE.findall(block[0]))
    return attrs.get("tvg-id") or attrs.get("tvg-name") or block[0].rsplit(",", 1)[-1]


def main() -> None:
    source_lines = SOURCE_PATH.read_text(encoding="utf-8").splitlines()
    if not source_lines or not source_lines[0].startswith("#EXTM3U"):
        raise SystemExit("Full playlist has no valid M3U header")
    access = json.loads(ACCESS_PATH.read_text(encoding="utf-8"))
    tested_streams = access.get("streams", {})
    if not isinstance(tested_streams, dict) or not tested_streams:
        raise SystemExit("Overseas access snapshot contains no streams")

    blocks = playlist_blocks(source_lines)
    included = [
        block
        for block in blocks
        if bool(tested_streams.get(stream_url(block), {}).get("reachable"))
    ]
    if not included:
        raise SystemExit("No location-tested streams remain")

    output_lines = [source_lines[0]]
    for block in included:
        output_lines.extend(block)
    OUTPUT_PATH.write_text(
        "\n".join(output_lines).rstrip() + "\n", encoding="utf-8"
    )

    quality_counts = {"UHD": 0, "FHD": 0, "HD": 0, "SD": 0, "unknown": 0}
    for block in included:
        quality = dict(ATTRIBUTE_RE.findall(block[0])).get("quality", "")
        quality_counts[quality or "unknown"] = quality_counts.get(quality or "unknown", 0) + 1
    status = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_playlist": SOURCE_PATH.name,
        "audit_generated_at": access.get("generated_at"),
        "location_label": access.get("location_label", "Overseas"),
        "media_segment_tested": True,
        "source_streams": len(blocks),
        "included_streams": len(included),
        "excluded_streams": len(blocks) - len(included),
        "unique_channels": len({channel_key(block) for block in included}),
        "quality_profiles": quality_counts,
    }
    STATUS_PATH.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
