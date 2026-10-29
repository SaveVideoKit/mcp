# SaveVideoKit · Codex client

This directory is a copy of the SaveVideoKit skill for **OpenAI Codex** (and Codex-compatible clients that support SKILL.md).

## Setup
1. **Register the MCP server** (one time):
   ```bash
   # Option A: auto-merge into ~/.codex/codex.json via the script
   bash mcp/setup.sh codex

   # Option B: manually merge mcp/codex.mcp.json mcpServers into ~/.codex/codex.json
   ```
2. **Install the skill**: copy this `codex/` directory into Codex's skills directory (path depends on the Codex client), so the final path is `.../skills/savevideokit/SKILL.md`.
3. Say "download this video <URL>" in a conversation to trigger it.

> This directory is mirrored from the repo root `workbuddy/` and is an initial scaffold; adjust in place if Codex requires a specific skill format.
