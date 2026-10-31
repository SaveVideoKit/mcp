---
name: savevideokit
description: Download and inspect public videos/audio from 1000+ sites via the SaveVideoKit remote MCP server. Supports YouTube, TikTok, Twitter/X, Instagram, Facebook, Reddit, Vimeo, Dailymotion, Twitch, Bilibili, SoundCloud, Bluesky/bsky.app, Pornhub, and many more — NOT limited to a fixed platform list. Use when the user provides a public video/audio URL and wants to save it to local disk, inspect its metadata/formats, or list supported platforms. Triggers include "下载这个视频", "save this video", "get the mp4 for this link", "savevideokit 支持哪些平台", "この動画をダウンロード", "動画を保存", "mp4を取得", "savevideokit 対応サイト", "이 동영상 다운로드", "동영상 저장", "mp4 받기", "savevideokit 지원 사이트".
agent_created: true
---

# SaveVideoKit — Public Video / Audio Download & Inspect

## Download policy — mandatory

**Direct first. Relay only when a merge is physically required.** Apply this before every download, without exception.

```
inspect_video(url)
│
├─ direct_options has ≥1 entry  ──►  DIRECT: fetch direct_options[].download_url
│                                     (source CDN → local disk, no relay)
│
└─ direct_options is empty      ──►  RELAY: create_download → poll → save
                                      (no complete single file exists;
                                       the service must download + mux streams)
```

### 1. DIRECT — the default whenever it is offered

`direct_options[].download_url` answers `302` and redirects to the **original media file on the source CDN**. The bytes travel source → local disk:

- no server-side download, muxing, merge or storage;
- no job, no polling, no 30-minute retention race;
- the file is byte-for-byte what the source itself serves;
- the fastest path, and it costs the service nothing.

**Rule: if `direct_options` is non-empty, download from it and never create a job.** A relay here only re-downloads bytes that were already one request away.

### 2. RELAY — only for sources that genuinely need a merge

Use `create_download` **only when the source exposes no complete, directly fetchable file** — i.e. the media exists as separate adaptive streams (video-only + audio-only) and the service must download and mux them. Read the signals, do not guess:

| Signal | Meaning |
|---|---|
| `direct_download_available == false` | the backend found no browser-safe file |
| `direct_options == []` | nothing fetchable without a merge |
| every `formats[].direct_eligible == false` | no single format qualifies |
| `direct_reason: requires_headers` | CDN only serves the file with the page's Referer/UA (typical of TikTok) — a plain fetch cannot work |
| `direct_reason: not_mp4` | audio-only or an incompatible container; a playable mp4 must be produced |

These are exactly the "no real download address, a merge is needed" cases. Only then take the relay: `create_download` → poll → save (see the workflow below).

### 3. Anti-patterns — never do these

- Calling `create_download` before reading `direct_download_available` / `direct_options`.
- Relaying because "the user asked for an mp4" — a direct option **is already** a complete playable mp4.
- Relaying because the direct URL looks long or opaque — signed tokens are normal and expected.
- Polling, or announcing "processing", after taking a direct option.
- Falling back to relay on the first `403`/`404` of a direct link — that link merely expired; re-run `inspect_video` for a fresh one.
- Saving a direct link without `--ext` — those tokens carry no file suffix.
- Handing the URL back to the user instead of saving it — the MCP never writes to disk; the local save is always our job.

### 4. Report the path you used

- Direct → "downloaded directly from the source".
- Relay → "merged on the service (this source has no directly downloadable file)".

## Overview
This skill orchestrates the SaveVideoKit remote MCP server (`https://mcp.savevideokit.com/mcp`). The engine covers **1000+ sites**; the MCP exposes 4 tools and the skill encodes the correct order of operations: inspect → direct fetch or relay → local save → verify.

**Platform scope is open, not a fixed whitelist.** Do not reject a URL because it is missing from a short "known" list — pass any public video/audio URL and let the backend resolve the extractor. The only real gates are the hard limits below (public content, no watermark removal, no playlist/batch), never the site name.

## When to use
- The user supplies a public video/audio URL from **any** site and wants it saved locally.
- The user wants to inspect metadata/formats before downloading.
- The user asks which platforms are supported (`get_supported_sites`).
- Do NOT use for private, login-gated, age-restricted or region-locked content, or for watermark removal.

