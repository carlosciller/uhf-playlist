# UHF Playlist

A UHF-friendly M3U8 playlist built from TDTChannels, with self-hosted logos and one reachable source per channel.

## Playlist URL

Spain/full catalogue:

```text
https://carlosciller.github.io/uhf-playlist/tv-uhf.m3u8
```

Worldwide/outside-Spain catalogue:

```text
https://carlosciller.github.io/uhf-playlist/tv-uhf-worldwide.m3u8
```

## EPG

```text
https://www.tdtchannels.com/epg/TV.xml.gz
```

## How it works

- Downloads the official TDTChannels playlist every day.
- Normalizes the M3U8 header for better UHF compatibility.
- Matches channels against the public `iptv-org` and `tv-logo/tv-logos` catalogues.
- Falls back to the TDTChannels image or the channel's official website icon when needed.
- Stores resolved logos in this repository and serves them through GitHub Pages.
- Removes broken logo references when no reliable replacement is available.
- Translates UHF group names into English while preserving official channel names.
- Keeps one original source per channel after two successful manifest and media-segment checks from the build network. Unreachable channels are omitted.
- Preserves adaptive HLS master playlists, allowing UHF to select the best rendition available for the connection and device.
- Preserves the original source order and does not rank sources by resolution or add quality labels.
- Excludes the Ottera sources that previously produced a black screen in UHF. Experimental UHD/HDR additions are disabled.
- Publishes a separate worldwide playlist containing only streams that delivered an HLS media segment during the latest audit from outside Spain. This avoids putting geo-blocked higher-resolution alternatives ahead of working international feeds.

## Overseas limitations

The worldwide playlist improves reliability; it cannot guarantee that every broadcaster permits every country forever. A stream is included only after both its manifest and a media segment have been fetched from the audited network in Thailand. Channels with no public feed available there are omitted instead of being shown as broken. The full Spain playlist remains unchanged.

The location snapshot is stored in `overseas_access.json`. Run `python scripts/audit_overseas.py --label Thailand` from the target network, then rebuild and validate, to refresh it.

## Reliability policy

Quality prioritization and curated UHD/HDR additions have been removed. The original adaptive stream chooses its own renditions; no maximum resolution is forced.

Successful HTTP media checks do not guarantee playback in UHF or access from every country. The current check evidence is published in `reliability.json`; it is refreshed during each build.

The TDTChannels EPG and cached channel logos are retained.

Cached logos are retained so they do not disappear when Facebook, X, or another provider changes its URLs. Special cases can be corrected in `logo_overrides.json`: use the channel's `tvg-id` or name as the key and a direct image URL as the value.

Source: [TDTChannels](https://www.tdtchannels.com/listas/).
