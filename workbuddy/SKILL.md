---
name: savevideokit
description: Download and inspect public videos/audio from 1000+ sites through the SaveVideoKit remote MCP server. Always use the remote MCP for URL extraction and audio/video merging; never install or run local yt-dlp or ffmpeg. Use a plain local HTTP client only to save the final URL returned by the MCP. Supports YouTube, TikTok, Twitter/X, Instagram, Facebook, Reddit, Vimeo, Dailymotion, Twitch, Bilibili, SoundCloud, Bluesky/bsky.app, Pornhub, and many more — NOT limited to a fixed platform list. Triggers include "下载这个视频", "save this video", "get the mp4 for this link", "savevideokit 支持哪些平台", "この動画をダウンロード", "動画を保存", "mp4を取得", "savevideokit 対応サイト", "이 동영상 다운로드", "동영상 저장", "mp4 받기", "savevideokit 지원 사이트".
agent_created: true
---

# SaveVideoKit — Public Video / Audio Download & Inspect

## Execution boundary — non-negotiable

SaveVideoKit is the media resolver. Local programs are byte-transfer clients only.

- **Remote MCP only for resolving, selecting, downloading source streams, and muxing.** Start with `inspect_video`; when it reports no complete file, use `create_download` and let the cloud service merge the streams.
- **Never search for, clone, install, import, or execute local `yt-dlp`, `youtube-dl`, `ffmpeg`, or another site extractor/downloader.** This remains forbidden even if one is already installed or present elsewhere on disk.
- **Never pass the original webpage URL to `curl`, `wget`, PowerShell, or a Python HTTP downloader.** Those clients may receive only a `direct_options[].download_url` or a successful job's `download_url`.
- Local saving may use `scripts/download_file.py`, `curl -L`, `wget`, PowerShell `Invoke-WebRequest`, or equivalent plain HTTP transfer. These tools follow the final URL; they do not resolve the video page.
- If the SaveVideoKit MCP tools are unavailable, stop and explain how to enable the connector. Do not silently replace the MCP with a local downloader.

For the least model-dependent execution path, run the bundled zero-dependency orchestrator. It speaks MCP directly and enforces the branch in code:

```
python3 <skill>/scripts/save_video.py "<public-video-url>" --output "<output-dir>"
```

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
| `direct_reason: no_audio` | video-only adaptive stream; the cloud service must add audio |
| `direct_reason: no_video` | audio-only stream; it is not a complete video file |

These are exactly the "no real download address, a merge is needed" cases. Only then take the relay: `create_download` → poll → save (see the workflow below).

### 3. Anti-patterns — never do these

- Installing or running local `yt-dlp`, `youtube-dl`, `ffmpeg`, or another media extractor as a fallback.
- Giving the original YouTube/TikTok/etc. webpage URL to a local HTTP client. Only MCP-returned download URLs are fetchable media.
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
- The `savevideokit` MCP server must be enabled in the current client with type `http` and URL `https://mcp.savevideokit.com/mcp`. Use that client's corresponding config from this repository. If `inspect_video` / `create_download` / `get_download_status` / `get_supported_sites` are unavailable, ask the user to enable/trust the `savevideokit` connector in the current client and start a fresh session. Never substitute a local media downloader.
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

Example: if a YouTube inspection returns `direct_options: []` and MP4 formats have `direct_reason: "no_audio"`, do not attempt local merging. Call `create_download` immediately; the cloud service downloads and muxes the separate streams.

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
- `scripts/save_video.py` — preferred zero-dependency end-to-end runner (MCP inspect → direct or cloud queue → local save); it never uses local media extraction tools.
- `scripts/download_file.py` — stdlib-only downloader (redirects, extension detection, safe naming, progress).
- `references/constraints.md` — platforms, direct options, retention and limits.

## Keeping up to date

On first activation in a session, check for a newer release and auto-update this skill:

```
python3 <skill>/scripts/check_update.py --auto
```

This compares this skill's `VERSION` with the latest GitHub release of SaveVideoKit/mcp (cached 24h) and updates in place when a newer release exists, keeping a `<dir>.bak-<timestamp>` backup. Use `--check` to only report, `--force` to bypass the cache.
