# SaveVideoKit

**SaveVideoKit 원격 MCP 서비스**를 통해 공개 동영상(YouTube, TikTok, Instagram, Facebook, X/Twitter, Reddit, Vimeo, Dailymotion)을 다운로드 / 확인합니다. API 키가 필요 없습니다. 소스가 직접 다운로드 가능한 파일을 제공하면 다운로드는 **소스 CDN의 원본 URL로 바로** 이루어집니다(서버 측 다운로드·병합·저장 없음). 이 저장소는 스킬과 MCP 연동 설정을 멀티 클라이언트 구조로 정리하여 WorkBuddy, Codex, Claude Code, Cursor, opencode, dsh 등 다양한 클라이언트에서 재사용·확장할 수 있습니다.

## 저장소 구조

```
SaveVideoKit/
├── README.md                 # 이 파일의 한국어 버전
├── INSTALL.md                # 에이전트용 설치 가이드(클라이언트 판별 → 해당 파일 설치)
├── clients.json              # 기계 판독용: 클라이언트 → 스킬 디렉터리 + MCP 설정 매핑
├── workbuddy/                # ★ 정식 소스(canonical): WorkBuddy 스킬
│   ├── SKILL.md
│   ├── references/constraints.md
│   └── scripts/download_file.py
├── codex/                    # Codex 스킬(스캐폴드)
├── claude-code/              # Claude Code 스킬(스캐폴드)
├── cursor/                   # Cursor 규칙(.cursor/rules) + scripts + references
│   └── rules/savevideokit.mdc
├── opencode/                 # opencode 스킬(SKILL.md)
├── dsh/                      # dsh 스킬(스캐폴드)
├── mcp/                      # 클라이언트별 MCP 설정 스니펫 + setup.sh
│   ├── setup.sh              # workbuddy|codex|claude-code|cursor|opencode|dsh|all
│   ├── workbuddy.mcp.json
│   ├── codex.mcp.json
│   ├── claude-code.mcp.json
│   ├── cursor.mcp.json
│   ├── opencode.mcp.json
│   └── dsh.mcp.json
└── cli/                      # ★ 독립형 MCP 클라이언트(의존성 없음, MCP 프로토콜을 직접 구사)
    └── savevideokit_cli.py  # inspect→직접 다운로드(우선) 또는 작업→저장, 단독 실행 가능
```

- `workbuddy/`가 **유일한 정식 소스**이며, 다른 클라이언트 디렉터리는 이를 각 클라이언트 형식에 맞게 미러한 것입니다(Cursor는 `SKILL.md` 대신 `.mdc` 규칙 사용).
- 스킬 로직을 추가·수정할 때는 먼저 `workbuddy/`에서 작업한 뒤 다른 클라이언트 디렉터리로 동기화하세요.
- **에이전트 자동 설치**: `clients.json`과 `INSTALL.md`를 읽고 현재 클라이언트를 판별해 해당 파일만 설치합니다.

## 빠른 시작(WorkBuddy 예시)

```bash
# 1) MCP 서버 등록(~/.workbuddy/mcp.json 작성)
bash mcp/setup.sh workbuddy

# 2) 스킬 설치: workbuddy/를 WorkBuddy 사용자 수준 스킬로 복사
cp -r workbuddy ~/.workbuddy/skills/savevideokit
```

기타 클라이언트는 각 디렉터리의 `README.md`를 참고하세요.

## 독립형 MCP 클라이언트(cli/, 클라이언트 없이 사용 가능)

`cli/savevideokit_cli.py`는 **의존성 없는**(Python 표준 라이브러리만 사용) MCP Streamable HTTP 클라이언트입니다. 별도의 클라이언트 측 MCP 연동 없이도 스스로 전체 흐름을 수행합니다: `initialize` 핸드셰이크 → `inspect_video` → **직접 옵션이 있으면 직접 다운로드**(없으면 `create_download` + 폴링으로 폴백) → 로컬 저장. 명령줄에서 직접 사용하거나, 아직 MCP를 연동하지 않은 클라이언트의 하위 도구로 적합합니다.

```bash
# 동영상 메타데이터만 확인
python3 cli/savevideokit_cli.py --inspect-only "https://www.youtube.com/watch?v=xxxx"

# 전체 흐름: 확인 + 다운로드(가능하면 소스 CDN에서 직접) → ./downloads
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456"
python3 cli/savevideokit_cli.py "https://youtu.be/xxxx" --quality 1080p

# 직접 옵션이 있어도 create_download 작업 경로를 강제
python3 cli/savevideokit_cli.py "https://www.tiktok.com/@user/video/123456" --no-direct

# 지원 플랫폼 목록 보기
python3 cli/savevideokit_cli.py --list-sites
```

> `scripts/download_file.py`와의 역할 분담: `savevideokit_cli.py`는 "MCP 프로토콜을 구사하며 전체 흐름을 실행"하고, `download_file.py`는 "download_url을 받은 후 바이트를 디스크에 저장"하는 단계만 담당합니다. 둘은 독립적으로 사용할 수 있습니다.

## 핵심 다운로드 로직(반드시 유지)

**직접 다운로드 우선, 작업은 폴백.** `inspect_video`는 `direct_download_available` / `direct_options[]`를 반환하며, 그 `download_url`은 `302`로 **소스 CDN의 원본 미디어 URL**로 리디렉션됩니다. 서버 측 다운로드·병합·저장이 전혀 없으므로 최적 옵션을 곧바로 저장하면 끝입니다(`create_download`도, 폴링도, 보관 기한도 없음).

직접 옵션이 없을 때만 폴백합니다: `create_download` → `get_download_status` 폴링 → 반환된 `download_url`은 **서버 생성 파일이며 30분간 보관**(`file_retention_seconds = 1800`). 어느 경로든 MCP는 디스크에 쓰지 않으므로 워크플로는 **반드시 `scripts/download_file.py`로 바이트를 저장**해야 하며, URL만 사용자에게 돌려주어서는 안 됩니다. 링크가 만료되면(작업은 `expired`, 직접 링크는 `403/404`) 새 `create_download` 작업 또는 `inspect_video` 재실행으로 다시 받으세요.

## 설치

전체 절차는 [`INSTALL.md`](INSTALL.md)를 참고하세요. 또는 아래 프롬프트를 AI 클라이언트에 붙여넣으세요:

```
https://github.com/SaveVideoKit/mcp.git 에서 SaveVideoKit을 설치하세요. 먼저 INSTALL.md와 clients.json을 읽고, 현재 클라이언트(WorkBuddy / Codex / Claude Code / Cursor / opencode / dsh)를 판별해 해당 스킬 디렉터리와 mcp/<client>.mcp.json만 설치하세요. 기존 설정은 덮어쓰지 말고 병합하세요.
```

## 다른 언어
- [English](README.md)
- [中文 (Chinese)](README.zh-CN.md)
- [日本語 (Japanese)](README.ja.md)
