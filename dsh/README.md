# SaveVideoKit · dsh client

This directory is an initial copy (scaffold) of the SaveVideoKit skill for **dsh**.

## Setup
1. **Register the MCP server**: dsh's MCP integration method is not finalized yet; refer to `mcp/dsh.mcp.json` (same shape as other clients: `type: http`, `url: https://mcp.savevideokit.com/mcp`) and merge it into dsh's MCP config per its actual format.
2. **Install the skill**: copy this `dsh/` directory into dsh's skills directory, so the final path is `.../skills/savevideokit/SKILL.md`.
3. Say "download this video <URL>" in a conversation to trigger it.

> This directory is mirrored from the repo root `workbuddy/`; once the dsh client is determined, add the specific loading instructions here.
