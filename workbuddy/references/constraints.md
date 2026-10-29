# SaveVideoKit — Supported Platforms & Constraints

Backend engine (v2026.10.26) · covers **1735** sites (1599 working). The table below is a curated mainstream subset — the engine handles far more, so any public URL can be attempted.

## Mainstream supported platforms (33 featured · 8 verified)

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
| Bluesky | bsky.app, bluesky.app | |
| PornHub | pornhub.com (incl. playlist / user / paged-list sub-extractors) | |
| XVideos | xvideos.com | |
| XHamster | xhamster.com | |
| Twitch | twitch.tv | |
| SoundCloud | soundcloud.com | |
| Bilibili | bilibili.com | |
| Douyin (抖音) | douyin.com | |
| Weibo (微博) | weibo.com | |
| Snapchat | snapchat.com | |
| Pinterest | pinterest.com | |
| LinkedIn | linkedin.com | |
| Tumblr | tumblr.com | |
| VK | vk.com | |
| Odnoklassniki | ok.ru | |
| Rumble | rumble.com | |
| Niconico | nicovideo.jp | |
| Streamable | streamable.com | |
| Imgur | imgur.com | |
| 9GAG | 9gag.com | |
| BitChute | bitchute.com | |
| Rutube | rutube.ru | |
| Youku (优酷) | youku.com | |
| Kick | kick.com | |
| Likee | likee.video | |

> Not a whitelist. The engine supports 1000+ more (BBC, CNN, iQIYI, Hotstar, Bandcamp, …). If the URL is public, just try it.

## create_download arguments
- `url` (required): public video/audio URL.
- `format` (optional): `mp4` (default) or an extractor-style selector.
- `quality` (optional): e.g. `1080p` / `720p` / `480p`.

## Status values (get_download_status)
- `queued` / `pending` / `processing` → keep polling.
- `success` → `download_url` present; download immediately.
- `failed` / `error` / `expired` → stop; `expired` = job_id invalid, create a new task.

## Hard limits
- **Public only**: private/protected, region-locked, age-restricted, members-only, login-gated content unsupported.
- **No watermark removal.**
- **No playlists / batch** — one video per task.
- **Retention**: generated file lives ~2h on server; save locally promptly.

## Error handling
- MCP HTTP/network error → surface message, suggest retry.
- `job_id` missing → show raw result, do not poll.
- `expired` → create fresh download task.
