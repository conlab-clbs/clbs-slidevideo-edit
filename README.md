# clbs-slidevideo-edit

CLBS受講生向けの、タグを発音しない音声用の動画編集スキルです。

台本上の `[スライドN]` / `[ピクチャーN]` / `[BロールN]` / `[カムリターン]` を、完成音声の読み上げ内容と照合し、Premiere Pro用XML、テロップSRT、タイミング表を生成します。

## AIエージェントに貼る導入文

受講生は、CodexまたはClaude Codeに次を貼ってください。

```text
このGitHubリポジトリから clbs-slidevideo-edit を導入してください。

https://github.com/conlab-clbs/clbs-slidevideo-edit

私の環境がCodexかClaude Codeかを確認して、適切なskillsフォルダにインストールしてください。
Codexなら ~/.codex/skills/clbs-slidevideo-edit、
Claude Codeなら ~/.claude/skills/clbs-slidevideo-edit に入れてください。

既存版がある場合は上書きしてください。
必要なPython依存関係とffmpegも確認してください。
インストール後、CodexまたはClaude Codeを再起動する必要があることを案内してください。
```

## 手動インストール

このリポジトリをダウンロードまたはcloneしたあと、リポジトリ直下で次を実行します。

```bash
python3 install.py --target codex
```

Claude Codeに入れる場合:

```bash
python3 install.py --target claude
```

両方に入れる場合:

```bash
python3 install.py --target both
```

## 対応タグ

| タグ | 対応素材例 |
|---|---|
| `[スライド1]` | `スライド/slide_001.png` |
| `[ピクチャー1]` | `pictures/picture_01.png` または `image01.png` |
| `[Bロール1]` | `broll/broll01.mp4` |
| `[カムリターン]` | 直前のピクチャー/Bロール表示を終了 |

タグは音声に読ませません。完成音声にはナレーション本文だけを入れてください。

## 主な出力

| ファイル | 内容 |
|---|---|
| `project_premiere.xml` | Premiere Pro用XML |
| `telop_source.srt` | テロップSRT |
| `telop_jetcut.srt` | 互換用テロップSRT |
| `telop_timing.json` | テロップタイミング |
| `slide_timing_plan.json` | ビジュアル素材タイミング |
| `slide_timing_report.md` | 確認用レポート |
| `slidevideo_final.mp4` | スライドのみの場合の確認用MP4 |

## 素材フォルダ例

```text
素材フォルダ/
├── script.md
├── 音声/
│   ├── 01.mp3
│   └── 02.mp3
├── スライド/
│   ├── slide_001.png
│   └── slide_002.png
├── pictures/
│   └── picture_01.png
└── broll/
    └── broll01.mp4
```

## 依存関係

- Python 3
- ffmpeg
- Pythonパッケージ: `openai-whisper`, `Pillow`, `PyMuPDF`

インストールスクリプトは、Pythonパッケージの導入を試みます。ffmpegがない場合は、MacならHomebrew、Windowsならwingetなどで入れてください。
