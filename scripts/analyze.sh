#!/usr/bin/env bash
# Transcribe a video (word timestamps) and detect pauses.
# Usage: scripts/analyze.sh <video> <out_dir> [language=en]
# Outputs: <out_dir>/audio.wav, audio.json (whisper), silences.txt ("start end" per line, seconds)
set -euo pipefail
VIDEO="$1"; OUT="$2"; LANG_CODE="${3:-en}"
mkdir -p "$OUT"
ffmpeg -hide_banner -loglevel error -y -i "$VIDEO" -vn -ac 1 -ar 16000 "$OUT/audio.wav"
ffmpeg -hide_banner -i "$OUT/audio.wav" -af silencedetect=noise=-33dB:d=0.3 -f null - 2>&1 \
  | grep -oE "silence_(start|end): [0-9.]+" | awk '{print $2}' | paste - - > "$OUT/silences.txt"
# Always pass --language: auto-detect mislabels accented English.
whisper "$OUT/audio.wav" --model small --language "$LANG_CODE" --word_timestamps True \
  --output_format json --output_dir "$OUT" > /dev/null
python3 -c "
import json,sys
for s in json.load(open(sys.argv[1]))['segments']:
    print(f\"[{s['start']:.2f}-{s['end']:.2f}] \"+' '.join(f\"{w['word'].strip()}@{w['start']:.2f}-{w['end']:.2f}\" for w in s['words']))
" "$OUT/audio.json" > "$OUT/transcript.txt"
echo "Wrote $OUT/{audio.json,transcript.txt,silences.txt}"
