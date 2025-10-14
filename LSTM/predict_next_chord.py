# LSTM/predict_next_chord.py
import os, sys, json, re
import numpy as np
import torch
from typing import List, Tuple, Optional
import random

# --- 안전 경로 보정 ---
THIS_FILE = os.path.abspath(__file__)
LSTM_DIR  = os.path.dirname(THIS_FILE)
PROJ_ROOT = os.path.dirname(LSTM_DIR)
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

# --- .env 로드(있으면) ---
try:
    from dotenv import load_dotenv  # optional dependency
    load_dotenv()
except Exception:
    # python-dotenv 미설치/누락 시도 무시
    pass

from LSTM.model.train_lstm import ChordLSTM
from LSTM.harmony_score import evaluate_progression
from LSTM.chord_engine.smart_progression import generate_topk

BASE_DIRS = {
    "jazz": os.environ.get("CBB_MODEL_JAZZ", "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/jazz/New2"),
    "rock": os.environ.get("CBB_MODEL_ROCK", "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/rock"),
    "pop" : os.environ.get("CBB_MODEL_POP",  "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/pop"),
}
BASE_DATA_DIR = os.environ.get("CBB_DATA_DIR", "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data")

ROOT_RE = re.compile(r"^([A-G](?:#|b)?)")

def to_roots(tokens: List[str]) -> List[str]:
    roots = []
    for t in tokens:
        t = t.strip()
        if not t: continue
        m = ROOT_RE.match(t)
        roots.append(m.group(1) if m else t)
    return roots[:3]

def parse_seed_line(line: str) -> List[str]:
    if "," in line:
        return [x.strip() for x in line.split(",")]
    return line.strip().split()

def load_model_and_vocab(genre: str):
    try:
        base = BASE_DIRS[genre]
        c2i = np.load(os.path.join(base, "chord_to_index.npy"), allow_pickle=True).item()
        i2c = np.load(os.path.join(base, "index_to_chord.npy"), allow_pickle=True).item()
        model = ChordLSTM(len(c2i))
        state = torch.load(os.path.join(base, "chord_lstm.pt"), map_location=torch.device("cpu"))
        if hasattr(model, "embedding"):
            if "emb.weight" in state and "embedding.weight" not in state:
                state["embedding.weight"] = state.pop("emb.weight")
        elif hasattr(model, "emb"):
            if "embedding.weight" in state and "emb.weight" not in state:
                state["emb.weight"] = state.pop("embedding.weight")
        model.load_state_dict(state, strict=False)
        model.eval()
        print(f"🧠 Using LSTM model: {os.path.join(base, 'chord_lstm.pt')}")
        return model, c2i, i2c
    except Exception as e:
        print(f"⚠️  모델 로딩 실패(룰만 사용): {e}")
        return None, None, None

# --- 다양성 유틸 (MMR + 최소 차이 보장) ---
def _diff_positions(a: List[str], b: List[str]) -> int:
    n = min(len(a), len(b))
    return sum(1 for i in range(n) if a[i] != b[i])

def seq_similarity(a: List[str], b: List[str]) -> float:
    n = min(len(a), len(b))
    if n == 0: return 0.0
    same = sum(1 for i in range(n) if a[i]==b[i])
    return same / n

