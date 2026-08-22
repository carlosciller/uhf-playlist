# UHF Playlist

A UHF-friendly M3U8 playlist built from TDTChannels.

## Playlist URL

```text
https://carlosciller.github.io/uhf-playlist/tv-uhf.m3u8
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
- Keeps every channel and alternative stream provided by the source.

Cached logos are retained so they do not disappear when Facebook, X, or another provider changes its URLs. Special cases can be corrected in `logo_overrides.json`: use the channel's `tvg-id` or name as the key and a direct image URL as the value.

Source: [TDTChannels](https://www.tdtchannels.com/listas/).
