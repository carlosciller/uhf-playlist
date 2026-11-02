"""Preserve the source catalogue without applying build-network geo restrictions."""
import datetime as dt
import json
import re
from pathlib import Path

from audit_overseas import stream_url

ROOT = Path(__file__).resolve().parents[1]


def select_reliable_blocks(blocks):
    # The Ottera rendition remained black in UHF despite its advertised FHD quality.
    candidates = [block for block in blocks if "stream.ads.ottera.tv" not in stream_url(block)]
    selected = []
    seen = set()
    for block in candidates:
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', block[0]))
        key = attrs.get("tvg-id") or attrs.get("tvg-name") or block[0].rsplit(",", 1)[-1]
        if key in seen:
            continue
        seen.add(key)
        clean = block.copy()
        clean[0] = re.sub(r'\s+(?:quality|video-range)="[^"]*"', "", clean[0])
        selected.append(clean)
    if not selected:
        raise RuntimeError("Source catalogue contains no channels")
    (ROOT / "docs" / "reliability.json").write_text(json.dumps({
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": "original source order, one source per channel; no quality priority or build-network reachability filter",
        "network_tested": False,
        "selected_urls": [stream_url(block) for block in selected],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Source catalogue: retained {len(selected)} channels from {len(blocks)} entries", flush=True)
    return selected
