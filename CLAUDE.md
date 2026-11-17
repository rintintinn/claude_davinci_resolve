# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Workspace for editing videos (social-media reels) in **DaVinci Resolve Studio 21.2** driven by Claude Code via the **DaVinci Resolve MCP** server (user-scope, Blackmagic's bundled `ResolveMCP` binary). There is no application code; work happens through MCP tools plus local CLI tools.

## Layout

- `videos/` — source footage, rendered outputs, `.srt` captions. `videos/music/` — background music (record source + license when adding).
- Media files are git-ignored (see `.gitignore`); only text (captions, docs, scripts) is committed.
- Resolve project `Reel_20261117` holds timelines `Reel - clean cut` (2:52, fillers still in), `Reel - no fillers` (2:37, current full version → `reel_edited_nofillers.mp4`) and `Reel 60s - FB Story` (music on A2; fillers still in).

## Tools

- MCP: `run_script` (sandboxed Python, `resolve`/`project` pre-injected), `run_script_unsafe` (needs file I/O), `search_scripting_api` / `get_scripting_api` (API stubs — check these, the API is newer than training data), `get_image` (verify a timeline frame), `get_whats_new`.
- Local: `ffmpeg`/`ffprobe` and `whisper` (openai-whisper CLI) in `/opt/homebrew/bin`. Scratch work goes in the session scratchpad, not this folder.

## Scripts

- `scripts/analyze.sh <video> <out_dir> [lang=en]` → `audio.json` (whisper words), `transcript.txt` (`word@start-end`, read this to pick cuts), `silences.txt`.
- `scripts/find_fillers.py audio.wav fillers.json` (run with `/opt/homebrew/opt/openai-whisper/libexec/bin/python`) → um/uh/erm candidates via short prompted windows.
- `scripts/cut_list.py keep.json silences.txt segments.json [--fps 30] [--remove fillers.json]` → frame segments with pauses (and exact `--remove` ranges, widened 0.04s) removed. `keep.json` = `[[start_s, end_s], ...]` chosen from the transcript.
- `scripts/resolve_helpers.py` — load in MCP `run_script_unsafe` via `exec(open(".../scripts/resolve_helpers.py").read())`, then `build_timeline`, `auto_captions`, `replace_captions(tl, srt_path, fixes)`, `add_music`, `render`. `render` returns the job status after ~55s — re-poll `GetRenderJobStatus` for long timelines.

## Reel editing workflow (what worked)

1. **Transcribe** with word timestamps: `whisper audio.wav --model small --language en --word_timestamps True --output_format json`. Always force `--language` — auto-detect picked Malay for English speech (Malaysian accent) and produced a translated, useless transcript.
2. **Detect pauses**: `ffmpeg -i audio.wav -af silencedetect=noise=-33dB:d=0.3 -f null -`.
3. **Cut list**: hand-pick keep ranges from the transcript (drop fillers, repeats, false starts, mic checks), then subtract detected silences with ~0.08s padding each side; convert to source frames.
4. **Build timeline**: new timeline, then `MediaPool.AppendToTimeline([{mediaPoolItem, startFrame, endFrame}, ...])`.
5. **Noise**: `Timeline.SetVoiceIsolationState(1, {"isEnabled": True, "amount": 70})`.
6. **Captions**: `Timeline.CreateSubtitlesFromAudio({...})` is async — poll `GetCreateSubtitlesFromAudioStatus()` until `Complete`. Then fix text via SRT round-trip (below).
7. **Render** with `SubtitleFormat: "BurnIn"`; verify by grabbing frames with ffmpeg and re-transcribing the output audio.

## Filler words (um/uh/erm) — hard-won lessons

- Whisper **omits** disfluencies, so a plain transcript (and verifying with one) misses them entirely. Use `find_fillers.py`; it still misses some and returns zero-length/imprecise timings.
- Fillers hide inside "stretched" words (e.g. `am@4.46-5.88`). Place cut edges from a 40 ms RMS-dB profile of `audio.wav`: fillers are steady low hums (~-25…-38 dB) between dips; a loud blob (~-15 dB) is usually a real word.
- Ambiguous spots: transcribe the isolated slice (whisper on a 0.3–1.5 s window) to hear what is actually there. This exposed "erm, with–, without, without, you know" that both transcribers tidied into "without".
- Every cut round: build an audio-only preview with ffmpeg (`atrim`+`concat`, `-/filter_complex file`), then (a) re-run `find_fillers.py` and (b) diff a plain whisper transcript against the previous version to catch clipped words. Resolve's `CreateSubtitlesFromAudio` on the rebuilt timeline is a fast (~20 s) second opinion; `MediaPoolItem.GetTranscription()` gives source word timings.
- Final 2:37 cut used 34 filler cuts: `videos/reel_nofillers_fillers.json` (source seconds) → `videos/reel_nofillers_segments.json`.

## Resolve API gotchas (verified)

- `AppendToTimeline` `endFrame` is **exclusive**.
- `SetRenderSettings` fails **entirely** if any key/value is invalid (e.g. `VideoQuality: "High"` → use `0` for auto). Check its return value; a silent failure previously dropped subtitle burn-in.
- Subtitle text **cannot be edited** via API (`TimelineItem.SetName` returns False). Workaround: export items to `.srt` (fix text), delete subtitle items, `ImportMedia` the `.srt`, `AppendToTimeline` it at `tl.GetStartFrame()`.
- Default burned-in subtitle font is very large on 1080×1920: keep lines ≤ ~16 chars, two lines per caption (U+2028 line separator appears in item names after import — normal).
- Timeline start is frame 108000 (01:00:00:00); subtract `GetStartFrame()` for SRT times.
- `ProjectManager.SaveProject()` (not `Project.SaveProject`).
- Music: `AppendToTimeline` with `trackIndex: 2, mediaType: 2`; `item.SetProperty("AudioVolume", -20.0)`; `item.SetFades({"FadeIn": 15, "FadeOut": 45})`.
- Loudness: Resolve render landed at ~-22 LUFS; for social, normalize after render: `ffmpeg -i in.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:a aac -b:a 192k out.mp4`.

## Content notes

- Speaker's web app is **Oratocue** — `oratocue.web.app` (speech recognizers mishear it as "oratoq"/"oratoku"). Medical terms to check in captions: BPH, benign prostatic hyperplasia, nocturia.
- Facebook Story limit: 60s per segment.
- Use music only with a verified license; CC0 from Wikimedia Commons (check `extmetadata` LicenseShortName/AttributionRequired via the Commons API) worked well.
