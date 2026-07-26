#!/usr/bin/env python3
"""Clone voice from a reference WAV (ElevenLabs IVC) and mux onto the FleetView demo.

Requires:
  export ELEVENLABS_API_KEY=...
  pip install elevenlabs imageio-ffmpeg

Instant Voice Cloning needs a paid ElevenLabs plan. On free tier this script fails at IVC;
use a stock voice fallback or upgrade for your cloned voice.

Usage:
  python3 scripts/narrate-fleetview-demo.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = ROOT / "docs" / "blog" / "assets" / "voice"
VIDEO = ROOT / "docs" / "blog" / "assets" / "agency-swarm-fleetview-demo.webm"
NARRATION = VOICE_DIR / "narration.txt"
REF = VOICE_DIR / "voice-ref-15s.wav"
OUT_VIDEO = ROOT / "docs" / "blog" / "assets" / "agency-swarm-fleetview-demo.webm"


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def main() -> int:
    key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")
    if not key:
        print("Missing ELEVENLABS_API_KEY. Export it, then re-run.", file=sys.stderr)
        return 2
    if not REF.is_file() or not NARRATION.is_file() or not VIDEO.is_file():
        print(f"Need {REF}, {NARRATION}, and {VIDEO}", file=sys.stderr)
        return 2

    text = NARRATION.read_text(encoding="utf-8").strip()
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import VoiceSettings
    except ImportError:
        print("pip install elevenlabs", file=sys.stderr)
        return 2

    client = ElevenLabs(api_key=key)
    print("Creating IVC voice from reference sample…")
    voice = client.voices.ivc.create(
        name="agency-swarm-demo-narrator",
        files=[str(REF)],
    )
    voice_id = getattr(voice, "voice_id", None) or getattr(voice, "voiceId", None) or (voice.get("voice_id") if isinstance(voice, dict) else None)
    if not voice_id:
        print(f"Unexpected IVC response: {voice!r}", file=sys.stderr)
        return 1
    print(f"Voice id: {voice_id}")

    print("Synthesizing narration…")
    audio_iter = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(stability=0.45, similarity_boost=0.85, style=0.2),
    )
    mp3 = VOICE_DIR / "narration.mp3"
    with mp3.open("wb") as f:
        for chunk in audio_iter:
            if chunk:
                f.write(chunk)
    print(f"Wrote {mp3}")

    ff = ffmpeg_exe()
    tmp = VOICE_DIR / "demo-with-audio.webm"
    # Replace any existing audio; keep video stream; shortest = trim to shorter stream
    cmd = [
        ff, "-y",
        "-i", str(VIDEO),
        "-i", str(mp3),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "libopus",
        "-shortest",
        str(tmp),
    ]
    print("Muxing…", " ".join(cmd))
    subprocess.check_call(cmd)
    tmp.replace(OUT_VIDEO)
    print(f"Updated {OUT_VIDEO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
