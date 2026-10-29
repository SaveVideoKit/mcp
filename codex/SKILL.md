---
name: savevideokit
description: Download and inspect public videos/audio from 1000+ sites via the SaveVideoKit remote MCP server. Supports YouTube, TikTok, Twitter/X, Instagram, Facebook, Reddit, Vimeo, Dailymotion, Twitch, Bilibili, SoundCloud, Bluesky/bsky.app, Pornhub, and many more — NOT limited to a fixed platform list. Use when the user provides a public video/audio URL and wants to save it to local disk, inspect its metadata/formats, or list supported platforms. Triggers include "下载这个视频", "save this video", "get the mp4 for this link", "savevideokit 支持哪些平台", "この動画をダウンロード", "動画を保存", "mp4を取得", "savevideokit 対応サイト", "이 동영상 다운로드", "동영상 저장", "mp4 받기", "savevideokit 지원 사이트".
agent_created: true
---

# SaveVideoKit — Public Video / Audio Download & Inspect

## Overview
This skill orchestrates the SaveVideoKit remote MCP server (`https://mcp.savevideokit.com/mcp`) to download or inspect public videos and audio. The underlying engine provides extractors for **1000+ sites**. The MCP exposes 4 tools; the skill encodes the correct multi-step workflow (inspect → create → poll → save → verify) plus the local-save step that the MCP itself does NOT perform.

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
- `inspect_video({url})` → metadata + available formats (text plus `structuredContent` with `title`).
- `create_download({url, format?, quality?})` → `job_id`; initial status queued/pending.
- `get_download_status({job_id})` → `{status, progress, download_url}`; `download_url` present only when `status == "success"`.
- `get_supported_sites({})` → returns **verified (8)** + **featured (33)** + full **all_sites (1735)**. The featured list in `references/constraints.md` is a curated mainstream subset — not a whitelist; the engine covers far more.

## Workflow: Download a video
1. (Optional) Call `inspect_video({url})` to show the user title and available formats.
2. Call `create_download({url, format: "mp4", quality: ""})`. Parse `job_id` from `structuredContent` (fallback: regex `job_id` in the text result). If missing, surface the raw result and stop.
3. Poll `get_download_status({job_id})` every 5s until `status == "success"`, or until `failed` / `error` / `expired` (stop and report the error). Default deadline 300s; keep reusing the same `job_id`.
4. On success, extract `download_url`. **The MCP does NOT save the file** — call `scripts/download_file.py` to fetch the bytes to local disk immediately, because the remote file is retained for only ~2 hours.
5. Verify the saved file exists and has size > 0; report the local path to the user.

Run the downloader:
```
python3 <skill>/scripts/download_file.py "<download_url>" "<output_dir>" --name "<title>"
```
It derives a safe filename (sanitized, ≤120 chars, correct extension) and prints the final path. Replace `<skill>` with this skill's directory.

## Workflow: Inspect only
Call `inspect_video({url})` and present the returned text / `structuredContent`.

## Workflow: List platforms
Call `get_supported_sites({})` and summarize. Make clear the returned list is a **curated subset**; the engine supports far more (1000+ sites), and any public video/audio URL can be attempted.

## Constraints & error handling
- Public content only; no private/age-restricted/region-locked; no watermark removal; no playlists or batch downloads.
- **No platform gate**: a URL missing from `get_supported_sites` should still be attempted — the backend resolves the extractor automatically.
- Remote file retained ~7200s (2h) — download promptly; if a `download_url` expires, create a fresh `create_download` task.
- Status `expired` → the job_id is invalid; create a new download task rather than re-polling.
- HTTP/network errors from the MCP → surface the message and suggest a retry.

See `references/constraints.md` for the platform overview (open list), URL patterns, capabilities, and known limits.

## Resources
- `scripts/download_file.py` — robust stdlib-only downloader (streaming, safe filename, progress output).
- `references/constraints.md` — platform overview and limits.