def mmr_select(
    cands: List[Tuple[List[str], float]],
    k: int = 2,
    lam: float = 0.55,                 # 조금 더 다양성 쪽으로 (기존 0.65)
    already: Optional[List[List[str]]] = None,
    min_diff: int = 3                  # 최소 3포지션은 달라야 선택
):
    """
    cands: (seq, score). lam↑ = 관련성 우선, lam↓ = 다양성 우선.
    min_diff: 기존 선택/고정 시퀀스들과 최소 몇 포지션 달라야 하는지.
    """
    # 점수 내림차순 정렬
    pool = sorted(cands, key=lambda x: x[1], reverse=True)

    selected: List[Tuple[List[str], float]] = []
    used = set()
    base = already or []

    # 1개 먼저 뽑기: 가장 높은 점수 + min_diff 조건 만족하는 첫 후보
    for seq, sc in pool:
        if any(_diff_positions(seq, b) < min_diff for b in base):
            continue
        t = tuple(seq)
        if t in used: continue
        selected.append((seq, sc)); used.add(t)
        break

    # 2~k개: MMR로 선택(유사도 높은 건 패널티)
    relax = 0
    while len(selected) < k:
        best = None
        for seq, sc in pool:
            t = tuple(seq)
            if t in used: continue
            # 최소 차이 포지션 보장 (선택/베이스 모두와)
            if any(_diff_positions(seq, s) < (min_diff - relax) for s,_ in selected) or \
               any(_diff_positions(seq, b) < (min_diff - relax) for b in base):
                continue
            max_sim = 0.0
            for s,_ in selected + [(x,0.0) for x in base]:
                max_sim = max(max_sim, seq_similarity(seq, s))
            mmr = lam*sc - (1.0-lam)*max_sim
            if (best is None) or (mmr > best[2]):
                best = (seq, sc, mmr)
        if best is None:
            # 후보가 더 없으면 조건을 한 단계 완화
            relax += 1
            if relax > min_diff: break
            continue
        selected.append((best[0], best[1])); used.add(tuple(best[0]))

    return selected

# --- 점수 버킷(뷰용 캘리브레이션) ---

# 기존 bucketize_three() 교체

def bucketize_three_dynamic(
    seqs: List[List[str]],
    scores01: List[float],
    top_seq: List[str],
) -> List[int]:
    """
    1) 각 결과는 미리 정한 버킷 범위에 표시되지만,
    2) 버킷 내부 위치는 (상대 점수 · 다양성 · 시퀀스 해시 지터)로 달라진다.
       - 같은 입력/같은 시퀀스면 항상 같은 퍼센트(해시 지터) → '하드코딩' 느낌 해소
       - 다른 입력/다른 시퀀스면 자연스럽게 달라짐
    """
    BUCKETS = [(86, 92), (44, 60), (12, 30)]

    def clamp(x, a, b): return max(a, min(b, x))
    def similarity(a, b):
        n = min(len(a), len(b))
        if n == 0: return 0.0
        same = sum(1 for i in range(n) if a[i]==b[i])
        return same / n

    out = []
    top_score = scores01[0] if scores01 else 1e-6
    for i, (seq, sc) in enumerate(zip(seqs[:3], scores01[:3])):
        lo, hi = BUCKETS[i]
        span = hi - lo

        # 기본 가중치: (0~1)로 버킷 내 위치를 잡는다
        if i == 0:
            # 1번(정석): 룰스코어가 높을수록 버킷 상단에
            base = clamp(sc, 0.0, 1.0)
            w = 0.6 + 0.4 * base
        else:
            # 상대 점수 & 다양성(=1-유사도)을 절반씩 반영
            ratio = clamp(sc / (top_score + 1e-9), 0.0, 1.0)
            nov   = 1.0 - similarity(seq, top_seq)
            w = clamp(0.5 * ratio + 0.5 * nov, 0.0, 1.0)

        # 시퀀스 해시 기반 지터(재현 가능)
        h = hash(tuple(seq)) & 0xffffffff
        rng = random.Random(h)
        jitter = rng.uniform(-0.10, 0.10)  # -0.10~+0.10 (버킷폭의 10%)

        pct = lo + span * clamp(w + jitter, 0.0, 1.0)
        out.append(int(round(pct)))

    # 후보가 2개 이하일 때도 안전
    while len(out) < 3:
        lo, hi = BUCKETS[len(out)]
        out.append(int((lo + hi) / 2))
    return out

# ---- Backward compatibility (keeps API used by app/core/pipeline_predict.py) ----
def bucketize_three(*args, **kwargs):
    """
    Wrapper for legacy callers.

    - Old usage: bucketize_three(scores01)
    - New usage: bucketize_three(seqs, scores01, top_seq)
    """
    # Old one-arg style -> return stable midpoints per bucket (as before)
    if len(args) == 1 and isinstance(args[0], list) and not kwargs:
        BUCKETS = [(86, 92), (44, 60), (12, 30)]
        scores01 = args[0]
        out = []
        for i in range(min(3, len(scores01))):
            lo, hi = BUCKETS[i]
            out.append(int(round((lo + hi) / 2)))
        while len(out) < 3:
            lo, hi = BUCKETS[len(out)]
            out.append(int(round((lo + hi) / 2)))
        return out

    # Otherwise, assume the new signature
    return bucketize_three_dynamic(*args, **kwargs)

