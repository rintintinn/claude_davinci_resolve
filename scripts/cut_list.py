"""Turn hand-picked keep ranges into frame segments with pauses removed.

Usage: python3 scripts/cut_list.py keep.json silences.txt segments.json [--fps 30]

keep.json     : [[start_s, end_s], ...] source-time ranges to keep (from transcript.txt)
silences.txt  : "start end" per line (from analyze.sh)
segments.json : [[start_frame, end_frame), ...] for AppendToTimeline (endFrame exclusive)
"""
import argparse, json

PAD = 0.08      # seconds of silence kept at each edge of a cut
MIN_GAP = 0.30  # only remove silences at least this long
MIN_PIECE = 0.12

ap = argparse.ArgumentParser()
ap.add_argument("keep"); ap.add_argument("silences"); ap.add_argument("out")
ap.add_argument("--fps", type=float, default=30)
args = ap.parse_args()

keep = json.load(open(args.keep))
sil = [tuple(map(float, l.split())) for l in open(args.silences) if l.strip()]

out = []
for a, b in keep:
    pieces = [(a, b)]
    for s, e in sil:
        s2, e2 = s + PAD, e - PAD
        if e2 - s2 < MIN_GAP - 2 * PAD:
            continue
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
