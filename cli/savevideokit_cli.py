#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SaveVideoKit MCP client (zero dependencies, Python standard library only).

Automates the full workflow and prefers the shortest path available:

  1. Direct path (preferred): inspect_video returns direct_options[] - URLs that answer
     302 and redirect straight to the original media file on the source CDN. Nothing is
     queued, merged or stored on the server, so this is the fastest route.
  2. Job path (fallback): create_download -> poll get_download_status -> save the
     download_url, used only when the source exposes no browser-safe progressive file.
     The generated file is retained for about 30 minutes.

This is a thin Streamable HTTP client for the remote MCP endpoint:
    https://mcp.savevideokit.com/mcp
No API key / OAuth / login required.

Examples:
    # 1) Inspect only (no download)
    python savevideokit_cli.py --inspect-only "https://www.youtube.com/shorts/xxxx"

    # 2) Full flow: inspect + download (direct when possible) + save to ./downloads
    python savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
    python savevideokit_cli.py "https://www.youtube.com/watch?v=xxxx" --quality 1080p

    # 3) Force the create_download job path even when a direct option exists
    python savevideokit_cli.py "https://www.tiktok.com/@user/video/123456" --no-direct

    # 4) List platforms verified by the service
    python savevideokit_cli.py --list-sites

Notes:
    - Public videos only; private/login/region-restricted content is unsupported; no watermark removal.
    - Direct links are signed and expire; re-run inspect_video (or this script) for a fresh one.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MCP_URL = "https://mcp.savevideokit.com/mcp"
PROTOCOL_VERSION = "2025-03-26"
USER_AGENT = "savevideokit-cli/1.0 (+https://www.savevideokit.com)"


def _headers():
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Mcp-Protocol-Version": PROTOCOL_VERSION,
        "User-Agent": USER_AGENT,
    }


class MCPError(RuntimeError):
    pass


class SaveVideoKitClient:
    """Minimal stateless MCP Streamable HTTP client (no session to maintain)."""

    def __init__(self, url=MCP_URL, timeout=60):
        self.url = url
        self.timeout = timeout
        self._id = 0

    def _next_id(self):
        self._id += 1
        return self._id

    @staticmethod
    def _parse_body(body: str, want_id):
        """Parse an MCP response, handling both plain JSON and SSE (text/event-stream)."""
        body = (body or "").strip()
        if not body:
            return None
        # 1) Plain JSON
        try:
            obj = json.loads(body)
            if want_id is None or obj.get("id") == want_id:
                return obj
        except json.JSONDecodeError:
            pass
        # 2) SSE: "event: message\ndata: {...}"
        last = None
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[len("data:"):].strip()
                try:
                    obj = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if want_id is None:
                    continue
                if obj.get("id") == want_id:
                    return obj
                last = obj
        return last if want_id is not None else None

    def _rpc(self, method, params=None, *, notification=False):
        mid = None if notification else self._next_id()
        payload = {"jsonrpc": "2.0", "method": method}
        if mid is not None:
            payload["id"] = mid
        if params is not None:
            payload["params"] = params
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers=_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise MCPError(f"HTTP {e.code}: {detail[:500]}")
        except urllib.error.URLError as e:
            raise MCPError(f"Network error: {e.reason}")

        obj = self._parse_body(raw, mid)
        if notification:
            return None
        if obj is None:
            raise MCPError("No valid response parsed")
        if "error" in obj:
            err = obj["error"]
            raise MCPError(f"MCP error [{err.get('code')}]: {err.get('message')}")
        return obj.get("result")

    # ---- High-level MCP calls ----
    def initialize(self):
        return self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "savevideokit-cli", "version": "1.0.0"},
            },
        )

    def notify_initialized(self):
        self._rpc("notifications/initialized", notification=True)

    def call_tool(self, name, arguments=None):
        return self._rpc("tools/call", {"name": name, "arguments": arguments or {}})

    def handshake(self):
        """Open a session (under stateless mode, initialize + notify every run)."""
        self.initialize()
        self.notify_initialized()

    # ---- Business methods ----
    def inspect(self, url):
        return self.call_tool("inspect_video", {"url": url})

    def create(self, url, fmt="mp4", quality=""):
        return self.call_tool("create_download", {"url": url, "format": fmt, "quality": quality})

    def status(self, job_id):
        return self.call_tool("get_download_status", {"job_id": job_id})

    def list_sites(self):
        return self.call_tool("get_supported_sites", {})


def _text_of(result):
    """Extract the text field from an MCP tools/call result."""
    if not result:
        return ""
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(p for p in parts if p)
        if "structuredContent" in result:
            return json.dumps(result["structuredContent"], ensure_ascii=False, indent=2)
    return json.dumps(result, ensure_ascii=False, indent=2)


def _download_file(url, dest, timeout=180, referer=""):
    """Stream a URL to disk. Redirects are followed, so a 302 to the origin CDN works."""
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    written = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        try:
            total = int(resp.headers.get("Content-Length", 0) or 0)
        except ValueError:
            total = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
    return written, total


