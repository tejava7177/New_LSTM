# app/core/pipeline_predict.py
import threading
import numpy as np
import torch
import os, sys

# 기존 경로 맞게 조정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../LSTM/model')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../LSTM')))
from LSTM.predict_next_chord import load_model_and_vocab, generate_multiple_progressions
from LSTM.harmony_score  import evaluate_progression, interpret_score

# 멀티 요청 대비 모델 캐싱(간단 구현)
_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()

def get_model_assets(genre):
    with _MODEL_LOCK:
        if genre not in _MODEL_CACHE:
            model, chord_to_index, index_to_chord = load_model_and_vocab(genre)
            _MODEL_CACHE[genre] = (model, chord_to_index, index_to_chord)
        return _MODEL_CACHE[genre]

def predict_top_k(genre: str, seed: list[str], k: int = 3):
    # 모델, vocab 불러오기 (캐시)
    model, chord_to_index, index_to_chord = get_model_assets(genre)
    # Top-3 진행 각각 생성 (기본 5스텝, seed 3개 + 5 = 8개)
    n_steps = 5
    candidates = generate_multiple_progressions(
        model, chord_to_index, index_to_chord, seed, n_generate=n_steps, k=k
    )  # [ [seed + pred...], ... ]  (k개)
    results = []
    for prog in candidates:
        s = evaluate_progression(model, prog, chord_to_index, index_to_chord)
        results.append({
            "progression": prog,
            "score": float(s),
            "label": interpret_score(s)
        })
    return results