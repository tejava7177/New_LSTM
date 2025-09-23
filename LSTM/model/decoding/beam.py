# LSTM/model/decoding/beam.py
import math
import numpy as np
import torch
from typing import List, Tuple, Dict

from LSTM.model.rules.base import GenreRule

def predict_topk_with_probs(model, chord_to_index: Dict[str,int], index_to_chord: Dict[int,str],
                            input_chords: List[str], k: int = 8):
    idxs = [chord_to_index.get(c, 0) for c in input_chords]
    x = torch.tensor([idxs], dtype=torch.long)
    with torch.no_grad():
        out = model(x)
        probs = torch.softmax(out, dim=1)[0].cpu().numpy()  # (vocab,)
        topk_idx = np.argsort(-probs)[:k]
    names = [index_to_chord[int(i)] for i in topk_idx]
    pvals = [float(probs[int(i)]) for i in topk_idx]
    return names, pvals

def generate_progressions_guided(model, chord_to_index, index_to_chord,
                                 seed_chords: List[str], steps: int = 5,
                                 beams: int = 4, per_step_top: int = 8,
                                 rule: GenreRule = None, enforce_upgrade: bool = False):
    """
    누적 점수 = Σ log(model_prob) + rule.alpha * rule.partial_score(seq)
    """
    if rule is None:
        rule = GenreRule()

    beams_list: List[Tuple[List[str], float]] = [(list(seed_chords), 0.0)]
    for _ in range(steps):
        new_beams: List[Tuple[List[str], float]] = []
        for seq, cum_log in beams_list:
            last3 = seq[-3:]
            names, pvals = predict_topk_with_probs(model, chord_to_index, index_to_chord, last3, k=per_step_top)
            # 후보 전처리
            names = [rule.normalize_candidate(seq[-1] if seq else "", n) for n in names]
            names = rule.filter_candidates(names)
            # 확률 맵 (이름 변경 후 정렬 싱크 문제는 근사치로 사용)
            # 실제로는 원-핫 매핑을 다시 계산하는 게 맞지만 간단화
            prob_map = {}
            for i, nm in enumerate(names):
                prob_map[nm] = pvals[i] if i < len(pvals) else 1e-9

            for ch in names:
                cand = ch
                if enforce_upgrade:
                    # 장르 규칙에 승격 메서드 있는 경우 사용
                    if hasattr(rule, "maybe_upgrade"):
                        cand = rule.maybe_upgrade(seq[-1] if seq else "", cand)
                prob = max(prob_map.get(ch, 1e-9), 1e-9)
                partial = seq + [cand]
                s_rule = rule.partial_score(partial)  # 0~1
                score = cum_log + math.log(prob) + rule.alpha * s_rule
                new_beams.append((partial, score))
        new_beams.sort(key=lambda x: x[1], reverse=True)
        beams_list = new_beams[:beams]
    return [seq for (seq, _) in beams_list[:3]]