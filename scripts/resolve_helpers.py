"""Resolve-side helpers. Load inside the MCP `run_script_unsafe` tool:

    exec(open("/Users/badrul/claude_davinci_resolve/scripts/resolve_helpers.py").read())
    tl = build_timeline("My Reel", "lv_0_...mp4", "/path/segments.json")

`resolve` is pre-injected by the MCP tool.
"""
import json, time


def _project():
    return resolve.GetProjectManager().GetCurrentProject()


def build_timeline(name, clip_name, segments_path, voice_isolation=70):
    """New timeline from [[start, end), ...] source frames; enables Voice Isolation on A1."""
    p = _project(); mp = p.GetMediaPool()
    clip = next(c for c in mp.GetRootFolder().GetClipList() if c.GetName() == clip_name)
    segs = json.load(open(segments_path))
    tl = mp.CreateEmptyTimeline(name)
    p.SetCurrentTimeline(tl)
    mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": a, "endFrame": b} for a, b in segs])
    tl.SetVoiceIsolationState(1, {"isEnabled": True, "amount": voice_isolation})
    return tl


def auto_captions(tl, chars_per_line=24, timeout_s=55):
    """Run Resolve auto-captions and wait; returns subtitle item names."""
    tl.CreateSubtitlesFromAudio({"language": resolve.AUTO_CAPTION_ENGLISH, "charsPerLine": chars_per_line,
                                 "lineBreak": resolve.AUTO_CAPTION_LINE_SINGLE, "gap": 0})
    p = _project(); t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(3)
        if tl.GetTrackCount("subtitle") and p.GetCreateSubtitlesFromAudioStatus().get("JobStatus") == "Complete":
            break
    return [s.GetName() for s in tl.GetItemListInTrack("subtitle", 1) or []]


def _split(text, max_len=14):
    w = text.split()
    if len(text) <= max_len or len(w) < 2:
        return text
    k = min(range(1, len(w)), key=lambda k: max(len(" ".join(w[:k])), len(" ".join(w[k:]))))
    return " ".join(w[:k]) + "\n" + " ".join(w[k:])


def replace_captions(tl, srt_path, fixes=None):
    """Subtitle text isn't editable via API: export to SRT with fixes + 2-line split, re-import, replace."""
    fixes = fixes or {}
    p = _project(); mp = p.GetMediaPool()
    fps = float(p.GetSetting("timelineFrameRate")); t0 = tl.GetStartFrame()

    def tc(f):
        ms = round(f * 1000 / fps); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    subs = tl.GetItemListInTrack("subtitle", 1)
    srt = "\n".join(f"{i}\n{tc(s.GetStart() - t0)} --> {tc(s.GetEnd() - t0)}\n{_split(fixes.get(s.GetName(), s.GetName()))}\n"
                    for i, s in enumerate(subs, 1))
    open(srt_path, "w").write(srt)
    tl.DeleteClips(subs)
    clip = mp.ImportMedia([srt_path])[0]
    mp.AppendToTimeline([{"mediaPoolItem": clip, "recordFrame": t0}])
    return len(tl.GetItemListInTrack("subtitle", 1))


def add_music(tl, music_path, volume_db=-20.0, fade_in=15, fade_out=45):
    """Music bed on A2, trimmed to timeline length."""
    mp = _project().GetMediaPool()
    clip = mp.ImportMedia([music_path])[0]
    if tl.GetTrackCount("audio") < 2:
        tl.AddTrack("audio", "stereo")
    length = tl.GetEndFrame() - tl.GetStartFrame()
    item = mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": 0, "endFrame": length,
                                 "trackIndex": 2, "recordFrame": tl.GetStartFrame(), "mediaType": 2}])[0]
    item.SetProperty("AudioVolume", volume_db)
    item.SetFades({"FadeIn": fade_in, "FadeOut": fade_out})
    return item


def render(target_dir, name, timeout_s=55):
    """Render current timeline to MP4 H.264 1080x1920 with burned-in subtitles."""
    p = _project()
    p.DeleteAllRenderJobs()
    p.SetCurrentRenderFormatAndCodec("mp4", "H264")
    ok = p.SetRenderSettings({"SelectAllFrames": True, "TargetDir": target_dir, "CustomName": name,
                              "FormatWidth": 1080, "FormatHeight": 1920, "VideoQuality": 0,
                              "ExportVideo": True, "ExportAudio": True, "AudioCodec": "aac",
                              "ExportSubtitle": True, "SubtitleFormat": "BurnIn"})
    if not ok:
        raise RuntimeError("SetRenderSettings rejected the settings (one invalid key fails them all)")
    job = p.AddRenderJob(); p.StartRendering([job]); t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(3)
        st = p.GetRenderJobStatus(job)
        if st.get("JobStatus") == "Complete":
            break
    resolve.GetProjectManager().SaveProject()
    return st
