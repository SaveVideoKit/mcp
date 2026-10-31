---
name: savevideokit
description: Download and inspect public videos/audio from 1000+ sites via the SaveVideoKit remote MCP server. Supports YouTube, TikTok, Twitter/X, Instagram, Facebook, Reddit, Vimeo, Dailymotion, Twitch, Bilibili, SoundCloud, Bluesky/bsky.app, Pornhub, and many more — NOT limited to a fixed platform list. Use when the user provides a public video/audio URL and wants to save it to local disk, inspect its metadata/formats, or list supported platforms. Triggers include "下载这个视频", "save this video", "get the mp4 for this link", "savevideokit 支持哪些平台", "この動画をダウンロード", "動画を保存", "mp4を取得", "savevideokit 対応サイト", "이 동영상 다운로드", "동영상 저장", "mp4 받기", "savevideokit 지원 사이트".
agent_created: true
---

# SaveVideoKit — Public Video / Audio Download & Inspect

## Overview
This skill orchestrates the SaveVideoKit remote MCP server (`https://mcp.savevideokit.com/mcp`) to download or inspect public videos and audio. The underlying engine provides extractors for **1000+ sites**. The MCP exposes 4 tools; the skill encodes the correct workflow — inspect → **direct download when the source allows it** → otherwise create/poll → save → verify — plus the local-save step that the MCP itself never performs.

**Direct download comes first.** `inspect_video` reports whether the source exposes a browser-safe progressive file (`direct_download_available` / `direct_options`). When it does, the returned URL answers `302` and redirects straight to the **original media file on the source CDN**: nothing is queued, muxed, merged or stored server-side, so it completes faster and needs no retention window. Only when no direct option exists should you fall back to `create_download`.

**Platform scope is open, not a fixed whitelist.** Do not reject a URL just because it is not in a short "known" list — pass any public video/audio URL to `create_download` and let the backend resolve the correct extractor. The only real gates are the hard limits below (public content only, no watermark removal, no playlist/batch), not the site name.

## When to use
- The user supplies a public video/audio URL from **any** site (backend covers 1000+ sites; no fixed platform gate) and wants it saved locally.
- The user wants to inspect a video's metadata/formats before downloading.
- The user asks which platforms are supported (`get_supported_sites`).
- Do NOT use for private, login-gated, age-restricted, or region-locked content, or for watermark removal — these are unsupported and will fail.

## Prerequisites
- The `savevideokit` MCP server must be enabled in WorkBuddy, configured in `~/.workbuddy/mcp.json` (type `http`, url `https://mcp.savevideokit.com/mcp`). If the tools `inspect_video` / `create_download` / `get_download_status` / `get_supported_sites` are not available, ask the user to open 连接器 → 自定义连接器 → MCP 服务管理, locate `savevideokit`, click 信任, enable it, then start a fresh session.
- No API key or login is required.

## Tools (provided by the MCP server)
- `inspect_video({url})` → metadata + available formats. `structuredContent` also carries the direct-download decision:
  - `direct_download_available` (bool) and `direct_options[]` — each option is `{option_id, download_url, format_id, ext, resolution, width, height, filesize}`. `download_url` is a signed link that redirects (302) to the original file, so **no server-side download, merge or storage happens**.
  - every entry in `formats` carries `direct_eligible` + `direct_reason` (e.g. `requires_headers` — the CDN only answers requests sent with the page's Referer/UA, as on TikTok — or `not_mp4`), plus `format_count` and `qualities`.
- `create_download({url, format?, quality?})` → `job_id`; use it **only when no direct option is available**. Initial status queued/pending.
- `get_download_status({job_id})` → `{status, progress, download_url}`; `download_url` present only when `status == "success"`. Generated files are retained for **30 minutes** (`file_retention_seconds = 1800`).
- `get_supported_sites({})` → service/engine version, `file_retention_seconds`, **verified (32)** + **featured (33)** + full **all_sites (1735)**. The featured list in `references/constraints.md` is a curated mainstream subset — not a whitelist; the engine covers far more.

## Workflow: Download a video
1. Call `inspect_video({url})`. Read `title`, `direct_download_available` and `direct_options`.
2. **If a direct option exists, use it — skip `create_download` entirely.** Pick the best option: highest `height` within the user's quality cap (fall back to the first when all heights are 0), then save it immediately:
   ```
   python3 <skill>/scripts/download_file.py "<direct_options[].download_url>" "<output_dir>" \
       --name "<title>" --ext "<option.ext>" --referer "<webpage_url>"
   ```
   The script follows the 302 to the source CDN, so the bytes never touch the service. Do not report "processing" to the user — the file is fetched right away.
3. **Only when no direct option exists** (`direct_download_available == false` or `direct_options` empty): call `create_download({url, format: "mp4", quality: ""})`, parse `job_id` from `structuredContent` (fallback: regex `job_id` in the text), poll `get_download_status` every 5s until `success` / `failed` / `error` / `expired` (deadline 300s, same `job_id`), then save the returned `download_url` with the same script (`--name "<title>" --ext mp4`).
4. Verify the saved file exists and has size > 0; report the local path to the user.

Run the downloader:
```
python3 <skill>/scripts/download_file.py "<url>" "<output_dir>" --name "<title>" [--ext mp4] [--referer "<page>"]
```
Always pass the video title returned by `inspect_video` as `--name` so the file is saved under the video title (never a random id). If the title is unavailable, a deterministic name derived from the URL is used instead. `--ext` matters for direct links because their tokens carry no file suffix; `--referer` helps origins that only serve media to same-site requests. The script sanitizes the title into a safe filename (≤120 chars), avoids overwriting an existing file by appending ` (1)`, and prints the final path. Replace `<skill>` with this skill's directory.

## Workflow: Inspect only
Call `inspect_video({url})` and present the returned text / `structuredContent`. Mention whether a direct download is available — that is what the user gets instantly.

## Workflow: List platforms
Call `get_supported_sites({})` and summarize. Make clear the returned list is a **curated subset**; the engine supports far more (1000+ sites), and any public video/audio URL can be attempted.

## Constraints & error handling
- Public content only; no private/age-restricted/region-locked; no watermark removal; no playlists or batch downloads.
- **No platform gate**: a URL missing from `get_supported_sites` should still be attempted — the backend resolves the extractor automatically.
- **Direct links are signed and expire** (the token carries an expiry). If one returns `403` / `404`, call `inspect_video` again for a fresh option instead of retrying the old URL.
- **Job files are retained for 30 minutes** (`file_retention_seconds = 1800`) — save them promptly; an expired `download_url` needs a new `create_download` task.
- Status `expired` → the job_id is invalid; create a new download task rather than re-polling.
- HTTP/network errors from the MCP → surface the message and suggest a retry.
- If `direct_options` is empty, that is a normal source limitation, not an error — fall back to `create_download` without comment.

See `references/constraints.md` for the platform overview (open list), URL patterns, capabilities, and known limits.

## Resources
- `scripts/download_file.py` — robust stdlib-only downloader (streaming, safe filename, progress output).
- `references/constraints.md` — platform overview and limits.

## Keeping up to date

On first activation in a session, check for a newer release and auto-update this skill:

```
python3 <skill>/scripts/check_update.py --auto
```

This compares this skill's `VERSION` with the latest GitHub release of SaveVideoKit/mcp (cached 24h) and updates in place when a newer release exists, keeping a `<dir>.bak-<timestamp>` backup. Use `--check` to only report, `--force` to bypass the cache.
