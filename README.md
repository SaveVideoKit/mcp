# SaveVideoKit

Download / inspect public videos (YouTube, TikTok, Instagram, Facebook, X/Twitter, Reddit, Vimeo, Dailymotion) via the **SaveVideoKit remote MCP service**. No API key required. When the source exposes a browser-safe file, the download goes **straight to the original URL on the source CDN** — no server-side download, merge or storage. This repository organizes the skill and MCP integration config into a multi-client layout, so it can be reused and extended across WorkBuddy, Codex, Claude Code, Cursor, opencode, dsh and other clients.

## Repository structure

```
SaveVideoKit/
├── README.md                 # This file
├── INSTALL.md                # Agent-oriented guide: detect client → install matching files
├── clients.json              # Machine-readable client → skill dir + MCP config mapping
├── workbuddy/                # ★ Canonical source: the WorkBuddy skill
│   ├── SKILL.md
│   ├── references/constraints.md
│   └── scripts/download_file.py
├── codex/                    # Codex skill (scaffold)
├── claude-code/              # Claude Code skill (scaffold)
├── cursor/                   # Cursor rule (.cursor/rules) + scripts + references
│   └── rules/savevideokit.mdc
├── opencode/                 # opencode skill (SKILL.md)
├── dsh/                      # dsh skill (scaffold)
├── mcp/                      # Per-client MCP config snippets + setup.sh
│   ├── setup.sh              # workbuddy|codex|claude-code|cursor|opencode|dsh|all
│   ├── workbuddy.mcp.json
│   ├── codex.mcp.json
│   ├── claude-code.mcp.json
│   ├── cursor.mcp.json
│   ├── opencode.mcp.json
│   └── dsh.mcp.json
└── cli/                      # ★ Standalone MCP client (zero deps, speaks the MCP protocol directly)
    └── savevideokit_cli.py  # inspect→direct download (preferred) or job→save; runs standalone
```

- `workbuddy/` is the **single source of truth**; the other client folders mirror it, formatted for each client (Cursor uses a `.mdc` rule instead of `SKILL.md`).
- When adding or changing skill logic, edit in `workbuddy/` first, then sync to the other client directories.
- **Agent auto-install**: read `clients.json` + `INSTALL.md` to detect the current client and install only its files.

## Quick start (WorkBuddy example)

```bash
# 1) Register the MCP server (writes ~/.workbuddy/mcp.json)
bash mcp/setup.sh workbuddy

# 2) Install the skill: copy workbuddy/ as a WorkBuddy user-level skill
cp -r workbuddy ~/.workbuddy/skills/savevideokit
```

See each client directory's `README.md` for other clients.

## Standalone MCP client (cli/, usable without any client)

`cli/savevideokit_cli.py` is a **zero-dependency** (Python standard library only) MCP Streamable HTTP client. It performs the full flow on its own: `initialize` handshake → `inspect_video` → **direct download when the source offers one** (or `create_download` + polling as a fallback) → local save, with no client-side MCP integration required. It is suitable for direct command-line use, or as a low-level tool for clients that have not integrated MCP yet.

```bash
# Inspect video metadata only
python3 cli/savevideokit_cli.py --inspect-only "https://www.youtube.com/watch?v=xxxx"

# Full flow: inspect + download (straight from the source CDN when possible) to ./downloads
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
python3 cli/savevideokit_cli.py "https://youtu.be/xxxx" --quality 1080p

# Force the create_download job path even if a direct option exists
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456" --no-direct

# List verified supported platforms
python3 cli/savevideokit_cli.py --list-sites
```

> Division of labor vs `scripts/download_file.py`: `savevideokit_cli.py` "speaks the MCP protocol and runs the full flow"; `download_file.py` only "fetches the bytes once a download_url is obtained". They can be used independently.

## Critical download logic (must keep)

**Direct first, job as fallback.** `inspect_video` reports `direct_download_available` / `direct_options[]`; each `download_url` answers `302` and redirects to the **original media file on the source CDN**, so nothing is downloaded, muxed, merged or stored by the service. Take the best option and save it right away — no `create_download`, no polling, no retention window.

Only when no direct option exists does the fallback apply: `create_download` → poll `get_download_status` → the returned `download_url` is a **server-generated file retained for 30 minutes** (`file_retention_seconds = 1800`). Either way the MCP never writes to disk, so the workflow **must call `scripts/download_file.py` to persist the bytes** instead of handing the URL back to the user. If the URL expires (`expired`, or `403/404` on a direct link), obtain a fresh one — a new `create_download` job, or a new `inspect_video` call.

## Installation

See [`INSTALL.md`](INSTALL.md) for the full agent-oriented guide, or copy the prompt below into your AI client:

```
Install SaveVideoKit from https://github.com/SaveVideoKit/mcp.git — read INSTALL.md and clients.json, detect which client you are running in (WorkBuddy / Codex / Claude Code / Cursor / opencode / dsh), and install only that client's skill folder and mcp/<client>.mcp.json. Merge into existing config, don't overwrite.
```

## Auto-update

Each skill ships a self-updater. On first activation in a session, run:

```bash
python3 <skill>/scripts/check_update.py --auto
```

It compares the skill's `VERSION` with the latest GitHub release (cached 24h) and updates in place when a newer release exists, keeping a `<dir>.bak-<timestamp>` backup. Use `--check` to only report, `--force` to bypass the cache.

## Translations
- [中文 (Chinese)](README.zh-CN.md)
- [한국어 (Korean)](README.ko.md)
- [日本語 (Japanese)](README.ja.md)
