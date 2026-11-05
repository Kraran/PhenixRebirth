"""Sync the lyrics of Lyra's songs on her isolated voice.

1. CTC forced alignment (wav2vec2) of the whole text of a song over its vocals: every word gets a start time, in order.
2. Check against faster-whisper word timestamps of the same vocals: for each line, do the words heard around its start
   time match the words of the line?

How to (needs: pip install audio-separator faster-whisper torch torchaudio transformers, and ffmpeg):
  1. the voice alone, in the work folder ($LYRICS_WORK, default ./lyrics_work), one file per song:
       audio-separator <song>.wav --model_filename UVR-MDX-NET-Voc_FT.onnx --single_stem Vocals --output_format WAV \
                       --output_dir lyrics_work/voc
  2. python tools/lyrics_align.py [keys...]          the alignment, <key>.align.json in the work folder
  3. python tools/lyrics_align_merge.py [--write]    the second pass, and the times into assets/music/lyrics/<key>.json
Run one step at a time on a small machine: the separation and the models each take a few GB of memory.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.abspath(os.environ.get("LYRICS_WORK", "lyrics_work"))
LYR = os.path.join(REPO, "assets/music/lyrics")
SONGS = {
    "lyra_eternal_dawn": "lyra_1_eternal_dawn",
    "lyra_what_we_lost": "lyra_2_what_we_lost",
    "lyra_no_mercy_left": "lyra_3_no_mercy_left",
    "lyra_oldest_fear": "Lyra-Voss-Oldest-Fear",
    "lyra_when_we_looked_up": "concertmars",
    "lyra_when_we_looked_up_unplugged": "Lyra-Voss-When-We-Looked-Up-Unplugged",
}
SR = 16000
LEAD = 0.15             # the line lights up just before its first word


def vocals(key):
    d = os.path.join(HERE, "voc")
    name = SONGS[key]
    f = next(os.path.join(d, x) for x in os.listdir(d) if x.startswith(name) and "Vocals" in x)
    raw = subprocess.run(["ffmpeg", "-loglevel", "quiet", "-i", f, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
       "8": "eight", "9": "nine", "10": "ten"}


def words_of(text):
    out = []
    for w in text.replace("—", " ").replace("-", " ").split():
        w = w.lower().replace("’", "'")
        w = NUM.get(re.sub(r"[^0-9]", "", w), w) if re.fullmatch(r"\W*\d+\W*", w) else w
        w = re.sub(r"[^a-z']", "", w).strip("'")
        if w:
            out.append(w)
    return out


def ctc_align(audio, line_words):
    import torch
    import torchaudio.functional as F
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    name = os.environ.get("W2V", "facebook/wav2vec2-large-960h-lv60-self")
    proc = Wav2Vec2Processor.from_pretrained(name)
    model = Wav2Vec2ForCTC.from_pretrained(name).eval()
    torch.set_num_threads(2)
    chunk = SR * 20
    ems = []
    with torch.inference_mode():
        for s in range(0, len(audio), chunk):
            seg = audio[s:s + chunk]
            if len(seg) < 400:
                continue
            x = proc(seg, sampling_rate=SR, return_tensors="pt").input_values
            ems.append(torch.log_softmax(model(x).logits[0], -1))
    em = torch.cat(ems)
    frame = len(audio) / SR / em.shape[0]
    vocab = proc.tokenizer.get_vocab()
    blank = vocab.get("<pad>", 0)
    sep = vocab["|"]
    tokens, owner = [], []                       # owner: (line index, word index) of each token
    for li, ws in line_words:
        for wi, w in enumerate(ws):
            for ch in w.upper():
                if ch in vocab:
                    tokens.append(vocab[ch])
                    owner.append((li, wi))
            tokens.append(sep)
            owner.append(None)
    targets = torch.tensor([tokens], dtype=torch.int32)
    ali, scores = F.forced_align(em.unsqueeze(0), targets, blank=blank)
    ali, scores = ali[0].tolist(), scores[0].exp().tolist()
    # first frame of each token
    starts, ti, prev = {}, -1, blank
    probs = {}
    for f, (tok, sc) in enumerate(zip(ali, scores)):
        if tok != blank and (tok != prev or prev == blank):
            ti += 1
            if ti < len(owner) and owner[ti] is not None:
                key = owner[ti]
                if key not in starts:
                    starts[key] = f * frame
                probs.setdefault(key[0], []).append(sc)
        prev = tok
    return starts, {li: float(np.mean(v)) for li, v in probs.items()}


def whisper_words(audio, prompt):
    from faster_whisper import WhisperModel
    m = WhisperModel(os.environ.get("WM", "large-v3-turbo"), device="cpu", compute_type="int8", cpu_threads=2)
    segs, _ = m.transcribe(audio, word_timestamps=True, language="en", initial_prompt=prompt[:600],
                           condition_on_previous_text=False, vad_filter=False)
    out = []
    for s in segs:
        for w in s.words:
            ww = words_of(w.word)
            if ww:
                out.append((ww[0], float(w.start)))
    return out


def check(ws, t, heard):
    near = {w for w, s in heard if t - 1.0 <= s <= t + 3.5}
    want = set(ws[:5])
    return len(want & near) / max(1, len(want))


def main():
    keys = [k for k in sys.argv[1:] if not k.startswith("--")] or list(SONGS)
    for key in keys:
        path = os.path.join(LYR, key + ".json")
        data = json.load(open(path, encoding="utf-8"))
        lines = data["lines"]
        line_words = [(i, words_of(ln.get("text", ""))) for i, ln in enumerate(lines) if ln.get("text")]
        audio = vocals(key)
        cache = os.path.join(HERE, key + ".whisper.json")
        if os.path.exists(cache):
            heard = [tuple(x) for x in json.load(open(cache))]
        else:
            heard = whisper_words(audio, " ".join(ln["text"] for ln in lines if ln.get("text")))
            json.dump(heard, open(cache, "w"))
        starts, probs = ctc_align(audio, line_words)
        rep = []
        for li, ws in line_words:
            t = starts.get((li, 0))
            if t is None:
                continue
            rep.append({"i": li, "t": round(max(0.0, t - LEAD), 2), "old": lines[li].get("t"), "p": round(probs.get(li, 0), 3),
                        "heard": round(check(ws, t, heard), 2), "text": lines[li]["text"]})
        json.dump(rep, open(os.path.join(HERE, key + ".align.json"), "w"), indent=1)
        ok = sum(r["heard"] >= 0.4 for r in rep)
        print(f"{key}: {len(rep)} lines, {ok} confirmed by whisper", flush=True)
        for r in rep:
            flag = "" if r["heard"] >= 0.4 else "   <-- ?"
            print(f"  {r['t']:7.2f} (was {r['old']:7.2f})  p={r['p']:.2f} heard={r['heard']:.2f}  {r['text'][:50]}{flag}")


if __name__ == "__main__":
    main()
