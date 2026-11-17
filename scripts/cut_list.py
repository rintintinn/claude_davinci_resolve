"""Turn hand-picked keep ranges into frame segments with pauses removed.

Usage: python3 scripts/cut_list.py keep.json silences.txt segments.json [--fps 30] [--remove fillers.json]

keep.json     : [[start_s, end_s], ...] source-time ranges to keep (from transcript.txt)
silences.txt  : "start end" per line (from analyze.sh)
fillers.json  : [[start_s, end_s, ...], ...] ranges cut exactly, widened by FILLER_PAD (from find_fillers.py)
segments.json : [[start_frame, end_frame), ...] for AppendToTimeline (endFrame exclusive)
"""
import argparse, json

PAD = 0.08      # seconds of silence kept at each edge of a cut
MIN_GAP = 0.30  # only remove silences at least this long
MIN_PIECE = 0.12
FILLER_PAD = 0.04  # extra seconds cut on each side of a filler

ap = argparse.ArgumentParser()
ap.add_argument("keep"); ap.add_argument("silences"); ap.add_argument("out")
ap.add_argument("--fps", type=float, default=30)
ap.add_argument("--remove")
args = ap.parse_args()

keep = json.load(open(args.keep))
sil = [tuple(map(float, l.split())) for l in open(args.silences) if l.strip()]
cuts = [(s + PAD, e - PAD) for s, e in sil if (e - s) >= MIN_GAP]
if args.remove:
    cuts += [(r[0] - FILLER_PAD, r[1] + FILLER_PAD) for r in json.load(open(args.remove))]

out = []
for a, b in keep:
    pieces = [(a, b)]
    for s2, e2 in cuts:
        nxt = []
        for x, y in pieces:
            if e2 <= x or s2 >= y:
                nxt.append((x, y)); continue
            if s2 > x: nxt.append((x, s2))
            if e2 < y: nxt.append((e2, y))
        pieces = nxt
    out += [p for p in pieces if p[1] - p[0] >= MIN_PIECE]

merged = []
for x, y in out:
    if merged and abs(x - merged[-1][1]) < 0.02:
        merged[-1] = (merged[-1][0], y)
    else:
        merged.append((x, y))

frames = [(round(x * args.fps), round(y * args.fps)) for x, y in merged]
frames = [[a, b] for a, b in frames if b > a]
json.dump(frames, open(args.out, "w"))
print(f"{len(frames)} segments, {sum(b - a for a, b in frames) / args.fps:.1f}s")
