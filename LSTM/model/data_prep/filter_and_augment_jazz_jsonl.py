# -*- coding: utf-8 -*-
# LSTM/model/data_prep/filter_and_augment_jazz_jsonl.py
import re, json, os, argparse, itertools, random
from collections import Counter

NOTES_SHARP = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
NOTES_FLAT  = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
NAME2IDX = {n:i for i,n in enumerate(NOTES_SHARP)}
NAME2IDX.update({n:i for i,n in enumerate(NOTES_FLAT)})

JAZZ_QUALS = ('7','maj7','m7','dim','aug','sus')  # 재즈성 여부 판단용(간단)

def parse_chord(ch: str):
    m = re.match(r'^([A-G](?:#|b)?)(.*)$', ch.strip())
    if not m:
        return ch.strip(), ''
    return m.group(1), m.group(2)

def simplify_suffix(rest: str) -> str:
    s = rest.strip()
    sl = s.lower()
    if 'maj7' in sl or 'Δ7' in s:     return 'maj7'
    if 'm7'   in sl or 'min7' in sl:  return 'm7'
    if 'maj'  in sl:                  return 'maj7'
    if any(x in sl for x in ['9','11','13']): return '7'
    if re.search(r'7', sl):           return '7'
    if 'min'  in sl:                  return 'm'
    if re.search(r'(^|[^a-zA-Z])m($|[^a-zA-Z])', sl): return 'm'
    if 'dim'  in sl:                  return 'dim'
    if 'aug'  in sl or '+' in sl:     return 'aug'
    if 'sus'  in sl:                  return 'sus4'
    return ''  # 메이저 삼화음

def simplify_chord(ch: str) -> str:
    root, rest = parse_chord(ch)
    suf = simplify_suffix(rest)
    return root + (suf if suf else '')

def jazz_ratio(seq):
    if not seq: return 0.0
    return sum(any(q in ch for q in JAZZ_QUALS) for ch in seq)/len(seq)

def transpose_note(root: str, shift: int, prefer_flat=True) -> str:
    idx = NAME2IDX.get(root)
    if idx is None:  # 알 수 없는 표기면 그대로
        return root
    new_idx = (idx + shift) % 12
    return NOTES_FLAT[new_idx] if prefer_flat else NOTES_SHARP[new_idx]

def transpose_chord(ch: str, shift: int) -> str:
    root, rest = parse_chord(ch)
    prefer_flat = ('b' in root) or ('#' not in root)  # b면 flat, #면 sharp, 나머지는 flat쪽 선호
    return transpose_note(root, shift, prefer_flat) + rest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="inp",  required=True, help="입력 JSONL 파일")
    ap.add_argument("--out", dest="outp", required=True, help="출력 JSONL 파일")
    ap.add_argument("--min_len", type=int, default=8)
    ap.add_argument("--max_len", type=int, default=64)
    ap.add_argument("--min_jazz_ratio", type=float, default=0.5)
    ap.add_argument("--augment", action="store_true", help="12키 전조 증강")
    args = ap.parse_args()

    raw = []
    with open(args.inp, "r", encoding="utf-8") as f:
        for ln in f:
            o = json.loads(ln)
            if isinstance(o, dict) and "chords" in o:
                raw.append(o["chords"])

    # 1) 정규화
    norm = [[simplify_chord(c) for c in seq] for seq in raw]

    # 2) 필터: 길이 & 재즈 비율
    keep = [seq for seq in norm
            if args.min_len <= len(seq) <= args.max_len and jazz_ratio(seq) >= args.min_jazz_ratio]

    # 3) 중복 제거
    seen = set()
    dedup = []
    for s in keep:
        t = tuple(s)
        if t not in seen:
            seen.add(t)
            dedup.append(s)

    # 4) 증강(옵션): 12키 전조
    out_seqs = []
    if args.augment:
        for s in dedup:
            for k in range(12):
                if k == 0:
                    out_seqs.append(s)
                else:
                    out_seqs.append([transpose_chord(ch, k) for ch in s])
    else:
        out_seqs = dedup

    # 5) 저장
    os.makedirs(os.path.dirname(args.outp), exist_ok=True)
    with open(args.outp, "w", encoding="utf-8") as f:
        for s in out_seqs:
            f.write(json.dumps({"chords": s}, ensure_ascii=False) + "\n")

    print(f"raw={len(raw)}  -> norm_keep={len(keep)}  -> dedup={len(dedup)}  -> out={len(out_seqs)}")
    # 간단 통계
    vocab = Counter(ch for s in out_seqs for ch in s)
    print(f"vocab_size={len(vocab)}  top20={vocab.most_common(20)}")

if __name__ == "__main__":
    main()