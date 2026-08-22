#!/usr/bin/env python3
"""Build a UHF-friendly TDTChannels playlist with self-hosted channel logos."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


SOURCE_URL = os.environ.get(
    "SOURCE_URL", "https://www.tdtchannels.com/lists/tv.m3u8"
)
EPG_URL = os.environ.get(
    "EPG_URL", "https://www.tdtchannels.com/epg/TV.xml.gz"
)
IPTV_ORG_CHANNELS_URL = os.environ.get(
    "IPTV_ORG_CHANNELS_URL", "https://iptv-org.github.io/api/channels.json"
)
IPTV_ORG_LOGOS_URL = os.environ.get(
    "IPTV_ORG_LOGOS_URL", "https://iptv-org.github.io/api/logos.json"
)
TDT_JSON_URL = os.environ.get(
    "TDT_JSON_URL", "https://www.tdtchannels.com/lists/tv.json"
)
PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL", "https://carlosciller.github.io/uhf-playlist"
).rstrip("/")

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
LOGOS_DIR = DOCS_DIR / "logos"
OUTPUT_PATH = DOCS_DIR / "tv-uhf.m3u8"
STATUS_PATH = DOCS_DIR / "status.json"
OVERRIDES_PATH = ROOT / "logo_overrides.json"
TV_LOGOS_DIR = Path(os.environ["TV_LOGOS_DIR"]) if os.environ.get("TV_LOGOS_DIR") else None

ATTRIBUTE_RE = re.compile(r'([\w-]+)="([^"]*)"')
EXTINF_NAME_RE = re.compile(r",(.*)$")
GROUP_TITLE_RE = re.compile(r'group-title="([^"]*)"')
SAFE_EXTENSIONS = {"png", "jpg", "webp", "gif", "svg"}
GROUP_TRANSLATIONS = {
    "Andalucía": "Andalusia",
    "C. Foral de Navarra": "Navarre",
    "C. Valenciana": "Valencian Community",
    "C. de Madrid": "Community of Madrid",
    "Canarias": "Canary Islands",
    "Castilla y León": "Castile and León",
    "Cataluña": "Catalonia",
    "Deportivos": "Sports",
    "Deportivos Int.": "International Sports",
    "Eventuales": "Event Channels",
    "Generalistas": "General",
    "Illes Balears": "Balearic Islands",
    "Infantiles": "Kids",
    "Informativos": "News",
    "Int. América": "International · Americas",
    "Int. Asia": "International · Asia",
    "Int. Europa": "International · Europe",
    "Int. Otros": "International · Other",
    "Int. África": "International · Africa",
    "Musicales": "Music",
    "P. de Asturias": "Asturias",
    "País Vasco": "Basque Country",
    "R. de Murcia": "Region of Murcia",
    "Religiosos": "Religious",
}
STYLE_TOKENS = {
    "4k",
    "black",
    "dark",
    "hd",
    "horizontal",
    "hz",
    "icon",
    "light",
    "sd",
    "uhd",
    "white",
}
COUNTRY_CODES = {
    "ae", "al", "ar", "at", "au", "ba", "be", "bg", "bo", "br", "ca",
    "ch", "cl", "cn", "co", "cr", "cz", "de", "dk", "do", "ec", "ee",
    "eg", "es", "fi", "fr", "gb", "gr", "hk", "hr", "hu", "id", "ie",
    "il", "in", "is", "it", "jp", "kr", "lt", "lu", "lv", "ma", "me",
    "mk", "mt", "mx", "my", "ng", "ni", "nl", "no", "nz", "pa", "pe",
    "ph", "pk", "pl", "pr", "pt", "py", "ro", "rs", "ru", "sa", "se",
    "sg", "si", "sk", "sv", "th", "tr", "tw", "ua", "uk", "us", "uy",
    "ve", "vn", "za",
}
COUNTRY_HINTS = {
    "alemania": "DE",
    "argentina": "AR",
    "australia": "AU",
    "austria": "AT",
    "bielorrusia": "BY",
    "brasil": "BR",
    "canada": "CA",
    "chequia": "CZ",
    "chile": "CL",
    "china": "CN",
    "colombia": "CO",
    "coreadelsur": "KR",
    "costarica": "CR",
    "croacia": "HR",
    "ecuador": "EC",
    "emiratosarabes": "AE",
    "espana": "ES",
    "estadosunidos": "US",
    "francia": "FR",
    "india": "IN",
    "italia": "IT",
    "japon": "JP",
    "mexico": "MX",
    "peru": "PE",
    "polonia": "PL",
    "reinounido": "GB",
    "rumania": "RO",
    "turquia": "TR",
    "ucrania": "UA",
    "usa": "US",
    "venezuela": "VE",
}
ALIASES = {
    "la1": "tve1",
    "la1can": "tve1",
    "la1cat": "tve1",
    "la2": "tve2",
    "la2can": "tve2",
    "24horas": "24h",
    "canal24horas": "24h",
    "tdp": "tdp",
    "teledeporte": "tdp",
    "bemad": "bemadtv",
    "apunt": "apunt",
    "extremaduratv": "canalextremadura",
    "canarias": "tvcanaria",
}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def request_bytes(url: str, *, attempts: int = 3, timeout: int = 25) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(6_000_001)
                if len(data) > 6_000_000:
                    raise ValueError("image exceeds 6 MB")
                return data, response.headers.get_content_type().lower()
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else "download failed")


def download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
    return raw.decode("utf-8-sig")


def download_json(url: str) -> object:
    return json.loads(download_text(url))


def attributes(line: str) -> dict[str, str]:
    return dict(ATTRIBUTE_RE.findall(line))


def channel_name(line: str) -> str:
    match = EXTINF_NAME_RE.search(line)
    return match.group(1).strip() if match else "channel"


def stable_key(line: str) -> str:
    attrs = attributes(line)
    return attrs.get("tvg-id") or attrs.get("tvg-name") or channel_name(line)


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-") or "channel"
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:70]}-{digest}"


def normalized_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", ascii_value)


def reference_stem_variants(path: Path) -> set[str]:
    tokens = path.stem.lower().split("-")
    if tokens and tokens[-1] in COUNTRY_CODES:
        tokens.pop()
    variants = {normalized_name("-".join(tokens))}
    while tokens and tokens[-1] in STYLE_TOKENS:
        tokens.pop()
        variants.add(normalized_name("-".join(tokens)))
    return {variant for variant in variants if variant}


def build_reference_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    if not TV_LOGOS_DIR or not TV_LOGOS_DIR.exists():
        return index
    for path in TV_LOGOS_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lstrip(".").lower() not in SAFE_EXTENSIONS:
            continue
        for variant in reference_stem_variants(path):
            index.setdefault(variant, []).append(path)
    return index


def channel_variants(line: str) -> set[str]:
    attrs = attributes(line)
    key = stable_key(line)
    values = {
        key.removesuffix(".TV"),
        attrs.get("tvg-name", ""),
        channel_name(line),
    }
    variants: set[str] = set()
    for value in values:
        cleaned = re.sub(r"\b(GEO|HD|SD|UHD|4K)\b", " ", value, flags=re.IGNORECASE)
        cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
        normalized = normalized_name(cleaned)
        if normalized:
            variants.add(normalized)
            if normalized.endswith("tv") and len(normalized) > 4:
                variants.add(normalized[:-2])
    variants.update(ALIASES[value] for value in tuple(variants) if value in ALIASES)
    return variants


def iptv_logo_rank(logo: dict[str, object]) -> tuple[object, ...]:
    tags = {str(tag).lower() for tag in logo.get("tags", []) if tag}
    image_format = str(logo.get("format", "")).upper()
    format_rank = {"PNG": 0, "WEBP": 1, "JPEG": 2, "JPG": 2, "SVG": 3}
    return (
        0 if logo.get("in_use") else 1,
        0 if logo.get("feed") is None else 1,
        1 if tags.intersection({"black", "dark", "white"}) else 0,
        format_rank.get(image_format, 4),
        -int(logo.get("width") or 0),
    )


def build_iptv_logo_index() -> dict[str, list[dict[str, object]]]:
    channels = download_json(IPTV_ORG_CHANNELS_URL)
    logos = download_json(IPTV_ORG_LOGOS_URL)
    if not isinstance(channels, list) or not isinstance(logos, list):
        raise ValueError("unexpected iptv-org API response")

    logos_by_channel: dict[str, list[dict[str, object]]] = {}
    for logo in logos:
        if not isinstance(logo, dict):
            continue
        channel_id = str(logo.get("channel") or "")
        url = str(logo.get("url") or "")
        if channel_id and url.startswith(("https://", "http://")):
            logos_by_channel.setdefault(channel_id, []).append(logo)

    index: dict[str, list[dict[str, object]]] = {}
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        channel_id = str(channel.get("id") or "")
        channel_logos = logos_by_channel.get(channel_id)
        if not channel_id or not channel_logos:
            continue
        ranked_urls: list[str] = []
        for logo in sorted(channel_logos, key=iptv_logo_rank):
            url = str(logo.get("url") or "")
            if url and url not in ranked_urls:
                ranked_urls.append(url)
            if len(ranked_urls) == 4:
                break
        names = {
            channel_id.rsplit(".", 1)[0],
            str(channel.get("name") or ""),
            *(str(name) for name in channel.get("alt_names", []) if name),
        }
        normalized_names = {normalized_name(name) for name in names if name}
        normalized_names.discard("")
        entry: dict[str, object] = {
            "id": channel_id,
            "country": str(channel.get("country") or "").upper(),
            "names": normalized_names,
            "urls": ranked_urls,
        }
        for name in normalized_names:
            index.setdefault(name, []).append(entry)
    return index


def build_website_index() -> dict[str, str]:
    data = download_json(TDT_JSON_URL)
    if not isinstance(data, dict) or not isinstance(data.get("countries"), list):
        raise ValueError("unexpected TDTChannels JSON response")
    index: dict[str, str] = {}
    for country in data["countries"]:
        if not isinstance(country, dict):
            continue
        for ambit in country.get("ambits", []):
            if not isinstance(ambit, dict):
                continue
            for channel in ambit.get("channels", []):
                if not isinstance(channel, dict):
                    continue
                website = str(channel.get("web") or "")
                if not website.startswith(("https://", "http://")):
                    continue
                hostname = (urllib.parse.urlsplit(website).hostname or "").lower()
                if hostname.removeprefix("www.") in {
                    "facebook.com",
                    "instagram.com",
                    "tiktok.com",
                    "x.com",
                    "youtube.com",
                }:
                    continue
                epg_id = str(channel.get("epg_id") or "")
                name = str(channel.get("name") or "")
                if epg_id:
                    index.setdefault(epg_id, website)
                    index.setdefault(normalized_name(epg_id.removesuffix(".TV")), website)
                if name:
                    index.setdefault(normalized_name(name), website)
    return index


def find_website(line: str, index: dict[str, str]) -> str | None:
    key = stable_key(line)
    if key in index:
        return index[key]
    for variant in sorted(channel_variants(line), key=len, reverse=True):
        if variant in index:
            return index[variant]
    return None


def favicon_url(website: str) -> str:
    encoded = urllib.parse.quote(website, safe="")
    return f"https://www.google.com/s2/favicons?sz=256&domain_url={encoded}"


def country_hint(line: str) -> str | None:
    value = normalized_name(line)
    matches = [code for name, code in COUNTRY_HINTS.items() if name in value]
    return matches[0] if len(set(matches)) == 1 else None


def find_iptv_logo_urls(
    line: str, index: dict[str, list[dict[str, object]]]
) -> list[str]:
    variants = channel_variants(line)
    hint = country_hint(line)
    candidates: dict[str, dict[str, object]] = {}
    for variant in variants:
        for candidate in index.get(variant, []):
            candidates[str(candidate["id"])] = candidate
    if not candidates:
        return []

    def candidate_score(candidate: dict[str, object]) -> tuple[int, int, str]:
        names = candidate["names"]
        exact_matches = len(variants.intersection(names)) if isinstance(names, set) else 0
        country = str(candidate["country"])
        country_score = 30 if hint and country == hint else -30 if hint else 3 if country == "ES" else 0
        return exact_matches * 100 + country_score, len(str(candidate["id"])), str(candidate["id"])

    ranked = sorted(candidates.values(), key=candidate_score, reverse=True)
    if len(ranked) > 1:
        first_score = candidate_score(ranked[0])[0]
        second_score = candidate_score(ranked[1])[0]
        if first_score == second_score:
            return []
    urls = ranked[0].get("urls", [])
    return [str(url) for url in urls] if isinstance(urls, list) else []


def prefer_reference(paths: list[Path]) -> Path:
    return sorted(
        paths,
        key=lambda path: (
            0 if "countries/spain/" in path.as_posix() else 1,
            1 if any(token in path.stem.split("-") for token in STYLE_TOKENS) else 0,
            len(path.name),
            path.as_posix(),
        ),
    )[0]


def find_reference_logo(line: str, index: dict[str, list[Path]]) -> Path | None:
    variants = channel_variants(line)
    for variant in sorted(variants, key=len, reverse=True):
        if variant in index:
            return prefer_reference(index[variant])

    # Only accept a very close and unambiguous fuzzy match.
    best_key = ""
    best_score = 0.0
    second_score = 0.0
    for variant in variants:
        if len(variant) < 5:
            continue
        for reference_key in index:
            if abs(len(reference_key) - len(variant)) > max(4, len(variant) // 3):
                continue
            score = difflib.SequenceMatcher(None, variant, reference_key).ratio()
            if score > best_score:
                second_score = best_score
                best_score = score
                best_key = reference_key
            elif score > second_score:
                second_score = score
    if best_key and best_score >= 0.94 and best_score - second_score >= 0.025:
        return prefer_reference(index[best_key])
    return None


def detect_extension(data: bytes, content_type: str) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    stripped = data.lstrip()[:256].lower()
    if stripped.startswith(b"<svg") or b"<svg" in stripped:
        return "svg"
    content_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/svg+xml": "svg",
    }
    return content_map.get(content_type)


def existing_logo(stem: str) -> Path | None:
    for path in LOGOS_DIR.glob(f"{stem}.*"):
        if path.suffix.lstrip(".").lower() in SAFE_EXTENSIONS and path.stat().st_size > 100:
            return path
    return None


def cache_download(stem: str, url: str) -> Path:
    data, content_type = request_bytes(url, attempts=2)
    extension = detect_extension(data, content_type)
    if extension not in SAFE_EXTENSIONS:
        raise ValueError(f"unsupported response type: {content_type}")
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    destination = LOGOS_DIR / f"{stem}.{extension}"
    with tempfile.NamedTemporaryFile(dir=LOGOS_DIR, delete=False) as temporary:
        temporary.write(data)
        temp_path = Path(temporary.name)
    temp_path.replace(destination)
    return destination


def cache_logo(
    key: str,
    candidates: list[tuple[str, str]],
    reference: Path | None,
) -> tuple[str, Path | None, str | None, str]:
    stem = slug(key)
    cached = existing_logo(stem)
    if cached:
        return key, cached, None, "cache"
    errors: list[str] = []
    preferred = [candidate for candidate in candidates if candidate[1] not in {"source", "favicon"}]
    fallbacks = [candidate for candidate in candidates if candidate[1] in {"source", "favicon"}]
    for url, source_name in preferred:
        if not url.startswith(("https://", "http://")):
            continue
        try:
            return key, cache_download(stem, url), None, source_name
        except Exception as error:
            errors.append(f"{source_name}: {error}")
    if reference:
        extension = reference.suffix.lstrip(".").lower()
        destination = LOGOS_DIR / f"{stem}.{extension}"
        LOGOS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(reference, destination)
        return key, destination, None, "tv-logos"
    for url, source_name in fallbacks:
        if not url.startswith(("https://", "http://")):
            continue
        hostname = (urllib.parse.urlsplit(url).hostname or "").lower()
        if source_name == "source" and hostname == "graph.facebook.com":
            continue
        try:
            return key, cache_download(stem, url), None, source_name
        except Exception as error:
            errors.append(f"{source_name}: {error}")
    return key, None, "; ".join(errors) or "no usable logo source", "failed"


def replace_logo(line: str, url: str) -> str:
    if re.search(r'tvg-logo="[^"]*"', line):
        return re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{url}"', line, count=1)
    comma = line.rfind(",")
    if comma == -1:
        return line
    return f'{line[:comma]} tvg-logo="{url}"{line[comma:]}'


def remove_logo(line: str) -> str:
    return re.sub(r'\s+tvg-logo="[^"]*"', "", line, count=1)


def translate_group_title(line: str) -> str:
    match = GROUP_TITLE_RE.search(line)
    if not match:
        return line
    translated = GROUP_TRANSLATIONS.get(match.group(1), match.group(1))
    return f"{line[:match.start(1)]}{translated}{line[match.end(1):]}"


def load_overrides() -> dict[str, str]:
    if not OVERRIDES_PATH.exists():
        return {}
    value = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("logo_overrides.json must contain an object")
    return {str(key): str(url) for key, url in value.items() if url}


def build() -> dict[str, object]:
    source = download_text(SOURCE_URL)
    source_lines = source.splitlines()
    extinf_lines = [line for line in source_lines if line.startswith("#EXTINF")]
    if not extinf_lines:
        raise RuntimeError("the source contains no channels")

    overrides = load_overrides()
    reference_index = build_reference_index()
    catalog_error: str | None = None
    try:
        iptv_logo_index = build_iptv_logo_index()
    except Exception as error:
        iptv_logo_index = {}
        catalog_error = str(error)
    website_catalog_error: str | None = None
    try:
        website_index = build_website_index()
    except Exception as error:
        website_index = {}
        website_catalog_error = str(error)
    logo_sources: dict[str, str] = {}
    logo_lines: dict[str, str] = {}
    for line in extinf_lines:
        attrs = attributes(line)
        key = stable_key(line)
        preferred = overrides.get(key) or overrides.get(channel_name(line))
        logo_sources.setdefault(key, preferred or attrs.get("tvg-logo", ""))
        logo_lines.setdefault(key, line)

    cached_logos: dict[str, Path] = {}
    failures: dict[str, str] = {}
    source_breakdown = {
        "cache": 0,
        "override": 0,
        "iptv-org": 0,
        "tv-logos": 0,
        "source": 0,
        "favicon": 0,
        "failed": 0,
    }
    workers = min(12, max(1, len(logo_sources)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for key, source_url in logo_sources.items():
            line = logo_lines[key]
            candidates: list[tuple[str, str]] = []
            override_url = overrides.get(key) or overrides.get(channel_name(line))
            if override_url:
                candidates.append((override_url, "override"))
            candidates.extend(
                (url, "iptv-org") for url in find_iptv_logo_urls(line, iptv_logo_index)
            )
            if source_url and source_url != override_url:
                candidates.append((source_url, "source"))
            website = find_website(line, website_index)
            if website:
                candidates.append((favicon_url(website), "favicon"))
            futures.append(
                executor.submit(
                    cache_logo,
                    key,
                    candidates,
                    find_reference_logo(line, reference_index),
                )
            )
        for future in concurrent.futures.as_completed(futures):
            key, path, error, source_name = future.result()
            source_breakdown[source_name] += 1
            if path:
                cached_logos[key] = path
            elif error:
                failures[key] = error

    output_lines = [f'#EXTM3U url-tvg="{EPG_URL}"']
    for line in source_lines:
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            key = stable_key(line)
            cached = cached_logos.get(key)
            if cached:
                public_url = (
                    f"{PUBLIC_BASE_URL}/logos/"
                    f"{urllib.parse.quote(cached.name, safe='.-_')}"
                )
                line = replace_logo(line, public_url)
            else:
                line = remove_logo(line)
            line = translate_group_title(line)
        output_lines.append(line)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    status: dict[str, object] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": SOURCE_URL,
        "epg": EPG_URL,
        "channels": len(extinf_lines),
        "unique_channels": len(logo_sources),
        "self_hosted_logos": len(cached_logos),
        "uncached_logos": len(failures),
        "logo_coverage_percent": round(len(cached_logos) * 100 / len(logo_sources), 1),
        "uncached_channel_ids": sorted(failures),
        "logo_source_breakdown": source_breakdown,
        "iptv_org_catalog_error": catalog_error,
        "tdt_website_catalog_error": website_catalog_error,
    }
    STATUS_PATH.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return status


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
