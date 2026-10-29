# Install SaveVideoKit (agent-oriented)

This repo ships the SaveVideoKit skill and MCP integration for several AI clients. Each
client uses a different skill format and MCP config location. **Detect the client you are
running in, then install only that client's files.** Do not install other clients unless
explicitly asked.

## 1. Detect your client

| # | Client | Hint |
|---|--------|------|
| 1 | WorkBuddy | running inside WorkBuddy |
| 2 | Codex | running inside OpenAI Codex |
| 3 | Claude Code | running inside Claude Code |
| 4 | Cursor | running inside Cursor |
| 5 | opencode | running inside opencode |
| 6 | dsh | running inside dsh |

If unsure, inspect which config path exists: `~/.workbuddy`, `~/.codex`, `~/.claude`,
`~/.cursor`, `~/.config/opencode`.

## 2. Read the manifest

`clients.json` maps each client id to:

- `skillDir` — folder in this repo holding the skill in that client's native format
- `skillFormat` — `skill-md` (SKILL.md) or `cursor-rule-mdc` (Cursor rule)
- `skillTarget` — where to install it
- `mcpConfigFile` — the MCP config snippet for that client
- `mcpFormat` — `mcpServers-json` or `opencode-mcp-json`
- `mcpTarget` — where that client reads its MCP config
- `setup` — one-line automated registration

## 3. Install (for the detected client `<id>`)

1. **Skill** — copy `skillDir` to `skillTarget` (create parent dirs).
   - `skill-md`: copy the whole folder so `<skillTarget>/SKILL.md` exists.
   - `cursor-rule-mdc`: copy `cursor/rules/savevideokit.mdc` into `.cursor/rules/`,
     plus `cursor/scripts/` and `cursor/references/` alongside.
2. **MCP** — merge `mcpConfigFile` into `mcpTarget`:
   - **Merge, never overwrite.** Keep existing MCP servers / skills.
   - If the file does not exist, create it from the snippet.
3. Or run the automated command from the manifest:
   ```
   bash mcp/setup.sh <id>
   ```

## 4. Verify

Confirm the `savevideokit` MCP server is registered and exposes the tools
`inspect_video`, `create_download`, `get_download_status`, `get_supported_sites`.
Then try: "download this video <URL>".

## Notes per client

- **Cursor**: rules live in `.cursor/rules/*.mdc`; MCP in `.cursor/mcp.json` (project) or
  `~/.cursor/mcp.json`. Remote MCP needs only a `url`.
- **opencode**: skill at `.opencode/skills/<name>/SKILL.md`; MCP under the `mcp` key in
  `opencode.json` with `{"type":"remote","url":...}`.
- **Claude Code**: skill at `~/.claude/skills/<name>/SKILL.md`; MCP via `claude mcp add`
  or a project `.mcp.json`.
- **Codex / dsh**: scaffolded; adjust to the client's native config if it differs.

## Safety

- Install only the current client's files; never install all clients unless asked.
- Preserve existing skills and MCP servers: merge, don't replace whole config files.
