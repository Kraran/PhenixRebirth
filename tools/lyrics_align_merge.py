"""Second pass of tools/lyrics_align.py: the time of each line from the forced alignment (CTC), or from whisper's first word of the line when the
alignment is unsure and whisper heard that word nearby. --write puts the times into the game's lyrics files."""
import difflib
import json
import os
import sys

from lyrics_align import HERE, LYR, SONGS, LEAD, words_of

SURE = 0.5          # the CTC score above which its time is kept
NEAR = 4.0          # whisper's word must be this close to the CTC time to replace it


def main():
    write = "--write" in sys.argv
    keys = [k for k in sys.argv[1:] if not k.startswith("--")] or list(SONGS)
    for key in keys:
        ali = os.path.join(HERE, key + ".align.json")
        if not os.path.exists(ali):
            print(key, "not aligned yet")
            continue
        rep = json.load(open(ali))
        heard = [tuple(x) for x in json.load(open(os.path.join(HERE, key + ".whisper.json")))]
        path = os.path.join(LYR, key + ".json")
        data = json.load(open(path, encoding="utf-8"))
        lines = data["lines"]
        lw, own = [], []
        for i, ln in enumerate(lines):
            for wi, w in enumerate(words_of(ln.get("text", ""))):
                lw.append(w)
                own.append((i, wi))
        hw = [w for w, _s in heard]
        # line -> whisper's time of its start: from its 2nd word (minus the length of a word) when heard, whisper dates
        # the first word after a silence too early; else from its first word
        by_word = {}
        sm = difflib.SequenceMatcher(None, lw, hw, autojunk=False)
        for a, b, n in sm.get_matching_blocks():
            for k in range(n):
                by_word[own[a + k]] = heard[b + k][1]
        first = {}
        for (li, wi), s in by_word.items():
            if wi == 1:
                first[li] = s - 0.35
        for (li, wi), s in by_word.items():
            if wi == 0 and li not in first:
                first[li] = s
        # a line heard for sure: at least 3 of its words in a row matched by the global alignment of the words
        strong = {}
        for a, b, n in sm.get_matching_blocks():
            run = {}
            for k in range(n):
                li, wi = own[a + k]
                run.setdefault(li, []).append((wi, heard[b + k][1]))
            for li, ws in run.items():
                if len(ws) >= 3 and li not in strong:
                    wi, s = ws[1] if ws[0][0] == 0 and len(ws) > 1 and ws[1][0] == 1 else ws[0]
                    strong[li] = s - 0.35 * wi
        times, changed, last = {}, 0, -1.0
        for r in rep:
            t = r["t"]
            w = first.get(r["i"])
            doubt = r["heard"] < 0.4                  # whisper did not hear the line where the alignment put it
            sure = strong.get(r["i"])
            if sure is not None and abs((sure - LEAD) - t) > 1.5:
                t = round(max(0.0, sure - LEAD), 2)   # the words of the line were heard elsewhere: they win
                changed += 1
            elif w is not None and abs((w - LEAD) - t) > 0.4 and (doubt or (r["p"] < SURE and abs((w - LEAD) - t) <= NEAR)):
                t = round(max(0.0, w - LEAD), 2)
                changed += 1
            t = max(t, last + 0.3)                    # (always in order)
            times[r["i"]] = round(t, 2)
            last = t
        moved = [abs(times[i] - (lines[i].get("t") or 0)) for i in times]
        print(f"{key}: {len(times)} lines, {changed} taken from whisper, moved > 1 s: {sum(m > 1 for m in moved)}, "
              f"max move {max(moved):.1f} s")
        if write:
            for i, t in times.items():
                lines[i]["t"] = t
            out = []
            for ln in lines:
                if ln.get("text"):
                    out.append({"t": ln["t"]} | {k: v for k, v in ln.items() if k != "t"})
                else:
                    out.append({"text": ""})
            data["lines"] = out
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
                fh.write("\n")


if __name__ == "__main__":
    main()