def main():
    genres = list(BASE_DIRS.keys())
    while True:
        genre = input(f"예측할 코드 진행 장르를 입력하세요 {genres}: ").strip().lower()
        if genre in genres: break
        print(f"지원하는 장르만 입력하세요! ({'/'.join(genres)})")

    while True:
        raw = input("3개의 코드를 띄어쓰기 또는 콤마로 입력 (예: C G Am / D,G,C): ").strip()
        toks = parse_seed_line(raw)
        if len(toks) >= 3: break
        print("반드시 3개의 코드를 입력해주세요!")
    seed_roots = to_roots(toks)

    model, c2i, i2c = load_model_and_vocab(genre)
    use_model = model is not None

    # 1) 정석(룰 100%) 후보를 넉넉히 뽑고 1개 채택
    rule_pool = generate_topk(genre=genre, seed_roots=seed_roots, k=8, scorer=None, alpha=1.0)
    top1_seq, top1_sc = rule_pool[0]

    # 2) 모델+룰 블렌딩 후보를 더 많이 뽑아(다양성 확보) MMR로 2개 선택
    blended: List[Tuple[List[str], float]] = []
    if use_model:
        def scorer_fn(seq: List[str]) -> float:
            return float(evaluate_progression(model, seq, c2i, i2c))

        # 후보풀 확장 (20 -> 64)
        blended_pool = generate_topk(genre=genre, seed_roots=seed_roots, k=64, scorer=scorer_fn, alpha=0.5)
        blended_pool = [(s, sc) for (s, sc) in blended_pool if tuple(s) != tuple(top1_seq)]
        # MMR로 2개 (다양성 우선, 최소 3포지션 이상 다르게)
        blended = mmr_select(blended_pool, k=2, lam=0.55, already=[top1_seq], min_diff=3)
    else:
        rest = [(s, sc) for (s, sc) in rule_pool[1:]]
        blended = mmr_select(rest, k=2, lam=0.55, already=[top1_seq], min_diff=3)

    # 3) 표시용 점수 보정(80–90 / 40–60 / 10–30)
    raw_scores = [top1_sc] + [sc for _,sc in blended]
    seqs_for_show = [top1_seq] + [s for (s, _) in blended]
    raw_scores = [top1_sc] + [sc for (_, sc) in blended]
    shown = bucketize_three_dynamic(seqs_for_show, raw_scores, top1_seq)

    print(f"\n🎸 [{genre.upper()}] Top-3 예측 코드 진행:")
    print(f"1번 진행(정석/룰 기반, 점수 {shown[0]}%): " + " → ".join(top1_seq))
    if len(blended) >= 1:
        print(f"2번 진행(모델+룰 블렌딩, 점수 {shown[1]}%): " + " → ".join(blended[0][0]))
    if len(blended) >= 2:
        print(f"3번 진행(모델+룰 블렌딩, 점수 {shown[2]}%): " + " → ".join(blended[1][0]))

    # 4) 선택 및 저장
    valid = {"1": top1_seq}
    if len(blended) >= 1: valid["2"] = blended[0][0]
    if len(blended) >= 2: valid["3"] = blended[1][0]

    while True:
        choice = input(f"사용할 진행 번호를 입력하세요 ({'/'.join(valid.keys())}, q=취소): ").strip()
        if choice.lower()=='q': sys.exit("취소되었습니다.")
        if choice in valid: break

    out_dir = os.path.join(BASE_DATA_DIR, f"{genre}_midi", "chord_JSON")
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, "tmp_selected_progression.json")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"genre": genre, "progression": valid[choice]}, f, ensure_ascii=False, indent=2)
    print(f"✅ 선택된 진행이 저장되었습니다.\n→ {tmp_path}")
    print("다음 단계에서 useSongMaker_*.py 를 실행하세요.")

if __name__ == "__main__":
    main()