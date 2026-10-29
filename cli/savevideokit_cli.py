#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SaveVideoKit MCP client (zero dependencies, Python standard library only).

Automates the full workflow: inspect -> create download -> poll status -> save file.

This is a thin Streamable HTTP client for the remote MCP endpoint:
    https://mcp.savevideokit.com/mcp
No API key / OAuth / login required.

Examples:
    # 1) Inspect only (no download)
    python savevideokit_cli.py --inspect-only "https://www.youtube.com/shorts/xxxx"

    # 2) Full flow: inspect + download + poll + save to ./downloads
    python savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
    python savevideokit_cli.py "https://www.youtube.com/watch?v=xxxx" --quality 1080p

    # 3) List platforms verified by the service
    python savevideokit_cli.py --list-sites

Notes:
    - Public videos only; private/login/region-restricted content is unsupported; no watermark removal.
    - The remote file is retained for only 2 hours; save it locally as soon as the download succeeds.
"""

import argparse
import json
import os
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


def _download_file(url, dest, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    written = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0) or 0)
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
    return written, total


def _safe_filename(name, fallback):
    if not name:
        return fallback
    keep = []
    for ch in name:
        if ch.isalnum() or ch in (" ", "-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    s = "".join(keep).strip().replace(" ", "_")
    return s[:120] or fallback


def cmd_list_sites(client):
    res = client.list_sites()
    print(_text_of(res))


def cmd_inspect(client, url):
    res = client.inspect(url)
    print(_text_of(res))


def cmd_download(client, url, fmt, quality, out_dir, poll_interval, poll_timeout):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Inspecting video: {url}")
    info = client.inspect(url)
    text = _text_of(info)
    print(text)

    # Try to read the title from the structured result (used for naming)
    title = None
    try:
        sc = info.get("structuredContent", {})
        title = sc.get("title") or sc.get("metadata", {}).get("title")
    except Exception:
        title = None
    print("-" * 60)

    print("[2/4] Creating download task ...")
    created = client.create(url, fmt=fmt, quality=quality)
    created_sc = created.get("structuredContent", {}) if isinstance(created, dict) else {}
    job_id = created_sc.get("job_id") or created_sc.get("id")
    if not job_id:
        # Fall back to parsing the full text
        import re
        m = re.search(r"job[_\s-]?id['\"]?\s*[:=]\s*['\"]?([\w-]+)", _text_of(created), re.I)
        job_id = m.group(1) if m else None
    if not job_id:
        raise MCPError(f"Could not obtain job_id, create returned:\n{_text_of(created)}")
    print(f"      Task created, job_id = {job_id}")

    print("[3/4] Polling download status ...")
    deadline = time.time() + poll_timeout
    final = None
    while time.time() < deadline:
        time.sleep(poll_interval)
        st = client.status(job_id)
        sc = st.get("structuredContent", {}) if isinstance(st, dict) else {}
        status = sc.get("status") or "?"
        progress = sc.get("progress")
        prog = f" ({progress}%)" if isinstance(progress, (int, float)) else ""
        print(f"      status = {status}{prog}")
        if status == "success":
            final = sc
            break
        if status in ("failed", "error", "expired"):
            raise MCPError(f"Download failed: status={status}\n{_text_of(st)}")
    else:
        raise MCPError(f"Polling timed out (>{poll_timeout}s); the task may still be processing. Re-query later with job_id={job_id}.")

    download_url = final.get("download_url") or final.get("url")
    if not download_url:
        raise MCPError(f"Download succeeded but no download_url returned:\n{json.dumps(final, ensure_ascii=False)}")

    print(f"[4/4] Downloading file -> {out_dir}/")
    ext = ".mp4"
    if "." in download_url.split("?")[0].split("/")[-1]:
        ext = "." + download_url.split("?")[0].rsplit(".", 1)[-1].split("/")[-1][:8]
    fname = _safe_filename(title, job_id) + ext
    dest = out_dir / fname
    written, total = _download_file(download_url, dest)
    size = written / 1024 / 1024
    print(f"      ✅ Saved: {dest}  ({size:.2f} MB)")
    print("      Note: the remote file is retained for only ~2 hours; use the local copy promptly.")


def main():
    p = argparse.ArgumentParser(
        description="SaveVideoKit MCP client: inspect -> download -> poll -> save",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", nargs="?", help="Public video URL (mutually exclusive with --list-sites)")
    p.add_argument("--inspect-only", action="store_true", help="Inspect video metadata only, do not download")
    p.add_argument("--list-sites", action="store_true", help="List verified supported platforms")
    p.add_argument("--format", default="mp4", help="Output format mp4/best or a format selector (default mp4)")
    p.add_argument("--quality", default="", help="Upper quality bound, e.g. 1080p/720p/480p")
    p.add_argument("--output", default="./downloads", help="Output directory (default ./downloads)")
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
            )
    except MCPError as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
