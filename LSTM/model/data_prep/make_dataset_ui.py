# LSTM/model/data_prep/make_dataset_ui.py
import os, json, random, numpy as np
from glob import glob
from vocab_ui import to_ui_token, transpose, ROOTS

# 입력: 정제된 진행 파일들 (json 또는 jsonl). 각 레코드에 ["chords"] 배열이 있다고 가정.
# 출력: X.npy, y.npy, chord_to_index.npy, index_to_chord.npy
def load_progressions(in_paths):
    progs = []
    for p in in_paths:
        if p.endswith(".jsonl"):
            with open(p,"r",encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    obj = json.loads(line)
                    ch = obj.get("chords") or obj.get("progression")
                    if ch: progs.append(ch)
        else:
            with open(p,"r",encoding="utf-8") as f:
                obj = json.load(f)
                if isinstance(obj, dict):  # {"chords":[...]} or {"progressions":[...]}
                    if "chords" in obj: progs.append(obj["chords"])
                    elif "progressions" in obj: progs += obj["progressions"]
                elif isinstance(obj, list):
                    progs += obj
    return progs

def ui_project(seq):
    out=[]
    for t in seq:
        u = to_ui_token(t)
        if u: out.append(u)
    return out

def augment(seq):
    return [ [transpose(t, s) for t in seq] for s in range(12) ]

def windows(seq, n_in=3):
    X,y=[],[]
    for i in range(len(seq)-n_in):
        X.append(seq[i:i+n_in]); y.append(seq[i+n_in])
    return X,y

def build_vocab(seqs):
    toks = sorted(set(t for s in seqs for t in s))
    chord_to_idx = {t:i for i,t in enumerate(toks)}
    idx_to_chord = {i:t for t,i in chord_to_idx.items()}
    return chord_to_idx, idx_to_chord

def encode(X, y, chord_to_idx):
    X_idx = np.array([[chord_to_idx[t] for t in seq] for seq in X], dtype=np.int64)
    y_idx = np.array([chord_to_idx[t] for t in y], dtype=np.int64)
    return X_idx, y_idx

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True, help="정제된 진행 파일들(.json/.jsonl)")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    raw = load_progressions(args.input)

    # 1) UI 축소 + 너무 짧은 진행 제거(>=8마디 권장)
    proj = [ui_project(seq) for seq in raw]
    proj = [s for s in proj if len(s) >= 8]

    # 2) 12키 증강
    aug = []
    for s in proj:
        aug += augment(s)

    # 3) 윈도우 슬라이싱
    X_all, y_all = [], []
    for s in aug:
        X,y = windows(s, n_in=3)
        X_all += X; y_all += y

    # 4) 어휘/인코딩
    chord_to_idx, idx_to_chord = build_vocab( X_all + [[t] for t in y_all] )
    X_idx, y_idx = encode(X_all, y_all, chord_to_idx)

    # 5) 저장
    np.save(os.path.join(args.outdir, "X.npy"), X_idx)
    np.save(os.path.join(args.outdir, "y.npy"), y_idx)
    np.save(os.path.join(args.outdir, "chord_to_index.npy"), chord_to_idx)
    np.save(os.path.join(args.outdir, "index_to_chord.npy"), idx_to_chord)

    # 간단 통계
    print(f"progressions(raw)={len(raw)}, filtered={len(proj)}, augmented={len(aug)}")
    print(f"dataset: X={len(X_idx)}, vocab={len(chord_to_idx)}")