# SaveVideoKit · Claude Code

This directory is the SaveVideoKit skill for **Claude Code** (and Claude-compatible clients that support `SKILL.md`).

## Setup
1. **Register the MCP server** (one time):
   ```bash
   # Option A: official CLI
   claude mcp add --transport http savevideokit https://mcp.savevideokit.com/mcp

   # Option B: merge mcp/claude-code.mcp.json into ~/.claude.json mcpServers,
   #           or drop a project-level .mcp.json
   ```
2. **Install the skill**: copy this `claude-code/` directory into Claude's skills directory, e.g.:
   ```bash
   cp -r claude-code ~/.claude/skills/savevideokit
   ```
   so the final path is `~/.claude/skills/savevideokit/SKILL.md`.
3. Say "download this video <URL>" in a conversation to trigger it.

> This directory is mirrored from the repo root `workbuddy/` and is an initial scaffold; adjust in place if Claude Code requires a specific skill format.
