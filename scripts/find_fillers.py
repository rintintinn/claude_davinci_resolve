"""Find filler words (um/uh/erm/emm/hmm) with timings.

Whisper drops disfluencies by default, and on long audio even a filler-style prompt
stops working after the first window. So: transcribe short overlapping windows, each
primed with a filler-laden prompt, and collect filler words in absolute time.

Run with whisper's own Python (it has torch + whisper installed):
  /opt/homebrew/opt/openai-whisper/libexec/bin/python scripts/find_fillers.py audio.wav fillers.json
Output: [[start_s, end_s, "word"], ...]
"""
import json, re, sys
import whisper

WIN, STEP, SR = 8.0, 6.0, 16000
PROMPT = "Umm, let me think like, hmm... Okay, uh, here's what I'm, erm, like, thinking. Emm, so, uh, yeah."
FILLER = re.compile(r"(u+m+|u+h+m*|e+r+m*|e+m+|h+m+|a+h+|m+h*m+)")

wav, out = sys.argv[1], sys.argv[2]
audio = whisper.load_audio(wav)
model = whisper.load_model("small")
dur = len(audio) / SR

hits = []
t = 0.0
while t < dur:
    clip = audio[int(t * SR): int(min(t + WIN, dur) * SR)]
    r = model.transcribe(clip, language="en", word_timestamps=True, initial_prompt=PROMPT,
                         condition_on_previous_text=False, fp16=False)
    for s in r["segments"]:
        for w in s["words"]:
            if FILLER.fullmatch(re.sub(r"[^a-z]", "", w["word"].lower())):
                hits.append([round(t + w["start"], 2), round(t + w["end"], 2), w["word"].strip()])
    t += STEP

# merge duplicates from overlapping windows
hits.sort()
merged = []
for h in hits:
    if merged and h[0] <= merged[-1][1] + 0.15:
        merged[-1][1] = max(merged[-1][1], h[1])
    else:
        merged.append(h)
json.dump(merged, open(out, "w"))
print(f"{len(merged)} fillers:", " ".join(f"{w}@{a:.2f}-{b:.2f}" for a, b, w in merged))
