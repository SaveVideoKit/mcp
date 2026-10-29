# SaveVideoKit

**SaveVideoKit リモート MCP サービス**を通じて、公開動画（YouTube、TikTok、Instagram、Facebook、X/Twitter、Reddit、Vimeo、Dailymotion）をダウンロード／確認できます。API キーは不要です。本リポジトリはスキルと MCP 連携設定をマルチクライアント構成で整理しており、WorkBuddy、Codex、Claude Code、Cursor、opencode、dsh など各クライアントで再利用・拡張できます。

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
    └── savevideokit_cli.py  # inspect→create→poll→保存、クライアントなしで単独実行可
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

`cli/savevideokit_cli.py` は**依存関係のない**（Python 標準ライブラリのみの）MCP Streamable HTTP クライアントです。クライアント側の MCP 連携なしで自律的に全体のフローを実行します：`initialize` ハンドシェイク → `inspect` / `create_download` / `get_download_status` ツール呼び出し → ローカル保存。コマンドラインでの直接利用や、まだ MCP を連携していないクライアントの下位ツールとして適しています。

```bash
# 動画メタデータのみ確認
python3 cli/savevideokit_cli.py --inspect-only "https://www.youtube.com/watch?v=xxxx"

# 全体フロー：確認 + 作成 + ポーリング + ./downloads へダウンロード
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
python3 cli/savevideokit_cli.py "https://youtu.be/xxxx" --quality 1080p

# 対応プラットフォーム一覧を表示
python3 cli/savevideokit_cli.py --list-sites
```

> `scripts/download_file.py` との役割分担：`savevideokit_cli.py` は「MCP プロトコルを話して全体フローを実行」し、`download_file.py` は「download_url を取得した後のバイト列のディスク保存」のみを担います。両者は独立して利用可能です。

## 重要なダウンロードロジック（必ず維持）

SaveVideoKit MCP は **`download_url` のみを返し、ファイルをローカルに保存しません**。また、リモートファイルは約 2 時間しか保持されません。したがって `download_url` を取得した後、スキルワークフローは **直ちに `scripts/download_file.py` を呼び出してバイト列をディスクに保存** しなければならず、URL だけをユーザーに返してはいけません。URL の有効期限が切れた（`expired`）場合は、古いジョブを再ポーリングせず、新しい `create_download` ジョブを作成してください。

## インストール

詳細な手順は [`INSTALL.md`](INSTALL.md) を参照してください。または以下のプロンプトを AI クライアントに貼り付けてください:

```
https://github.com/SaveVideoKit/mcp.git から SaveVideoKit をインストールします。まず INSTALL.md と clients.json を読み、現在のクライアント（WorkBuddy / Codex / Claude Code / Cursor / opencode / dsh）を判定し、対応するスキルディレクトリと mcp/<client>.mcp.json のみをインストールしてください。既存の設定には上書きせずマージしてください。
```

## その他の言語
- [English](README.md)
- [中文 (Chinese)](README.zh-CN.md)
- [한국어 (Korean)](README.ko.md)
