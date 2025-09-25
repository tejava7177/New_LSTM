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

# 새 로직에서 실제로 존재하는 것들만 임포트
from LSTM.predict_next_chord import (
    load_model_and_vocab,
    mmr_select,
    bucketize_three,
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
    """
    프론트엔드가 기대하는 결과 포맷으로 Top-K 진행을 생성.
    반환: [{ progression: [..], score: 0~1, label: str }, ...]
    """
    # 1) seed를 루트 3개로 축약
    seed_roots = _to_roots(seed)

    # 2) 모델/사전
    model, c2i, i2c = get_model_assets(genre)
    use_model = model is not None

    # 3) 룰 기반 상위 후보(안정적 정석용)
    rule_pool: List[Tuple[List[str], float]] = generate_topk(
        genre=genre, seed_roots=seed_roots, k=8, scorer=None, alpha=1.0
    )
    if not rule_pool:
        # 예외적 상황: 후보가 하나도 없으면 seed만 돌려줌
        return [{
            "progression": seed_roots,
            "score": 0.5,
            "label": "기본 진행"
        }]

    top1_seq, top1_sc = rule_pool[0]

    # 4) 블렌딩 후보 + 다양성 선택(MMR)
    blended: List[Tuple[List[str], float]] = []
    if use_model:
        def scorer_fn(seq: List[str]) -> float:
            return float(evaluate_progression(model, seq, c2i, i2c))

        # 후보풀 넓게 뽑고(64) 1등과 동일한 건 제외
        blended_pool = generate_topk(
            genre=genre, seed_roots=seed_roots, k=64, scorer=scorer_fn, alpha=0.5
        )
        blended_pool = [(s, sc) for (s, sc) in blended_pool if tuple(s) != tuple(top1_seq)]

        # 다양성 우선( lam=0.55 ) + 최소 3포지션 이상 다른 후보
        blended = mmr_select(
            blended_pool, k=max(0, k - 1), lam=0.55, already=[top1_seq], min_diff=3
        )
    else:
        # 모델 없으면 룰풀의 나머지에서 다양성 선택
        rest = [(s, sc) for (s, sc) in rule_pool[1:]]
        blended = mmr_select(rest, k=max(0, k - 1), lam=0.55, already=[top1_seq], min_diff=3)

    combined = [(top1_seq, top1_sc)] + blended
    combined = combined[:k]

    # 5) UI용 점수 보정(0~1로 반환: 프론트가 x100% 표시)
    raw_scores = [sc for _, sc in combined]
    # bucketize_three는 상위 3개 기준으로 보정하므로 부족하면 0으로 채움
    shown_pct = bucketize_three(raw_scores + [0.0, 0.0, 0.0])  # List[int] (예: [88, 52, 18])

    results = []
    for i, (seq, sc) in enumerate(combined):
        label = "정석 진행" if i == 0 else "대안 진행"
        # 프론트는 0~1 점수를 기대하므로 백분율/100으로 전달
        score01 = float(shown_pct[i] if i < len(shown_pct) else 50) / 100.0
        results.append({
            "progression": seq,
            "score": score01,
            "label": label
        })

    return results