## Prerequisites
- The `savevideokit` MCP server must be enabled, configured in `~/.workbuddy/mcp.json` (type `http`, url `https://mcp.savevideokit.com/mcp`). If `inspect_video` / `create_download` / `get_download_status` / `get_supported_sites` are unavailable, ask the user to open 连接器 → 自定义连接器 → MCP 服务管理, locate `savevideokit`, click 信任, enable it, then start a fresh session.
- No API key or login is required.

## Tools (provided by the MCP server)
- `inspect_video({url})` → metadata + formats, plus the direct-download decision:
  - `direct_download_available` (bool) and `direct_options[]` — each `{option_id, download_url, format_id, ext, resolution, width, height, filesize}`. `download_url` is a signed link that redirects (302) to the original file.
  - `formats[].direct_eligible` + `formats[].direct_reason` (`requires_headers`, `not_mp4`, …), `format_count`, `qualities`, `webpage_url`.
- `create_download({url, format?, quality?})` → `job_id`. **Relay only** — never before the direct check.
- `get_download_status({job_id})` → `{status, progress, download_url}`; `download_url` only on `status == "success"`. Generated files are retained **30 minutes** (`file_retention_seconds = 1800`).
- `get_supported_sites({})` → service/engine version, `file_retention_seconds`, **32 verified** + **33 featured** + full **1735** site list.

## Workflow: Download a video
1. `inspect_video({url})`. Read `title`, `direct_download_available`, `direct_options`.
2. **Branch — this is the whole policy in one step:**
   - **`direct_options` non-empty → DIRECT.** Choose the best option: highest `height` within the user's quality cap (when every height is `0`, take the first), then fetch it at once:
     ```
     python3 <skill>/scripts/download_file.py "<direct_options[].download_url>" "<output_dir>" \
         --name "<title>" --ext "<option.ext>" --referer "<webpage_url>"
     ```
     The script follows the 302 to the source CDN. Do **not** call `create_download`, do **not** poll, do **not** say "processing".
   - **`direct_options` empty → RELAY.** `create_download({url, format: "mp4", quality: ""})`, parse `job_id` from `structuredContent` (fallback: regex `job_id` in the text), poll `get_download_status` every 5s until `success` / `failed` / `error` / `expired` (deadline 300s, same `job_id`), then save the returned `download_url` with the same script (`--name "<title>" --ext mp4`).
3. Verify the saved file exists and has size > 0; report the local path and which path was used.

## The downloader
```
python3 <skill>/scripts/download_file.py "<url>" "<output_dir>" --name "<title>" [--ext mp4] [--referer "<page>"]
```
Always pass the video title from `inspect_video` as `--name` so the file is saved under the video title (never a random id); when no title is available a deterministic name derived from the URL is used. `--ext` is required in practice for direct links (opaque tokens carry no suffix; the script also falls back to the response `Content-Type`). `--referer` helps origins that bind media to the page. The script writes a safe filename (≤120 chars), appends ` (1)` instead of overwriting, rejects empty bodies, and prints the final path. Replace `<skill>` with this skill's directory.

## Workflow: Inspect only
Call `inspect_video({url})` and present the result. State explicitly whether a direct download is available — that is the difference between "instant" and "queued + merged".

## Workflow: List platforms
Call `get_supported_sites({})` and summarize. Make clear the returned list is a **curated subset**; the engine supports far more, and any public video/audio URL can be attempted.

## Constraints & error handling
- Public content only; no private/age-restricted/region-locked; no watermark removal; no playlists or batch downloads.
- **No platform gate**: a URL missing from `get_supported_sites` should still be attempted.
- **Direct links are signed and expire.** `403` / `404` → re-run `inspect_video` for a fresh option; never silently downgrade to relay for that reason.
- **Job files last 30 minutes** (`file_retention_seconds = 1800`); an expired `download_url` needs a new `create_download`.
- Status `expired` → the job_id is invalid; create a new task rather than re-polling.
- HTTP/network errors → surface the message and suggest a retry.
- Empty `direct_options` is a normal source limitation, not an error — relay without commentary.

See `references/constraints.md` for the platform list, direct-download details and known limits.

## Resources
- `scripts/download_file.py` — stdlib-only downloader (redirects, extension detection, safe naming, progress).
- `references/constraints.md` — platforms, direct options, retention and limits.

## Keeping up to date

On first activation in a session, check for a newer release and auto-update this skill:

```
python3 <skill>/scripts/check_update.py --auto
```

This compares this skill's `VERSION` with the latest GitHub release of SaveVideoKit/mcp (cached 24h) and updates in place when a newer release exists, keeping a `<dir>.bak-<timestamp>` backup. Use `--check` to only report, `--force` to bypass the cache.
