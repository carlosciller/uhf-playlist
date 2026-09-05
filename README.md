# UHF Playlist

A UHF-friendly M3U8 playlist built from TDTChannels, with self-hosted logos and a small set of manually verified public UHD/HDR channels.

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
- Preserves adaptive HLS master playlists, allowing UHF to select the best rendition available for the connection and device.
- Adds only public UHD/HDR streams whose advertised and decoded video properties have been checked.

## UHD and HDR policy

The `UHD / HDR` group contains manually curated additions from `extra_channels.json`. Quality labels describe the actual video, not the channel name or marketing claim.

- `IRIB UHD · 4K SDR` currently offers a 3840×2160 rendition in its adaptive HLS master.
- No public live feed currently included has been verified as genuine HLG, PQ/HDR10, or Dolby Vision, so none is labelled HDR.
- Streams that are encrypted, subscription-only, restreamed without a trustworthy origin, or merely named “4K” while delivering a lower resolution are not added.

The TDTChannels EPG covers channels from its own catalogue. Manually curated UHD/HDR additions may appear without programme information.

Cached logos are retained so they do not disappear when Facebook, X, or another provider changes its URLs. Special cases can be corrected in `logo_overrides.json`: use the channel's `tvg-id` or name as the key and a direct image URL as the value.

Source: [TDTChannels](https://www.tdtchannels.com/listas/).
