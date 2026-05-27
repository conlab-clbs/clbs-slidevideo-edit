---
name: clbs-slidevideo-edit
description: タグを発音しない音声とビジュアルタグ付き台本から、音声結合、Whisper文字起こし、台本照合、スライド・ピクチャー・Bロールのタイミング推定、テロップSRT生成、Premiere Pro XML、確認用MP4を書き出すVSL・ウェビナー・講座動画編集スキル。スライドだけで遷移する動画、VSL動画、ウェビナー動画、タグなし音声、Premiere XML、SRT生成、テロップ生成、音声に合わせてスライド/Bロール/ピクチャー配置、などの依頼で使用する。
---

# clbs-slidevideo-edit

タグを発音しない完成音声に、台本上の `[スライドN]` / `[ピクチャーN]` / `[BロールN]` / `[カムリターン]` 割り振りを照合して、Premiere Pro用タイムラインを作る。

通常の `clbs-video-edit` と違い、音声内に `[スライドN]` や `[カムリターン]` の発話が入っていない前提。Silero VADの無音検出ではなく、Whisper文字起こしと台本本文の文字列照合を主軸にする。

## 入力フォルダ

ユーザーが指定した素材フォルダに、次の構成があることを確認する。

```text
素材フォルダ/
├── script.md または script.txt または *台本*.md
├── 音声/ または audio/
│   ├── 01.mp3
│   ├── 02.mp3
│   └── ...
├── slides.pdf または deck.pdf
├── スライド/ または slides/
│   ├── slide_001.png
│   ├── slide_002.png
│   └── ...
├── pictures/ または ピクチャー/ または 画像/  # 任意
│   ├── picture_01.png または image01.png
│   └── ...
└── broll/ または Bロール/                 # 任意
    ├── broll01.mp4
    └── ...
```

台本は次のようなブロックを基本形にする。

```text
[スライド1]
ここに実際に読まれるナレーション本文。

[ピクチャー1]
ここで画像を見せながら説明する本文。

[カムリターン]
[Bロール1]
ここでBロール動画を見せながら説明する本文。

[カムリターン]

---
```

従来の `【スライド1】タイトル ナレーション（約20秒）` ブロック形式も引き続き対応する。

## 実行手順

1. 素材フォルダを確認する。
2. `scripts/build_slidevideo.py` を素材フォルダに対して実行する。
3. 出力物を確認する。
4. `slide_timing_report.md` を見て、極端に短いスライドやズレがないか確認する。

実行例:

```bash
python3 /path/to/clbs-slidevideo-edit/scripts/build_slidevideo.py "/path/to/素材フォルダ"
```

Whisperモデルを変えたい場合:

```bash
python3 /path/to/clbs-slidevideo-edit/scripts/build_slidevideo.py "/path/to/素材フォルダ" --model small
```

## 出力

素材フォルダ内に以下を作成する。

```text
combined_audio.m4a          # 音声を順番に結合したもの
video.mp4                   # 黒画面 + 結合音声
project_premiere.xml        # Premiere Pro用 XMEML
slidevideo_final.mp4        # スライドのみの場合の確認用MP4
slide_timing_plan.json      # 機械可読のタイミング表
slide_timing_report.md      # 人間が確認するタイミング表
webinar_transcript.json     # Whisper文字起こし結果
telop_source.srt            # テロップSRT（元音声タイムライン）
telop_jetcut.srt            # テロップSRT（互換用。ジェットカットなしのためsourceと同じ）
telop_timing.json           # テロップタイミングJSON
slides_concat.txt           # MP4レンダー用中間ファイル
```

## 判断ルール

- 音声ファイルはファイル名順に結合する。`01`, `02`, `03` のような番号を付けるよう促す。
- スライドは `slide_001.png` / `slide_001.jpg` のような3桁連番を優先する。
- 画像フォルダがなく、`slides.pdf` / `deck.pdf` だけがある場合は、自動で `スライド/slide_001.png` 形式に画像化する。
- ピクチャーは `picture_01.png` / `image01.png` などを番号で拾う。
- Bロールは `broll01.mp4` / `broll1.mp4` などを番号で拾う。
- `[カムリターン]` は直前のピクチャー/Bロール表示を終了する。スライドは次の `[スライドN]` まで継続する。
- 台本と音声内容が大きく違う場合は、予想で補正せず、`slide_timing_report.md` を見せてユーザーに確認する。
- テロップはタグを除いた台本本文を正として使い、Whisper文字起こしのタイミングに合わせて `telop_source.srt` / `telop_jetcut.srt` を出す。
- Premiere XMLは30fps、1920x1080、V1に黒画面動画、上位トラックにスライド/ピクチャー/Bロール、A1に音声を置く。
- ピクチャー/Bロールを含む場合、最終確認はPremiere Pro XMLで行う。スライドのみの場合は確認用MP4も出す。

## 必要な依存関係

- Python 3
- ffmpeg
- Pythonパッケージ: `openai-whisper`, `Pillow`, `PyMuPDF`

依存関係が足りない場合は、インストーラーを案内するか、次を実行する。

```bash
pip3 install --upgrade openai-whisper Pillow PyMuPDF
```
