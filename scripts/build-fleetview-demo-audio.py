#!/usr/bin/env python3
"""Build Personal Voice narration in timed sections for A/V sync.

Writes:
  docs/blog/assets/voice/sections/*.aiff
  docs/blog/assets/voice/narration-personal.aiff  (concat)
  docs/blog/assets/voice/timings.json            (ms per section)
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "scripts" / "fleetview-demo-sections.json"
VOICE_DIR = ROOT / "docs" / "blog" / "assets" / "voice"
SECT_DIR = VOICE_DIR / "sections"
OUT_AIFF = VOICE_DIR / "narration-personal.aiff"
TIMINGS = VOICE_DIR / "timings.json"
RATE = "165"  # slightly slower = clearer


def aiff_duration_sec(path: Path) -> float:
    # afinfo is reliable on macOS for AIFF
    r = subprocess.run(["afinfo", str(path)], capture_output=True, text=True)
    m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", r.stdout)
    if m:
        return float(m.group(1))
    # fallback via afconvert → wav
    wav = path.with_suffix(".wav")
    subprocess.check_call(
        ["afconvert", "-f", "WAVE", "-d", "LEI16", str(path), str(wav)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with wave.open(str(wav)) as w:
        return w.getnframes() / float(w.getframerate())


def main() -> None:
    sections = json.loads(SECTIONS.read_text(encoding="utf-8"))
    SECT_DIR.mkdir(parents=True, exist_ok=True)
    VOICE_DIR.mkdir(parents=True, exist_ok=True)

    timings = []
    aiffs = []
    for i, sec in enumerate(sections):
        sid = sec["id"]
        text = sec["text"].strip()
        out = SECT_DIR / f"{i:02d}-{sid}.aiff"
        print(f"say [{sid}] …")
        subprocess.check_call(
            ["say", "-v", "Personal Voice", "-r", RATE, "-o", str(out), text]
        )
        dur = aiff_duration_sec(out)
        # Small breath between sections (visual pause pad)
        pad_ms = 350 if i < len(sections) - 1 else 200
        timings.append(
            {
                "id": sid,
                "text": text,
                "audio_ms": int(round(dur * 1000)),
                "pad_ms": pad_ms,
                "total_ms": int(round(dur * 1000)) + pad_ms,
            }
        )
        aiffs.append(out)
        print(f"  {dur:.2f}s + {pad_ms}ms pad")

    # Concatenate with afconvert + ffmpeg silence pads
    import imageio_ffmpeg

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    list_file = SECT_DIR / "concat.txt"
    silence = SECT_DIR / "silence.wav"
    # 350ms silence at 22050 mono
    subprocess.check_call(
        [
            ff,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=22050:cl=mono",
            "-t",
            "0.35",
            str(silence),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    lines = []
    wav_parts = []
    for i, aiff in enumerate(aiffs):
        wav = aiff.with_suffix(".wav")
        subprocess.check_call(
            ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wav_parts.append(wav)
        lines.append(f"file '{wav}'")
        if i < len(aiffs) - 1:
            lines.append(f"file '{silence}'")
    list_file.write_text("\n".join(lines) + "\n")

    out_wav = VOICE_DIR / "narration-personal.wav"
    subprocess.check_call(
        [
            ff,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out_wav),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Keep AIFF for say-compat; also keep wav for mux
    subprocess.check_call(
        ["afconvert", "-f", "AIFF", "-d", "BEI16", str(out_wav), str(OUT_AIFF)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    total_ms = sum(t["total_ms"] for t in timings)
    payload = {"voice": "Personal Voice", "rate": int(RATE), "total_ms": total_ms, "sections": timings}
    TIMINGS.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUT_AIFF}")
    print(f"Wrote {TIMINGS} total={total_ms/1000:.1f}s")


if __name__ == "__main__":
    main()
