# SaveVideoKit — Supported Platforms & Constraints

MCP service **v0.1.7** · engine **2026.10.26** (built-in) · covers **1735** sites (1599 working) · **32 verified** / **33 featured** · generated-file retention **1800s (30 min)**.

The table below is a curated mainstream subset — the engine handles far more, so any public URL can be attempted.

## Mainstream supported platforms (33 featured · 32 verified)

| Platform | Domains | Verified |
|---|---|---|
| YouTube | youtube.com, youtu.be | ✅ |
| TikTok | tiktok.com | ✅ |
| Instagram | instagram.com | ✅ |
| Facebook | facebook.com | ✅ |
| Twitter / X | x.com, twitter.com | ✅ |
| Reddit | reddit.com | ✅ |
| Vimeo | vimeo.com | ✅ |
| Dailymotion | dailymotion.com | ✅ |
| Bluesky | bsky.app, bluesky.app | ✅ |
| PornHub | pornhub.com (incl. playlist / user / paged-list sub-extractors) | ✅ |
| XVideos | xvideos.com | ✅ |
| XHamster | xhamster.com | ✅ |
| Twitch | twitch.tv | ✅ |
| SoundCloud | soundcloud.com | |
| Bilibili | bilibili.com | ✅ |
| Douyin (抖音) | douyin.com | ✅ |
| Weibo (微博) | weibo.com | ✅ |
| Snapchat | snapchat.com | ✅ |
| Pinterest | pinterest.com | ✅ |
| LinkedIn | linkedin.com | ✅ |
| Tumblr | tumblr.com | ✅ |
| VK | vk.com | ✅ |
| Odnoklassniki | ok.ru | ✅ |
| Rumble | rumble.com | ✅ |
| Niconico | nicovideo.jp | ✅ |
| Streamable | streamable.com | ✅ |
| Imgur | imgur.com | ✅ |
| 9GAG | 9gag.com | ✅ |
| BitChute | bitchute.com | ✅ |
| Rutube | rutube.ru | ✅ |
| Youku (优酷) | youku.com | ✅ |
| Kick | kick.com | ✅ |
| Likee | likee.video | ✅ |

> Not a whitelist. The engine supports 1000+ more (BBC, CNN, iQIYI, Hotstar, Bandcamp, …). If the URL is public, just try it.

## Download policy: direct first, relay only when a merge is required

### Execution boundary

All webpage resolution, stream selection, source-stream downloading, and muxing belongs to the remote SaveVideoKit MCP service. Never install or invoke local `yt-dlp`, `youtube-dl`, `ffmpeg`, or another media extractor as a fallback. Local `curl -L`, `wget`, PowerShell `Invoke-WebRequest`, or Python HTTP code may only transfer a final URL returned by `inspect_video` or `get_download_status`; never pass them the original video webpage URL.

If the MCP tools are unavailable, stop and ask the user to enable the connector. The bundled `scripts/save_video.py` is the zero-dependency end-to-end fallback because it connects to the same remote MCP endpoint and enforces this policy in code.

`inspect_video` decides per URL whether the source exposes a browser-safe progressive file and returns:

- `direct_download_available` — boolean.
- `direct_options[]` — `{option_id, download_url, format_id, ext, resolution, width, height, filesize}`.
- `formats[].direct_eligible` / `direct_reason` — why a given format is or is not directly downloadable.

### Direct (default)

`direct_options[].download_url` answers `302` and redirects to the **original media URL on the source CDN**. Nothing is queued, muxed, merged or stored by the service, so:

- the bytes are exactly what the source serves — no re-encode, no mux;
- there is no job to poll and no retention window to race against, only the signed-link expiry;
- it is the fastest path and it does not consume the service's download capacity.

Save it with `--name "<title>" --ext "<option.ext>" --referer "<webpage_url>"`. Direct links carry no file suffix, so `--ext` (or the response `Content-Type`) determines the extension.

### Relay (only when the source has no complete single file)

Call `create_download` **only** when a merge is physically unavoidable — the media exists as separate adaptive streams and the service must download and mux them. Triggering signals:

| Signal | Meaning |
|---|---|
| `direct_download_available == false` | no browser-safe file was found |
| `direct_options == []` | nothing is fetchable without a merge |
| all `formats[].direct_eligible == false` | no single format qualifies |
| `direct_reason: requires_headers` | the CDN only answers requests carrying the page's Referer/UA (e.g. TikTok) |
| `direct_reason: not_mp4` | audio-only or an incompatible container; an mp4 must be produced |
| `direct_reason: no_audio` | video-only adaptive stream; audio must be merged by the cloud service |
| `direct_reason: no_video` | audio-only stream; it is not a complete video file |

Everything else is a direct download. Relaying while a direct option exists wastes a queue slot and moves bytes the source already serves.

## create_download arguments
- `url` (required): public video/audio URL.
- `format` (optional): `mp4` (default) or an extractor-style selector.
- `quality` (optional): e.g. `1080p` / `720p` / `480p`. Ignored when a custom selector is passed.

## Status values (get_download_status)
- `queued` / `pending` / `running` / `processing` → keep polling.
- `success` → `download_url` present; download immediately.
- `failed` / `error` / `expired` → stop; `expired` = job_id invalid, create a new task.

## Hard limits
- **Public only**: private/protected, region-locked, age-restricted, members-only, login-gated content unsupported.
- **No watermark removal.**
- **No playlists / batch** — one video per task.
- **Retention**: a generated job file lives 30 minutes (`file_retention_seconds = 1800`); direct options are not stored at all.

## Error handling
- MCP HTTP/network error → surface message, suggest retry.
- `job_id` missing → show raw result, do not poll.
- `expired` → create fresh download task.
- Direct link `403` / `404` → the signed option expired; re-run `inspect_video` for a fresh one.
