# app/core/pipeline_predict.py
from __future__ import annotations
import threading
import re
import os, sys
from typing import List, Tuple

# ---- 경로 보정 (LSTM 패키지 접근) ----
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from LSTM.predict_next_chord import (
    load_model_and_vocab,
    mmr_select,
    bucketize_three_dynamic as bucketize_three,  # ← 새 함수로 매핑
)

from LSTM.chord_engine.smart_progression import generate_topk
from LSTM.harmony_score import evaluate_progression, interpret_score

# 멀티 요청 대비 모델 캐시
_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()

ROOT_RE = re.compile(r"^([A-G](?:#|b)?)")

def _to_roots(tokens: List[str]) -> List[str]:
    """코드 심볼에서 루트만 추출(C, D#, Eb 등). 최대 3개 사용."""
    roots: List[str] = []
    for t in tokens:
        t = (t or "").strip()
        if not t:
            continue
        m = ROOT_RE.match(t)
        roots.append(m.group(1) if m else t)
    return roots[:3]

def get_model_assets(genre: str):
    """모델/사전 캐시 로드."""
    with _MODEL_LOCK:
        if genre not in _MODEL_CACHE:
            model, chord_to_index, index_to_chord = load_model_and_vocab(genre)
            _MODEL_CACHE[genre] = (model, chord_to_index, index_to_chord)
        return _MODEL_CACHE[genre]

def predict_top_k(genre: str, seed: List[str], k: int = 3):
    seed_roots = _to_roots(seed)

    model, c2i, i2c = get_model_assets(genre)
    use_model = model is not None

    rule_pool: List[Tuple[List[str], float]] = generate_topk(
        genre=genre, seed_roots=seed_roots, k=8, scorer=None, alpha=1.0
    )
    if not rule_pool:
        return [{"progression": seed_roots, "score": 0.5, "label": "기본 진행"}]

    top1_seq, top1_sc = rule_pool[0]

    blended: List[Tuple[List[str], float]] = []
    if use_model:
        def scorer_fn(seq: List[str]) -> float:
            return float(evaluate_progression(model, seq, c2i, i2c))
        blended_pool = generate_topk(
            genre=genre, seed_roots=seed_roots, k=64, scorer=scorer_fn, alpha=0.5
        )
        blended_pool = [(s, sc) for (s, sc) in blended_pool if tuple(s) != tuple(top1_seq)]
        blended = mmr_select(blended_pool, k=max(0, k - 1), lam=0.55, already=[top1_seq], min_diff=3)
    else:
        rest = [(s, sc) for (s, sc) in rule_pool[1:]]
        blended = mmr_select(rest, k=max(0, k - 1), lam=0.55, already=[top1_seq], min_diff=3)

    combined = [(top1_seq, top1_sc)] + blended
    combined = combined[:k]

    # ★ 동적 버킷팅 (입력에 따라 %가 달라짐)
    raw_scores = [sc for _, sc in combined]
    seqs_for_show = [seq for (seq, _) in combined]
    top_seq = combined[0][0]
    shown_pct = bucketize_three(seqs_for_show, raw_scores, top_seq=top_seq)  # e.g., [91, 57, 23]

    results = []
    for i, (seq, _) in enumerate(combined):
        label = "정석 진행" if i == 0 else "대안 진행"
        score01 = float(shown_pct[i] if i < len(shown_pct) else 50) / 100.0
        results.append({"progression": seq, "score": score01, "label": label})

    return results