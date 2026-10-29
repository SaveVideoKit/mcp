# SaveVideoKit · Cursor

Cursor uses **rules** (`.cursor/rules/*.mdc`) instead of `SKILL.md`, plus MCP config.

## Setup
1. Copy the rule into your project (or user) rules dir:
   ```bash
   mkdir -p .cursor/rules
   cp cursor/rules/savevideokit.mdc .cursor/rules/
   ```
   Also copy `cursor/scripts/` and `cursor/references/` into the project so the rule's
   relative paths resolve (or adjust the paths in the rule).
2. Register the MCP server (project-level recommended):
   ```bash
   mkdir -p .cursor
   # merge mcp/cursor.mcp.json into .cursor/mcp.json (keep existing servers)
   ```
   or, from inside your project, run `bash mcp/setup.sh cursor`.
3. Reload Cursor — the rule and the `savevideokit` MCP server become active.

> Cursor MCP config lives at `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global).
> For remote servers, Cursor needs only a `url` (Streamable HTTP/SSE is auto-detected).
