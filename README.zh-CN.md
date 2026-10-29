# SaveVideoKit

通过 **SaveVideoKit 远端 MCP 服务**下载 / 查看公开视频（YouTube、TikTok、Instagram、Facebook、X/Twitter、Reddit、Vimeo、Dailymotion）。无需 API key。本仓库把技能与 MCP 接入配置整理为多客户端结构，便于在 WorkBuddy、Codex、Claude Code、Cursor、opencode、dsh 等客户端复用与扩展。

## 仓库结构

```
SaveVideoKit/
├── README.md                 # 本文件（中文）
├── INSTALL.md                # 面向 Agent 的安装指南（识别客户端 → 装对应文件）
├── clients.json              # 机器可读：客户端 → 技能目录 + MCP 配置 映射
├── workbuddy/                # ★ 规范来源（canonical）：WorkBuddy 技能
│   ├── SKILL.md
│   ├── references/constraints.md
│   └── scripts/download_file.py
├── codex/                    # Codex 技能（脚手架）
├── claude-code/              # Claude Code 技能（脚手架）
├── cursor/                   # Cursor 规则（.cursor/rules）+ scripts + references
│   └── rules/savevideokit.mdc
├── opencode/                 # opencode 技能（SKILL.md）
├── dsh/                      # dsh 技能（脚手架）
├── mcp/                      # 各客户端 MCP 配置片段 + setup.sh
│   ├── setup.sh              # workbuddy|codex|claude-code|cursor|opencode|dsh|all
│   ├── workbuddy.mcp.json
│   ├── codex.mcp.json
│   ├── claude-code.mcp.json
│   ├── cursor.mcp.json
│   ├── opencode.mcp.json
│   └── dsh.mcp.json
└── cli/                      # ★ 独立 MCP 客户端（零依赖，直接说 MCP 协议）
    └── savevideokit_cli.py  # inspect→create→poll→落盘，可脱离任何客户端单独运行
```

- `workbuddy/` 是**唯一规范来源**；其它客户端目录由它镜像、按各客户端格式组织（Cursor 用 `.mdc` 规则而非 `SKILL.md`）。
- 新增或修改技能逻辑时，请先在 `workbuddy/` 改，再同步到其它客户端目录。
- **Agent 自动安装**：读取 `clients.json` + `INSTALL.md`，识别当前客户端，只安装对应文件。

## 快速开始（以 WorkBuddy 为例）

```bash
# 1) 注册 MCP（写入 ~/.workbuddy/mcp.json）
bash mcp/setup.sh workbuddy

# 2) 安装技能：把 workbuddy/ 复制为 WorkBuddy 的用户级技能
cp -r workbuddy ~/.workbuddy/skills/savevideokit
```

其它客户端见各自目录下的 `README.md`。

## 独立 MCP 客户端（cli/，可脱离客户端直接用）

`cli/savevideokit_cli.py` 是一个**零依赖**（仅 Python 标准库）的 MCP Streamable HTTP 客户端，自己完成 `initialize` 握手 → `inspect` / `create_download` / `get_download_status` 工具调用 → 本地落盘，不需要任何客户端的 MCP 集成即可运行。适合直接命令行使用，或给尚未接入 MCP 的客户端当底层工具。

```bash
# 仅查看视频信息
python3 cli/savevideokit_cli.py --inspect-only "https://www.youtube.com/watch?v=xxxx"

# 完整流程：检查 + 创建 + 轮询 + 下载到 ./downloads
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
python3 cli/savevideokit_cli.py "https://youtu.be/xxxx" --quality 1080p

# 列出已验证支持的平台
python3 cli/savevideokit_cli.py --list-sites
```

> 与技能内 `scripts/download_file.py` 的分工：`savevideokit_cli.py` 负责「说 MCP 协议跑完整流程」；`download_file.py` 只负责「拿到 download_url 后把字节落盘」这一步。两者可独立使用。

## 关键下载逻辑（务必保留）

SaveVideoKit MCP **只返回 `download_url`，不会把文件存到本地**，且远端文件仅保留约 2 小时。因此技能工作流在「拿到 download_url」之后**必须立即调用 `scripts/download_file.py` 把字节落盘**，不能只把链接返给用户；若 URL 过期（`expired`）则重新 `create_download` 取得新任务。

## 安装

完整步骤见 [`INSTALL.md`](INSTALL.md)，或把下面的提示词粘贴到你的 AI 客户端：

```
请从 https://github.com/SaveVideoKit/mcp.git 安装 SaveVideoKit：先读 INSTALL.md 和 clients.json，判断你当前运行在哪个客户端（WorkBuddy / Codex / Claude Code / Cursor / opencode / dsh），只安装该客户端对应的技能目录和 mcp/<client>.mcp.json；合并进现有配置，不要覆盖。
```

## 自动更新

每个技能内置自更新器。技能首次激活时运行：

```bash
python3 <skill>/scripts/check_update.py --auto
```

它会将技能 `VERSION` 与 GitHub 最新 Release 比对（缓存 24 小时），有新版则就地更新并保留带时间戳的备份。`--check` 仅报告，`--force` 跳过缓存。

## 其它语言
- [English](README.md)
- [한국어 (Korean)](README.ko.md)
- [日本語 (Japanese)](README.ja.md)