def _unique_path(path):
    """Avoid clobbering an existing file: title.mp4 -> title (1).mp4."""
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def _sanitize(name, fallback="video"):
    """Build a readable, filesystem-safe filename from a video title."""
    if not name:
        return fallback
    keep = []
    for ch in str(name):
        if ch.isalnum() or ch in (" ", "-", "_", ".", "(", ")", "[", "]", "&", "+"):
            keep.append(ch)
        else:
            keep.append(" ")
    s = re.sub(r"\s+", " ", "".join(keep)).strip(" ._")
    s = s[:120].strip(" ._")
    return s or fallback


def _extract_title(info):
    """Best-effort extraction of the video title from an inspect_video result."""
    if isinstance(info, dict):
        sc = info.get("structuredContent")
        if isinstance(sc, dict):
            t = sc.get("title") or (sc.get("metadata") or {}).get("title")
            if t:
                return str(t).strip()
    text = _text_of(info)
    # Localized labels are written as escapes so the source stays ASCII-only:
    # U+6807 U+9898 (zh), U+30BF U+30A4 U+30C8 U+30EB (ja), U+C81C U+BAA9 (ko), U+FF1A full-width colon.
    m = re.search(r"(?im)^\s*(?:title|\u6807\u9898|\u30bf\u30a4\u30c8\u30eb|\uc81c\ubaa9)\s*[:\uff1a]\s*(.+?)\s*$", text)
    if m:
        return m.group(1).strip()
    m = re.search(r'"title"\s*:\s*"([^"]+)"', text)
    if m:
        return m.group(1).strip()
    return None


def _derive_name_from_url(url):
    """Deterministic, meaningful fallback name from the source URL (never random)."""
    try:
        from urllib.parse import urlparse, parse_qs
        p = urlparse(url)
        q = parse_qs(p.query)
        if q.get("v"):
            return "youtube_" + q["v"][0]
        segs = [s for s in p.path.split("/") if s]
        if segs:
            last = segs[-1]
            if "." in last:
                last = last.rsplit(".", 1)[0]
            host = p.netloc.replace("www.", "").split(".")[0]
            host = {"youtu": "youtube", "twitter": "x"}.get(host, host)
            if last:
                return (host + "_" + last) if host else last
    except Exception:
        pass
    return "video"


def _quality_cap(quality):
    """Parse a quality cap such as '1080p' / '720' into an int height, else None."""
    m = re.search(r"(\d{3,4})", str(quality or ""))
    return int(m.group(1)) if m else None


def _pick_direct_option(sc, quality="", fmt="mp4"):
    """Choose the best direct option from inspect_video structuredContent.

    Preference: highest resolution within the requested quality cap, then largest file.
    Returns None when the source offers no direct option.
    """
    if not isinstance(sc, dict):
        return None
    opts = [o for o in (sc.get("direct_options") or [])
            if isinstance(o, dict) and o.get("download_url")]
    if not opts:
        return None

    if fmt and fmt.lower() not in ("mp4", "best"):
        same = [o for o in opts if str(o.get("ext", "")).lower() == fmt.lower()]
        if same:
            opts = same

    def height(o):
        try:
            return int(o.get("height") or 0)
        except (TypeError, ValueError):
            return 0

    cap = _quality_cap(quality)
    if cap:
        within = [o for o in opts if 0 < height(o) <= cap]
        if within:
            opts = within

    opts.sort(key=lambda o: (height(o), int(o.get("filesize") or 0)), reverse=True)
    return opts[0]


def cmd_list_sites(client):
    res = client.list_sites()
    print(_text_of(res))


def cmd_inspect(client, url):
    res = client.inspect(url)
    print(_text_of(res))


