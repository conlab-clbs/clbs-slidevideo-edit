#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from PIL import Image


FPS = 30
WIDTH = 1920
HEIGHT = 1080
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac"}
SLIDE_EXTS = {".png", ".jpg", ".jpeg"}
PICTURE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
BROLL_EXTS = {".mp4", ".mov", ".m4v"}
TAG_RE = re.compile(
    r"[\[【]\s*(スライド|ピクチャー|ピクチャ|picture|bロール|Bロール|ビーロール|b-roll|B-Roll|カムリターン|cam\s*return)\s*(\d+)?\s*[\]】]",
    re.I,
)


@dataclass
class SlideBlock:
    number: int
    title: str
    hint: str
    text: str
    script_start: int = 0
    script_end: int = 0


@dataclass
class VisualEvent:
    type: str
    number: int | None
    label: str
    title: str
    script_pos: int
    path: str | None = None


@dataclass
class ScriptPlan:
    speech_text: str
    events: list[VisualEvent]


@dataclass
class CaptionBlock:
    text: str
    script_start: int
    script_end: int


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def find_ffmpeg() -> str:
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    path = shutil.which("ffmpeg")
    if path:
        return path
    fail("ffmpegが見つかりません。インストーラーを実行するか、ffmpegをインストールしてください。")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def pick_script(project_dir: Path, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = project_dir / path
        if path.exists():
            return path
        fail(f"台本ファイルが見つかりません: {path}")

    candidates = [
        project_dir / "script.md",
        project_dir / "script.txt",
        project_dir / "台本.md",
        project_dir / "台本.txt",
    ]
    candidates.extend(sorted(project_dir.glob("*台本*.md")))
    candidates.extend(sorted(project_dir.glob("*台本*.txt")))
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    fail("台本ファイルが見つかりません。script.md / script.txt / *台本*.md のいずれかを置いてください。")


def pick_dir(project_dir: Path, explicit: str | None, names: list[str], label: str) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = project_dir / path
        if path.exists() and path.is_dir():
            return path
        fail(f"{label}フォルダが見つかりません: {path}")

    for name in names:
        path = project_dir / name
        if path.exists() and path.is_dir():
            return path
    fail(f"{label}フォルダが見つかりません。候補: {', '.join(names)}")


def pick_pdf(project_dir: Path) -> Path | None:
    candidates = [
        project_dir / "slides.pdf",
        project_dir / "deck.pdf",
        project_dir / "スライド.pdf",
    ]
    candidates.extend(sorted(project_dir.glob("*.pdf")))
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def convert_pdf_to_slides(pdf_path: Path, slide_dir: Path) -> None:
    try:
        import fitz
    except ImportError:
        fail("PDFを画像化するにはPyMuPDFが必要です。`pip install PyMuPDF` を実行してください。")

    slide_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    if len(doc) == 0:
        fail(f"PDFにページがありません: {pdf_path}")

    print(f"Convert PDF to slide images: {pdf_path}")
    for index, page in enumerate(doc, start=1):
        out_path = slide_dir / f"slide_{index:03d}.png"
        if out_path.exists():
            continue
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pix.save(out_path)


def pick_slide_dir(project_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return pick_dir(project_dir, explicit, ["スライド", "slides", "Slides"], "スライド")

    for name in ["スライド", "slides", "Slides"]:
        path = project_dir / name
        if path.exists() and path.is_dir():
            return path

    pdf_path = pick_pdf(project_dir)
    if pdf_path:
        slide_dir = project_dir / "スライド"
        convert_pdf_to_slides(pdf_path, slide_dir)
        return slide_dir

    fail("スライドフォルダまたは slides.pdf が見つかりません。")


def pick_optional_dir(project_dir: Path, explicit: str | None, names: list[str]) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = project_dir / path
        if path.exists() and path.is_dir():
            return path
        fail(f"素材フォルダが見つかりません: {path}")

    for name in names:
        path = project_dir / name
        if path.exists() and path.is_dir():
            return path
    return None


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[\s　]+", "", text)
    text = re.sub(r"[「」『』“”\"'’‘、。，．・：:；;！？!?…—―ー\-〜~（）()\[\]【】<>＜＞/／&＆]", "", text)
    text = re.sub(r"[^0-9a-zぁ-んァ-ン一-龥]", "", text)
    return text


def normalize_tag_type(raw: str) -> str:
    key = unicodedata.normalize("NFKC", raw).lower().replace(" ", "")
    if "スライド" in key:
        return "slide"
    if "ピクチャ" in key or key == "picture":
        return "picture"
    if "bロール" in key or "ビーロール" in key or "b-roll" in key:
        return "broll"
    if "カムリターン" in key or "camreturn" in key:
        return "cam_return"
    fail(f"未対応のタグです: {raw}")


def strip_non_speech_lines(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---" or stripped.startswith("※"):
            continue
        if stripped.startswith("<") and stripped.endswith(">"):
            continue
        lines.append(stripped.strip("「」\""))
    return "\n".join(lines)


def parse_tagged_text(text: str, base_pos: int = 0) -> tuple[str, list[VisualEvent]]:
    speech_parts: list[str] = []
    events: list[VisualEvent] = []
    cursor = 0
    for match in TAG_RE.finditer(text):
        before = text[cursor:match.start()]
        speech_parts.append(before)
        current_text = "".join(speech_parts)
        tag_type = normalize_tag_type(match.group(1))
        number = int(match.group(2)) if match.group(2) else None
        events.append(
            VisualEvent(
                type=tag_type,
                number=number,
                label=match.group(0),
                title="",
                script_pos=base_pos + len(normalize_text(current_text)),
            )
        )
        cursor = match.end()
    speech_parts.append(text[cursor:])
    return "".join(speech_parts), events


def extract_quoted_text(block: str) -> str:
    quoted = re.findall(r"[「\"](.+?)[」\"]", block, flags=re.S)
    if quoted:
        return "\n".join(quoted)

    lines: list[str] = []
    for line in block.splitlines()[1:]:
        stripped = line.strip()
        if not stripped or stripped == "---" or stripped.startswith("※"):
            continue
        if stripped.startswith("<") and stripped.endswith(">"):
            continue
        lines.append(stripped.strip("「」\""))
    return "\n".join(lines)


def parse_script(script_path: Path, slide_dir: Path, picture_dir: Path | None, broll_dir: Path | None, project_dir: Path) -> ScriptPlan:
    text = script_path.read_text(encoding="utf-8")
    header_re = re.compile(r"^【スライド(\d+)】(.+?)ナレーション（約([^）]+)）\s*$", re.M)
    matches = list(header_re.finditer(text))
    events: list[VisualEvent] = []
    speech_parts: list[str] = []
    cursor = 0
    seen_slides = set()

    if matches:
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            raw_block = text[start:end]
            slide_number = int(match.group(1))
            title = match.group(2).strip()
            hint = match.group(3).strip()
            if slide_number in seen_slides:
                fail(f"スライド番号が重複しています: {slide_number}")
            seen_slides.add(slide_number)

            events.append(
                VisualEvent(
                    type="slide",
                    number=slide_number,
                    label=f"【スライド{slide_number}】",
                    title=title,
                    script_pos=cursor,
                )
            )
            body = strip_non_speech_lines("\n".join(raw_block.splitlines()[1:]))
            body_without_tags, inline_events = parse_tagged_text(body, cursor)
            for event in inline_events:
                if event.type == "slide" and event.number is None:
                    event.number = slide_number
                events.append(event)
            norm = normalize_text(body_without_tags)
            if not norm:
                fail(f"スライド{slide_number}のナレーション本文が空です。")
            speech_parts.append(body_without_tags)
            cursor += len(norm)
    else:
        clean_text = strip_non_speech_lines(text)
        body_without_tags, events = parse_tagged_text(clean_text, 0)
        speech_parts.append(body_without_tags)
        cursor = len(normalize_text(body_without_tags))
        if not events:
            fail("台本から `[スライドN]` / `[ピクチャーN]` / `[BロールN]` タグを検出できませんでした。")
        if not normalize_text(body_without_tags):
            fail("台本から照合可能なナレーション本文を検出できませんでした。")

    speech_text = "".join(speech_parts)
    validate_and_resolve_events(events, slide_dir, picture_dir, broll_dir, project_dir)
    return ScriptPlan(speech_text=speech_text, events=events)


def audio_files(audio_dir: Path) -> list[Path]:
    files = sorted([p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS])
    if not files:
        fail(f"音声ファイルが見つかりません: {audio_dir}")
    return files


def resolve_slide(slide_dir: Path, number: int) -> Path | None:
    stems = [
        f"slide_{number:03d}",
        f"slide-{number:03d}",
        f"slides_page-{number:04d}",
        f"slides_page-{number:03d}",
        f"{number:03d}",
    ]
    for stem in stems:
        for ext in SLIDE_EXTS:
            path = slide_dir / f"{stem}{ext}"
            if path.exists():
                return path
    return None


def resolve_picture(project_dir: Path, picture_dir: Path | None, number: int) -> Path | None:
    dirs = [p for p in [picture_dir, project_dir / "pictures", project_dir / "ピクチャー", project_dir / "画像", project_dir] if p and p.exists()]
    stems = [
        f"picture_{number:02d}",
        f"picture_{number:03d}",
        f"picture{number:02d}",
        f"picture{number}",
        f"image_{number:02d}",
        f"image_{number:03d}",
        f"image{number:02d}",
        f"image{number}",
    ]
    for directory in dirs:
        for stem in stems:
            for ext in PICTURE_EXTS:
                path = directory / f"{stem}{ext}"
                if path.exists():
                    return path
    return None


def resolve_broll(project_dir: Path, broll_dir: Path | None, number: int) -> Path | None:
    dirs = [p for p in [broll_dir, project_dir / "broll", project_dir / "brolls", project_dir / "Bロール", project_dir] if p and p.exists()]
    stems = [
        f"broll{number:02d}",
        f"broll{number}",
        f"broll_{number:02d}",
        f"broll_{number:03d}",
        f"b-roll{number:02d}",
        f"Bロール{number:02d}",
        f"Bロール{number}",
    ]
    for directory in dirs:
        for stem in stems:
            for ext in BROLL_EXTS:
                path = directory / f"{stem}{ext}"
                if path.exists():
                    return path
    return None


def validate_and_resolve_events(
    events: list[VisualEvent],
    slide_dir: Path,
    picture_dir: Path | None,
    broll_dir: Path | None,
    project_dir: Path,
) -> None:
    counters = {"slide": 0, "picture": 0, "broll": 0}
    for event in events:
        if event.type == "cam_return":
            continue
        counters[event.type] += 1
        if event.number is None:
            event.number = counters[event.type]

        if event.type == "slide":
            path = resolve_slide(slide_dir, event.number)
            if not path:
                fail(f"対応するスライド画像が見つかりません: slide_{event.number:03d}.png/.jpg")
        elif event.type == "picture":
            path = resolve_picture(project_dir, picture_dir, event.number)
            if not path:
                fail(f"対応するピクチャー画像が見つかりません: picture/image {event.number}")
        elif event.type == "broll":
            path = resolve_broll(project_dir, broll_dir, event.number)
            if not path:
                fail(f"対応するBロール動画が見つかりません: broll{event.number:02d}.mp4")
        else:
            fail(f"未対応のイベント種別です: {event.type}")
        event.path = str(path.resolve())


def duration_from_ffmpeg(ffmpeg: str, path: Path) -> float:
    proc = subprocess.run([ffmpeg, "-i", str(path)], text=True, capture_output=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not match:
        fail(f"音声/動画の長さを取得できません: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def concat_audio(ffmpeg: str, files: list[Path], out_path: Path) -> None:
    cmd = [ffmpeg, "-y"]
    for path in files:
        cmd.extend(["-i", str(path)])
    cmd.extend([
        "-filter_complex",
        f"concat=n={len(files)}:v=0:a=1[a]",
        "-map",
        "[a]",
        "-ar",
        "44100",
        "-ac",
        "1",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(out_path),
    ])
    run(cmd)


def make_black_video(ffmpeg: str, audio_path: Path, out_path: Path, total_duration: float) -> None:
    run([
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}:d={total_duration:.3f}",
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(out_path),
    ])


def transcribe(audio_path: Path, out_json: Path, model_name: str) -> dict:
    if out_json.exists():
        print(f"Reuse transcript: {out_json}")
        return json.loads(out_json.read_text(encoding="utf-8"))

    import whisper

    print(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)
    result = model.transcribe(
        str(audio_path),
        language="ja",
        fp16=False,
        verbose=False,
        condition_on_previous_text=True,
    )
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def transcript_char_times(result: dict) -> tuple[str, list[float]]:
    chars: list[str] = []
    times: list[float] = []
    last_time = 0.0
    for segment in result.get("segments", []):
        norm = normalize_text(segment.get("text", ""))
        if not norm:
            continue
        start = float(segment.get("start", last_time))
        end = float(segment.get("end", start))
        span = max(end - start, 0.001)
        count = len(norm)
        for idx, char in enumerate(norm):
            chars.append(char)
            times.append(start + span * (idx / max(count, 1)))
        last_time = end
    if not chars:
        fail("Whisper文字起こしから照合可能な文字列を作れませんでした。")
    return "".join(chars), times


def map_script_to_transcript(script_text: str, transcript_text: str) -> list[tuple[int, int]]:
    matcher = difflib.SequenceMatcher(None, script_text, transcript_text, autojunk=False)
    anchors: list[tuple[int, int]] = [(0, 0)]
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" and i2 > i1:
            anchors.append((i1, j1))
            anchors.append((i2, j2))
        elif tag == "replace" and i2 > i1 and j2 > j1:
            anchors.append((i1, j1))
            anchors.append((i2, j2))
    anchors.append((len(script_text), max(len(transcript_text) - 1, 0)))
    anchors = sorted(set(anchors))

    cleaned: list[tuple[int, int]] = []
    max_t = -1
    for script_i, transcript_i in anchors:
        transcript_i = max(transcript_i, max_t)
        transcript_i = min(transcript_i, max(len(transcript_text) - 1, 0))
        cleaned.append((script_i, transcript_i))
        max_t = transcript_i
    return cleaned


def interp(anchor_map: list[tuple[int, int]], script_pos: int) -> int:
    if script_pos <= anchor_map[0][0]:
        return anchor_map[0][1]
    for idx in range(1, len(anchor_map)):
        left_s, left_t = anchor_map[idx - 1]
        right_s, right_t = anchor_map[idx]
        if script_pos <= right_s:
            if right_s == left_s:
                return right_t
            ratio = (script_pos - left_s) / (right_s - left_s)
            return round(left_t + ratio * (right_t - left_t))
    return anchor_map[-1][1]


def split_caption_text(text: str, max_chars: int = 34, line_chars: int = 18) -> list[CaptionBlock]:
    blocks: list[CaptionBlock] = []
    norm_cursor = 0
    for line in text.splitlines():
        stripped = line.strip("「」\" \t")
        if not stripped:
            continue
        parts = re.findall(r"[^。！？!?]+[。！？!?]?", stripped)
        for part in parts or [stripped]:
            sentence = part.strip()
            if not sentence:
                continue
            chunks = chunk_caption_sentence(sentence, max_chars=max_chars)
            for chunk in chunks:
                norm = normalize_text(chunk)
                if not norm:
                    continue
                start = norm_cursor
                end = start + len(norm)
                blocks.append(CaptionBlock(text=format_caption_lines(chunk, line_chars), script_start=start, script_end=end))
                norm_cursor = end
    return blocks


def chunk_caption_sentence(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    chunks: list[str] = []
    rest = sentence
    while len(rest) > max_chars:
        split_at = max(rest.rfind("、", 0, max_chars + 1), rest.rfind(",", 0, max_chars + 1))
        if split_at < max_chars // 2:
            split_at = max_chars
        else:
            split_at += 1
        chunks.append(rest[:split_at].strip())
        rest = rest[split_at:].strip()
    if rest:
        chunks.append(rest)
    return chunks


def format_caption_lines(text: str, line_chars: int) -> str:
    text = text.strip()
    if len(text) <= line_chars:
        return text
    split_at = max(text.rfind("、", 0, line_chars + 1), text.rfind(",", 0, line_chars + 1))
    if split_at < max(6, line_chars // 2):
        split_at = min(line_chars, len(text))
    else:
        split_at += 1
    first = text[:split_at].strip()
    second = text[split_at:].strip()
    return f"{first}\n{second}" if second else first


def build_caption_timings(
    caption_blocks: list[CaptionBlock],
    script_text: str,
    transcript_text: str,
    transcript_times: list[float],
    total_duration: float,
) -> list[dict]:
    anchor_map = map_script_to_transcript(script_text, transcript_text)
    captions: list[dict] = []
    for block in caption_blocks:
        start_idx = interp(anchor_map, block.script_start)
        end_idx = interp(anchor_map, max(block.script_end - 1, block.script_start))
        start = transcript_times[min(max(start_idx, 0), len(transcript_times) - 1)]
        end = transcript_times[min(max(end_idx, 0), len(transcript_times) - 1)]
        captions.append({"text": block.text, "start": round(max(0.0, start), 3), "end": round(min(total_duration, max(end, start + 0.8)), 3)})

    for idx, caption in enumerate(captions):
        if idx + 1 < len(captions):
            next_start = captions[idx + 1]["start"]
            caption["end"] = round(min(caption["end"], max(caption["start"] + 0.5, next_start - 0.05)), 3)
        if caption["end"] <= caption["start"]:
            caption["end"] = round(min(total_duration, caption["start"] + 0.8), 3)
    return captions


def format_srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis -= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(captions: list[dict], out_path: Path) -> None:
    lines: list[str] = []
    for idx, caption in enumerate(captions, start=1):
        lines.append(str(idx))
        lines.append(f"{format_srt_time(caption['start'])} --> {format_srt_time(caption['end'])}")
        lines.append(caption["text"])
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_timings(
    events: list[VisualEvent],
    script_text: str,
    transcript_text: str,
    transcript_times: list[float],
    total_duration: float,
) -> list[dict]:
    anchor_map = map_script_to_transcript(script_text, transcript_text)
    timings: list[dict] = []
    last_start = 0.0
    for event in events:
        start_idx = interp(anchor_map, event.script_pos)
        start = transcript_times[min(max(start_idx, 0), len(transcript_times) - 1)]
        start = max(start, last_start)
        if event.type == "slide" and not any(t["type"] == "slide" for t in timings):
            start = 0.0
        item = {
            "type": event.type,
            "number": event.number,
            "label": event.label,
            "title": event.title,
            "start": round(min(start, total_duration), 3),
            "path": event.path,
        }
        timings.append(item)
        last_start = item["start"]

    for idx, item in enumerate(timings):
        if item["type"] == "cam_return":
            continue
        end = total_duration
        for next_item in timings[idx + 1:]:
            if item["type"] == "slide":
                if next_item["type"] == "slide":
                    end = next_item["start"]
                    break
            elif next_item["type"] in ("cam_return", "slide", "picture", "broll"):
                end = next_item["start"]
                break
        end = min(max(end, item["start"] + 0.5), total_duration)
        item["end"] = round(end, 3)
        item["duration"] = round(item["end"] - item["start"], 3)
    return timings


def pathurl(path: Path) -> str:
    return "file://localhost" + quote(str(path.resolve()))


def rate_xml() -> str:
    return f"<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>"


def motion_filter(scale: float = 100.0, pos_x: int = WIDTH // 2, pos_y: int = HEIGHT // 2) -> str:
    return f"""
            <filter>
              <effect>
                <name>motion</name>
                <effectid>motion</effectid>
                <effectcategory>motion</effectcategory>
                <effecttype>motion</effecttype>
                <mediatype>video</mediatype>
                <parameter authoringApp="PremierePro">
                  <parameterid>position</parameterid>
                  <name>Position</name>
                  <value><horiz>{pos_x}</horiz><vert>{pos_y}</vert></value>
                </parameter>
                <parameter authoringApp="PremierePro">
                  <parameterid>scale</parameterid>
                  <name>Scale</name>
                  <value>{scale:.2f}</value>
                </parameter>
                <parameter authoringApp="PremierePro">
                  <parameterid>scaleLinkedToWidth</parameterid>
                  <name>Uniform Scale</name>
                  <value>TRUE</value>
                </parameter>
              </effect>
            </filter>"""


def media_track(items: list[str]) -> str:
    return "\n        <track>\n          <enabled>TRUE</enabled>\n" + "\n".join(items) + "\n        </track>"


def image_clipitem(item: dict, track: str, index: int) -> str:
    start = round(item["start"] * FPS)
    end = max(round(item["end"] * FPS), start + 1)
    duration = end - start
    media_path = Path(item["path"])
    with Image.open(media_path) as image:
        width, height = image.size
    scale = min(WIDTH / width, HEIGHT / height) * 100
    return f"""
          <clipitem id="clipitem-{track}-{index:03d}">
            <name>{html.escape(media_path.name)}</name>
            <duration>{duration}</duration>
            {rate_xml()}
            <in>0</in><out>{duration}</out><start>{start}</start><end>{end}</end>
            <file id="file-{track}-{index:03d}">
              <name>{html.escape(media_path.name)}</name>
              <pathurl>{pathurl(media_path)}</pathurl>
              <media><video><samplecharacteristics><width>{width}</width><height>{height}</height><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></video></media>
            </file>{motion_filter(scale=scale)}
          </clipitem>"""


def broll_clipitem(ffmpeg: str, item: dict, index: int) -> str:
    start = round(item["start"] * FPS)
    end = max(round(item["end"] * FPS), start + 1)
    duration = end - start
    media_path = Path(item["path"])
    try:
        actual_frames = max(round(duration_from_ffmpeg(ffmpeg, media_path) * FPS), 1)
        out_frame = min(duration, actual_frames)
        end = start + out_frame
        duration = out_frame
    except SystemExit:
        out_frame = duration
    return f"""
          <clipitem id="clipitem-v4-{index:03d}">
            <name>{html.escape(media_path.name)}</name>
            <duration>{duration}</duration>
            {rate_xml()}
            <in>0</in><out>{out_frame}</out><start>{start}</start><end>{end}</end>
            <file id="file-v4-{index:03d}">
              <name>{html.escape(media_path.name)}</name>
              <pathurl>{pathurl(media_path)}</pathurl>
              <media><video><samplecharacteristics><width>{WIDTH}</width><height>{HEIGHT}</height><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></video></media>
            </file>{motion_filter()}
          </clipitem>"""


def generate_xml(timings: list[dict], video_path: Path, out_path: Path, total_duration: float, ffmpeg: str) -> None:
    total_frames = math.ceil(total_duration * FPS)
    main_url = pathurl(video_path)
    video_track = f"""
        <track>
          <enabled>TRUE</enabled>
          <clipitem id="clipitem-v1-main">
            <name>{html.escape(video_path.name)}</name>
            <duration>{total_frames}</duration>
            {rate_xml()}
            <in>0</in><out>{total_frames}</out><start>0</start><end>{total_frames}</end>
            <file id="file-main-video">
              <name>{html.escape(video_path.name)}</name>
              <pathurl>{main_url}</pathurl>
              <media>
                <video><samplecharacteristics><width>{WIDTH}</width><height>{HEIGHT}</height><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></video>
                <audio><samplecharacteristics><depth>16</depth><samplerate>44100</samplerate></samplecharacteristics><channelcount>1</channelcount></audio>
              </media>
            </file>
          </clipitem>
        </track>"""

    picture_items = [image_clipitem(item, "v2", idx) for idx, item in enumerate(timings, start=1) if item["type"] == "picture"]
    slide_items = [image_clipitem(item, "v3", idx) for idx, item in enumerate(timings, start=1) if item["type"] == "slide"]
    broll_items = [broll_clipitem(ffmpeg, item, idx) for idx, item in enumerate(timings, start=1) if item["type"] == "broll"]

    audio_track = f"""
      <audio>
        <track>
          <enabled>TRUE</enabled>
          <clipitem id="clipitem-a1-main">
            <name>{html.escape(video_path.name)}</name>
            <duration>{total_frames}</duration>
            {rate_xml()}
            <in>0</in><out>{total_frames}</out><start>0</start><end>{total_frames}</end>
            <file id="file-main-audio">
              <name>{html.escape(video_path.name)}</name>
              <pathurl>{main_url}</pathurl>
              <media><audio><samplecharacteristics><depth>16</depth><samplerate>44100</samplerate></samplecharacteristics><channelcount>1</channelcount></audio></media>
            </file>
            <sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>
          </clipitem>
        </track>
      </audio>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
  <sequence>
    <name>clbs-slidevideo-edit</name>
    <duration>{total_frames}</duration>
    {rate_xml()}
    <media>
      <video>
        <format><samplecharacteristics><width>{WIDTH}</width><height>{HEIGHT}</height><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>
{video_track}
{media_track(slide_items)}
{media_track(picture_items)}
{media_track(broll_items)}
      </video>
{audio_track}
    </media>
  </sequence>
</xmeml>
"""
    out_path.write_text(xml, encoding="utf-8")


def write_concat_list(timings: list[dict], out_path: Path) -> None:
    lines: list[str] = []
    render_items = [item for item in timings if item["type"] in ("slide", "picture")]
    if not render_items:
        fail("確認用MP4を作るためのスライド/ピクチャー画像イベントがありません。")
    for item in render_items:
        lines.append(f"file '{Path(item['path']).as_posix()}'")
        lines.append(f"duration {item['duration']:.6f}")
    lines.append(f"file '{Path(render_items[-1]['path']).as_posix()}'")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_final_mp4(ffmpeg: str, concat_list: Path, audio_path: Path, out_path: Path) -> None:
    vf = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    run([
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-i",
        str(audio_path),
        "-vf",
        vf,
        "-r",
        str(FPS),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(out_path),
    ])


def write_report(timings: list[dict], durations: list[tuple[str, float]], out_path: Path) -> None:
    lines = ["# Visual Timing Report", "", "## Audio Durations", ""]
    total = 0.0
    for name, seconds in durations:
        total += seconds
        lines.append(f"- {name}: {seconds:.2f}s ({seconds / 60:.2f} min)")
    lines.append(f"- TOTAL: {total:.2f}s ({total / 60:.2f} min)")
    lines.extend(["", "## Visual Timings", ""])
    for item in timings:
        if item["type"] == "cam_return":
            lines.append(f"- Cam Return: {item['start']:.2f}s")
            continue
        name = f"{item['type']} {item['number']:03d}" if item.get("number") else item["type"]
        lines.append(f"- {name}: {item['start']:.2f}s -> {item['end']:.2f}s ({item['duration']:.2f}s) | {Path(item['path']).name}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build VSL video and Premiere XML from narration audio and visual tags.")
    parser.add_argument("project_dir", help="素材フォルダ")
    parser.add_argument("--script", help="台本ファイル名またはパス")
    parser.add_argument("--audio-dir", help="音声フォルダ名またはパス")
    parser.add_argument("--slide-dir", help="スライドフォルダ名またはパス")
    parser.add_argument("--picture-dir", help="ピクチャー画像フォルダ名またはパス")
    parser.add_argument("--broll-dir", help="Bロール動画フォルダ名またはパス")
    parser.add_argument("--model", default="base", help="Whisper model name. default: base")
    parser.add_argument("--skip-render", action="store_true", help="完成MP4レンダーをスキップ")
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.exists():
        fail(f"素材フォルダが見つかりません: {project_dir}")

    ffmpeg = find_ffmpeg()
    script_path = pick_script(project_dir, args.script)
    audio_dir = pick_dir(project_dir, args.audio_dir, ["音声", "audio", "Audio"], "音声")
    slide_dir = pick_slide_dir(project_dir, args.slide_dir)
    picture_dir = pick_optional_dir(project_dir, args.picture_dir, ["ピクチャー", "pictures", "Pictures", "画像", "images"])
    broll_dir = pick_optional_dir(project_dir, args.broll_dir, ["Bロール", "broll", "brolls", "Broll"])

    plan = parse_script(script_path, slide_dir, picture_dir, broll_dir, project_dir)
    files = audio_files(audio_dir)
    durations = [(path.name, duration_from_ffmpeg(ffmpeg, path)) for path in files]
    total_duration = sum(seconds for _, seconds in durations)

    combined_audio = project_dir / "combined_audio.m4a"
    video_mp4 = project_dir / "video.mp4"
    transcript_json = project_dir / "webinar_transcript.json"
    timing_json = project_dir / "slide_timing_plan.json"
    report_md = project_dir / "slide_timing_report.md"
    telop_source_srt = project_dir / "telop_source.srt"
    telop_jetcut_srt = project_dir / "telop_jetcut.srt"
    telop_json = project_dir / "telop_timing.json"
    concat_list = project_dir / "slides_concat.txt"
    xml_path = project_dir / "project_premiere.xml"
    final_mp4 = project_dir / "slidevideo_final.mp4"

    concat_audio(ffmpeg, files, combined_audio)
    make_black_video(ffmpeg, combined_audio, video_mp4, total_duration)

    result = transcribe(combined_audio, transcript_json, args.model)
    transcript_text, transcript_times = transcript_char_times(result)
    normalized_script = normalize_text(plan.speech_text)
    timings = build_timings(plan.events, normalized_script, transcript_text, transcript_times, total_duration)
    caption_blocks = split_caption_text(plan.speech_text)
    captions = build_caption_timings(caption_blocks, normalized_script, transcript_text, transcript_times, total_duration)

    timing_json.write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding="utf-8")
    telop_json.write_text(json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8")
    write_srt(captions, telop_source_srt)
    write_srt(captions, telop_jetcut_srt)
    write_report(timings, durations, report_md)
    generate_xml(timings, video_mp4, xml_path, total_duration, ffmpeg)

    if not args.skip_render:
        if any(item["type"] in ("picture", "broll") for item in timings):
            print("ピクチャー/Bロールを含むため、確認用MP4は簡易レンダーをスキップします。Premiere XMLで確認してください。")
        else:
            write_concat_list(timings, concat_list)
            render_final_mp4(ffmpeg, concat_list, combined_audio, final_mp4)

    print("\nDone:")
    done_paths = [combined_audio, video_mp4, xml_path, telop_source_srt, telop_jetcut_srt, timing_json, telop_json, report_md]
    if final_mp4.exists():
        done_paths.insert(3, final_mp4)
    for path in done_paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
