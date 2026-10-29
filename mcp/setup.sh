#!/usr/bin/env bash
# SaveVideoKit MCP registration script
# Registers the SaveVideoKit remote MCP service (no API key) into various AI clients.
# Usage:
#   ./setup.sh                 # register all known clients
#   ./setup.sh workbuddy       # WorkBuddy only
#   ./setup.sh codex           # Codex only
#   ./setup.sh claude-code     # Claude Code only
#   ./setup.sh cursor          # Cursor (project .cursor/mcp.json)
#   ./setup.sh opencode        # opencode (project opencode.json)
#   ./setup.sh dsh             # dsh only (placeholder; merge manually)
set -euo pipefail

MCP_NAME="savevideokit"
MCP_URL="https://mcp.savevideokit.com/mcp"

merge_mcp_servers_json() {
  # $1 = config path, $2 = server name, $3 = url  (mcpServers-style, e.g. WorkBuddy/Codex/Cursor)
  local cfg="$1"
  mkdir -p "$(dirname "$cfg")"
  python3 - "$cfg" "$2" "$3" <<'PY'
import json, sys, os
cfg, name, url = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(cfg) and os.path.getsize(cfg) > 0:
    with open(cfg) as f:
        data = json.load(f)
servers = data.setdefault("mcpServers", {})
servers[name] = {"type": "http", "url": url}
with open(cfg, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"wrote {cfg}")
PY
}

register_workbuddy() {
  merge_mcp_servers_json "$HOME/.workbuddy/mcp.json" "$MCP_NAME" "$MCP_URL"
  echo "[workbuddy] ok"
}

register_codex() {
  merge_mcp_servers_json "$HOME/.codex/codex.json" "$MCP_NAME" "$MCP_URL"
  echo "[codex] ok"
}

register_claude_code() {
  if command -v claude >/dev/null 2>&1; then
    claude mcp add --transport http "$MCP_NAME" "$MCP_URL"
    echo "[claude-code] registered via CLI"
  else
    echo "[claude-code] CLI not found; merge mcp/claude-code.mcp.json into ~/.claude.json mcpServers, or add a project .mcp.json"
  fi
}

register_cursor() {
  # Project-level .cursor/mcp.json (remote server needs only a url)
  local cfg=".cursor/mcp.json"
  mkdir -p "$(dirname "$cfg")"
  python3 - "$cfg" "$MCP_NAME" "$MCP_URL" <<'PY'
import json, sys, os
cfg, name, url = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(cfg) and os.path.getsize(cfg) > 0:
    with open(cfg) as f:
        data = json.load(f)
servers = data.setdefault("mcpServers", {})
servers[name] = {"url": url}
with open(cfg, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"[cursor] wrote {cfg}")
PY
}

register_opencode() {
  # Project-level opencode.json (mcp key, remote type)
  local cfg="opencode.json"
  python3 - "$cfg" "$MCP_NAME" "$MCP_URL" <<'PY'
import json, sys, os
cfg, name, url = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(cfg) and os.path.getsize(cfg) > 0:
    with open(cfg) as f:
        data = json.load(f)
data.setdefault("$schema", "https://opencode.ai/config.json")
mcp = data.setdefault("mcp", {})
mcp[name] = {"type": "remote", "url": url, "enabled": True}
with open(cfg, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"[opencode] wrote {cfg}")
PY
}

register_dsh() {
  echo "[dsh] integration method TBD; merge mcp/dsh.mcp.json into dsh's MCP config manually"
}

case "${1:-all}" in
  workbuddy)          register_workbuddy ;;
  codex)              register_codex ;;
  claude|claude-code) register_claude_code ;;
  cursor)             register_cursor ;;
  opencode)           register_opencode ;;
  dsh)                register_dsh ;;
  all)                register_workbuddy; register_codex; register_claude_code; register_cursor; register_opencode; register_dsh ;;
  *) echo "Usage: $0 [workbuddy|codex|claude-code|cursor|opencode|dsh|all]"; exit 1 ;;
esac