def cmd_download(client, url, fmt, quality, out_dir, poll_interval, poll_timeout, allow_direct=True):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Inspecting video: {url}")
    info = client.inspect(url)
    print(_text_of(info))

    sc = info.get("structuredContent") if isinstance(info, dict) else {}
    sc = sc if isinstance(sc, dict) else {}

    # Readable filename base from the video title (never a random id)
    title = _extract_title(info)
    base = _sanitize(title or _derive_name_from_url(url), "video")
    print("-" * 60)

    # Preferred path: a direct option points at the original file on the source CDN.
    option = _pick_direct_option(sc, quality, fmt) if allow_direct else None
    if option:
        ext = "." + str(option.get("ext") or "mp4").lstrip(".")
        h = option.get("height") or 0
        res = option.get("resolution") or (f"{h}p" if h else "source")
        print(f"[2/3] Direct source URL available ({res}) - downloading from the origin, no queue or merge")
        dest = _unique_path(out_dir / (base + ext))
        try:
            written, _ = _download_file(
                option["download_url"], dest,
                referer=sc.get("webpage_url") or url,
            )
        except urllib.error.HTTPError as e:
            raise MCPError(
                f"Direct download failed: HTTP {e.code}. The signed link may have expired - "
                f"run the command again to obtain a fresh direct option.")
        if written <= 0:
            dest.unlink(missing_ok=True)
            raise MCPError("Direct download produced an empty file; nothing was saved.")
        print(f"      ✅ Saved: {dest}  ({written / 1024 / 1024:.2f} MB)")
        print("      Fetched straight from the source CDN - the service stored nothing.")
        return

    if allow_direct:
        print("[2/3] No direct source URL for this link - falling back to a download job ...")
    else:
        print("[2/3] Direct options skipped (--no-direct) - using a download job ...")
    created = client.create(url, fmt=fmt, quality=quality)
    created_sc = created.get("structuredContent", {}) if isinstance(created, dict) else {}
    job_id = created_sc.get("job_id") or created_sc.get("id")
    if not job_id:
        # Fall back to parsing the full text
        m = re.search(r"job[_\s-]?id['\"]?\s*[:=]\s*['\"]?([\w-]+)", _text_of(created), re.I)
        job_id = m.group(1) if m else None
    if not job_id:
        raise MCPError(f"Could not obtain job_id, create returned:\n{_text_of(created)}")
    print(f"      Task created, job_id = {job_id}")

    print("[3/3] Polling download status ...")
    deadline = time.time() + poll_timeout
    final = None
    while time.time() < deadline:
        time.sleep(poll_interval)
        st = client.status(job_id)
        st_sc = st.get("structuredContent", {}) if isinstance(st, dict) else {}
        status = st_sc.get("status") or "?"
        progress = st_sc.get("progress")
        prog = f" ({progress}%)" if isinstance(progress, (int, float)) else ""
        print(f"      status = {status}{prog}")
        if status == "success":
            final = st_sc
            break
        if status in ("failed", "error", "expired"):
            raise MCPError(f"Download failed: status={status}\n{_text_of(st)}")
    else:
        raise MCPError(f"Polling timed out (>{poll_timeout}s); the task may still be processing. Re-query later with job_id={job_id}.")

    download_url = final.get("download_url") or final.get("url")
    if not download_url:
        raise MCPError(f"Download succeeded but no download_url returned:\n{json.dumps(final, ensure_ascii=False)}")

    ext = next((o.get("ext") for o in (sc.get("direct_options") or [])
                if isinstance(o, dict) and o.get("format_id") == final.get("format_id")), None)
    if ext:
        ext = "." + str(ext).lstrip(".")
    else:
        ext = ".mp4"
        tail = download_url.split("?")[0].split("/")[-1]
        if "." in tail:
            cand = tail.rsplit(".", 1)[-1][:8]
            if 2 <= len(cand) <= 9:
                ext = "." + cand

    dest = _unique_path(out_dir / (base + ext))
    print(f"      Saving to {dest} ...")
    written, _ = _download_file(download_url, dest)
    if written <= 0:
        dest.unlink(missing_ok=True)
        raise MCPError("Download produced an empty file; nothing was saved.")
    print(f"      ✅ Saved: {dest}  ({written / 1024 / 1024:.2f} MB)")
    print("      Note: the generated file is retained for about 30 minutes; the local copy is yours.")


def main():
    p = argparse.ArgumentParser(
        description="SaveVideoKit MCP client: inspect -> direct download (preferred) or job -> save",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", nargs="?", help="Public video URL (mutually exclusive with --list-sites)")
    p.add_argument("--inspect-only", action="store_true", help="Inspect video metadata only, do not download")
    p.add_argument("--list-sites", action="store_true", help="List verified supported platforms")
    p.add_argument("--format", default="mp4", help="Output format mp4/best or a format selector (default mp4)")
    p.add_argument("--quality", default="", help="Upper quality bound, e.g. 1080p/720p/480p")
    p.add_argument("--output", default="./downloads", help="Output directory (default ./downloads)")
    p.add_argument("--no-direct", action="store_true",
                   help="Skip direct_options and always use the create_download job path")
    p.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval in seconds (default 5)")
    p.add_argument("--poll-timeout", type=float, default=300.0, help="Poll timeout in seconds (default 300)")
    p.add_argument("--mcp-url", default=MCP_URL, help="MCP endpoint (defaults to the official address)")
    args = p.parse_args()

    if not args.list_sites and not args.url:
        p.error("Provide a video URL, or use --list-sites / --inspect-only")

    client = SaveVideoKitClient(url=args.mcp_url)
    try:
        print(">>> Handshaking with MCP service (initialize) ...")
        client.handshake()
        if args.list_sites:
            cmd_list_sites(client)
        elif args.inspect_only:
            cmd_inspect(client, args.url)
        else:
            cmd_download(
                client, args.url, args.format, args.quality,
                args.output, args.poll_interval, args.poll_timeout,
                allow_direct=not args.no_direct,
            )
    except MCPError as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
