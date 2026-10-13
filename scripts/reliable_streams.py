"""Retain a single twice-reachable original source per channel, without quality ranking."""
import concurrent.futures
import datetime as dt
import json
import re
from pathlib import Path

from audit_overseas import audit_block, stream_url

ROOT = Path(__file__).resolve().parents[1]


def select_reliable_blocks(blocks):
    # The Ottera rendition remained black in UHF despite its advertised FHD quality.
    candidates = [block for block in blocks if "stream.ads.ottera.tv" not in stream_url(block)]
    results = {}

    def check(block):
        url, first = audit_block(block)
        if first.get("reachable"):
            _, second = audit_block(block)
            first["reachable"] = bool(second.get("reachable"))
            first["second_check"] = second
        return url, first

    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
        for url, result in executor.map(check, candidates):
            results[url] = result
    selected = []
    seen = set()
    for block in candidates:
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', block[0]))
        key = attrs.get("tvg-id") or attrs.get("tvg-name") or block[0].rsplit(",", 1)[-1]
        if key in seen or not results.get(stream_url(block), {}).get("reachable"):
            continue
        if "#EXT-X-KEY" in "\n".join(block):
            continue
        seen.add(key)
        clean = block.copy()
        clean[0] = re.sub(r'\s+(?:quality|video-range)="[^"]*"', "", clean[0])
        selected.append(clean)
    if not selected:
        raise RuntimeError("No sources passed both media-segment checks")
    (ROOT / "docs" / "reliability.json").write_text(json.dumps({
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": "original source order, one source per channel, two media-segment checks; no quality priority",
        "selected_urls": [stream_url(block) for block in selected],
        "streams": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Reliability checks: retained {len(selected)} channels from {len(blocks)} source entries", flush=True)
    return selected
