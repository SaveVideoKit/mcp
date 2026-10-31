# SaveVideoKit

**SaveVideoKit リモート MCP サービス**を通じて、公開動画（YouTube、TikTok、Instagram、Facebook、X/Twitter、Reddit、Vimeo、Dailymotion）をダウンロード／確認できます。API キーは不要です。ソースが直接ダウンロード可能なファイルを公開している場合、ダウンロードは**ソース CDN 上の元 URL へ直接**行われます（サーバー側でのダウンロード・マージ・保存は行いません）。本リポジトリはスキルと MCP 連携設定をマルチクライアント構成で整理しており、WorkBuddy、Codex、Claude Code、Cursor、opencode、dsh など各クライアントで再利用・拡張できます。

## リポジトリ構成

```
SaveVideoKit/
├── README.md                 # 本ファイルの日本語版
├── INSTALL.md                # エージェント向けインストールガイド（クライアント判定 → 対応ファイル導入）
├── clients.json              # 機械可読：クライアント → スキルディレクトリ + MCP 設定の対応
├── workbuddy/                # ★ 正規ソース(canonical)：WorkBuddy スキル
│   ├── SKILL.md
│   ├── references/constraints.md
│   └── scripts/download_file.py
├── codex/                    # Codex スキル（スキャフォールド）
├── claude-code/              # Claude Code スキル（スキャフォールド）
├── cursor/                   # Cursor ルール（.cursor/rules）+ scripts + references
│   └── rules/savevideokit.mdc
├── opencode/                 # opencode スキル（SKILL.md）
├── dsh/                      # dsh スキル（スキャフォールド）
├── mcp/                      # クライアント別 MCP 設定スニペット + setup.sh
│   ├── setup.sh              # workbuddy|codex|claude-code|cursor|opencode|dsh|all
│   ├── workbuddy.mcp.json
│   ├── codex.mcp.json
│   ├── claude-code.mcp.json
│   ├── cursor.mcp.json
│   ├── opencode.mcp.json
│   └── dsh.mcp.json
└── cli/                      # ★ スタンドアロン MCP クライアント（依存なし、MCP プロトコルを直接話す）
    └── savevideokit_cli.py  # inspect→直接ダウンロード（優先）またはジョブ→保存、単独実行可
```

- `workbuddy/` が**唯一の正規ソース**です。他のクライアントディレクトリはそれを各クライアント向けに整形したものです（Cursor は `SKILL.md` ではなく `.mdc` ルールを使用）。
- スキルロジックを追加・変更する際は、まず `workbuddy/` で作業し、その後他のクライアントディレクトリへ同期してください。
- **エージェント自動インストール**：`clients.json` と `INSTALL.md` を読み、現在のクライアントを判定して対応ファイルのみを導入します。

## クイックスタート（WorkBuddy の例）

```bash
# 1) MCP サーバーを登録（~/.workbuddy/mcp.json へ書き込み）
bash mcp/setup.sh workbuddy

# 2) スキルをインストール：workbuddy/ を WorkBuddy のユーザーレベルスキルとして複製
cp -r workbuddy ~/.workbuddy/skills/savevideokit
```

その他のクライアントは各ディレクトリの `README.md` を参照してください。

## スタンドアロン MCP クライアント（cli/、クライアントなしで利用可）

`cli/savevideokit_cli.py` は**依存関係のない**（Python 標準ライブラリのみの）MCP Streamable HTTP クライアントです。クライアント側の MCP 連携なしで自律的に全体のフローを実行します：`initialize` ハンドシェイク → `inspect_video` → **直接オプションがあれば直接ダウンロード**（なければ `create_download` + ポーリングにフォールバック）→ ローカル保存。コマンドラインでの直接利用や、まだ MCP を連携していないクライアントの下位ツールとして適しています。

```bash
# 動画メタデータのみ確認
python3 cli/savevideokit_cli.py --inspect-only "https://www.youtube.com/watch?v=xxxx"

# 全体フロー：確認 + ダウンロード（可能ならソース CDN から直接）→ ./downloads
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
python3 cli/savevideokit_cli.py "https://youtu.be/xxxx" --quality 1080p

# 対応プラットフォーム一覧を表示
python3 cli/savevideokit_cli.py --list-sites
```

> `scripts/download_file.py` との役割分担：`savevideokit_cli.py` は「MCP プロトコルを話して全体フローを実行」し、`download_file.py` は「download_url を取得した後のバイト列のディスク保存」のみを担います。両者は独立して利用可能です。

## ダウンロード方針（必ず維持）

**0. ローカル解析は禁止。** ページ解析、ソースストリームの取得、音声・映像のマージはリモート SaveVideoKit MCP で実行します。ローカルの `yt-dlp` / `youtube-dl` / `ffmpeg` はインストールも実行もしません。`curl -L`、`wget`、PowerShell、Python HTTP は MCP が返す最終 `download_url` の保存にのみ使用します。

**1. 直接ダウンロードを優先（既定）。** `inspect_video` は `direct_download_available` / `direct_options[]` を返し、その `download_url` は `302` で**ソース CDN 上の元メディアファイル**へリダイレクトします。バイト列はソースから直接ローカルへ流れ、サーバー側のダウンロード・マージ・保存は一切ありません。**`direct_options` が空でない限り、必ずこの経路を使います**（`create_download` もポーリングも不要、保持期限もなし）。

**2. マージが不可避な場合のみ中継を使う。** ソースに完全な単一ファイルがなく、サーバー側で音声と映像をダウンロード＋マージする必要がある場合に限り `create_download` を呼びます。判定材料は明確です：`direct_download_available == false`、`direct_options == []`、すべての `formats[].direct_eligible == false`、または `direct_reason` が `requires_headers`（CDN がページの Referer/UA に紐づく。TikTok が典型）や `not_mp4`（音声のみ／非対応コンテナ）。この場合に返る `download_url` はサーバー生成ファイルで、保持は **30 分**（`file_retention_seconds = 1800`）。

**3. どの経路でも必ず保存する。** MCP はディスクに書き込まないため、`scripts/download_file.py` でバイト列を保存する必要があり、URL だけをユーザーに返してはいけません。リンクが失効した場合（ジョブは `expired`、直接リンクは `403/404`）は、新しい `create_download` または `inspect_video` の再実行で取り直します。**直接リンクの失効を理由に中継へ降格しないでください。**

## インストール

詳細な手順は [`INSTALL.md`](INSTALL.md) を参照してください。または以下のプロンプトを AI クライアントに貼り付けてください:

```
https://github.com/SaveVideoKit/mcp.git から SaveVideoKit をインストールします。まず INSTALL.md と clients.json を読み、現在のクライアント（WorkBuddy / Codex / Claude Code / Cursor / opencode / dsh）を判定し、対応するスキルディレクトリと mcp/<client>.mcp.json のみをインストールしてください。既存の設定には上書きせずマージしてください。
```

## その他の言語
- [English](README.md)
- [中文 (Chinese)](README.zh-CN.md)
- [한국어 (Korean)](README.ko.md)
