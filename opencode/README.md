# SaveVideoKit · opencode

opencode supports Agent Skills (`SKILL.md`) and MCP servers.

## Setup
1. Install the skill (project or global):
   ```bash
   mkdir -p .opencode/skills
   cp -r opencode .opencode/skills/savevideokit
   # global: cp -r opencode ~/.config/opencode/skills/savevideokit
   ```
2. Register the MCP server by merging `mcp/opencode.mcp.json` into `opencode.json`
   (project) or `~/.config/opencode/opencode.json` (global):
   ```json
   { "mcp": { "savevideokit": { "type": "remote", "url": "https://mcp.savevideokit.com/mcp", "enabled": true } } }
   ```
   or run `bash mcp/setup.sh opencode` (writes/merges project `opencode.json`).
3. Ask: "download this video &lt;URL&gt;".
