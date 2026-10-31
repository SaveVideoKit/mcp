# SaveVideoKit

通过 **SaveVideoKit 远端 MCP 服务**下载 / 查看公开视频（YouTube、TikTok、Instagram、Facebook、X/Twitter、Reddit、Vimeo、Dailymotion）。无需 API key。当源站提供可直接下载的文件时，下载会**直达源站 CDN 上的原始地址**——服务端不做下载、合并或存储。本仓库把技能与 MCP 接入配置整理为多客户端结构，便于在 WorkBuddy、Codex、Claude Code、Cursor、opencode、dsh 等客户端复用与扩展。

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
│   ├── SERVER_CONTRACT.md       # 服务端 instructions / 工具描述强制契约
│   ├── setup.sh              # workbuddy|codex|claude-code|cursor|opencode|dsh|all
│   ├── workbuddy.mcp.json
│   ├── codex.mcp.json
│   ├── claude-code.mcp.json
│   ├── cursor.mcp.json
│   ├── opencode.mcp.json
│   └── dsh.mcp.json
└── cli/                      # ★ 独立 MCP 客户端（零依赖，直接说 MCP 协议）
    └── savevideokit_cli.py  # inspect→直连下载（优先）或任务→落盘，可脱离任何客户端单独运行
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

`cli/savevideokit_cli.py` 是一个**零依赖**（仅 Python 标准库）的 MCP Streamable HTTP 客户端，自己完成 `initialize` 握手 → `inspect_video` → **有直连就直连下载**（没有才回退 `create_download` + 轮询）→ 本地落盘，不需要任何客户端的 MCP 集成即可运行。适合直接命令行使用，或给尚未接入 MCP 的客户端当底层工具。

```bash
# 仅查看视频信息
python3 cli/savevideokit_cli.py --inspect-only "https://www.youtube.com/watch?v=xxxx"

# 完整流程：检查 + 下载（能直连就直连源站 CDN）到 ./downloads
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
python3 cli/savevideokit_cli.py "https://youtu.be/xxxx" --quality 1080p

# 列出已验证支持的平台
python3 cli/savevideokit_cli.py --list-sites
```

> 与技能内 `scripts/download_file.py` 的分工：`savevideokit_cli.py` 负责「说 MCP 协议跑完整流程」；`download_file.py` 只负责「拿到 download_url 后把字节落盘」这一步。两者可独立使用。

## 下载策略（务必保留）

**0. 禁止本地解析。** 视频页面解析、源流下载和视音频合并只能由远端 SaveVideoKit MCP 执行。绝不安装或调用本地 `yt-dlp` / `youtube-dl` / `ffmpeg`。本地 `curl -L`、`wget`、PowerShell 或 Python HTTP 代码只能保存 MCP 返回的最终 `download_url`，不能用来解析原始视频页面。
只接入 MCP 而不安装技能的客户端，还必须在服务端部署 [`mcp/SERVER_CONTRACT.md`](mcp/SERVER_CONTRACT.md) 中的 `initialize.instructions` 和工具描述。

**1. 优先直连（默认）。** `inspect_video` 返回 `direct_download_available` / `direct_options[]`，其中的 `download_url` 以 `302` 跳转到**源站 CDN 上的原始媒体文件**——字节从源站直接到本地，服务端不下载、不合并、不存储。**只要 `direct_options` 非空就必须走这条路**：不建 `create_download`、不轮询、没有保留期限。

**2. 只有在必须合并时才走中转。** 仅当源站压根没有完整单文件、需要服务端下载并合并音视频流时才调用 `create_download`。触发信号是明确的：`direct_download_available == false`、`direct_options == []`、所有 `formats[].direct_eligible == false`，或 `direct_reason` 为 `requires_headers`（CDN 绑定页面 Referer/UA，TikTok 典型）或 `not_mp4`（纯音频 / 容器不兼容）。此时返回的 `download_url` 是服务端生成的文件，保留 **30 分钟**（`file_retention_seconds = 1800`）。

**3. 无论如何都要落盘。** 两种方式 MCP 都不写本地磁盘，所以必须调用 `scripts/download_file.py` 把字节存下来，不能只把链接返给用户。链接过期时（任务 `expired`，直连 `403/404`）重新获取：新建 `create_download` 或重新 `inspect_video`——**不要因为直连过期就降级去走中转**。

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
