# make_midi_test/jazzDrumPatterns_Test.py
import random
from typing import Tuple, List, Optional

# 본 프로젝트의 드럼 생성기(수정 없음)를 그대로 import
from SongMaker.Patterns_Jazz.Drum.jazzDrumPatterns import generate_jazz_drum_pattern as base_drum

def _sprinkle_ghosts(melodies, prob: float, r: random.Random):
    if not melodies:
        return melodies
    out = []
    for ev in melodies:
        out.append(ev)
        if r.random() < prob:
            out.append(ev)  # 단순 복제 → 이후 velocity 휴먼라이즈로 유령음처럼 낮아짐
    return out

def generate_jazz_drum_pattern_variation(
    measures: int,
    style: str,
    density: str = "medium",
    fill_prob: float = 0.12,
    seed: Optional[int] = None,
) -> Tuple[List, List, List, List]:
    r = random.Random(seed)
    d_m, d_b, d_d, d_l = base_drum(
        measures=measures, style=style, density=density, fill_prob=fill_prob, seed=seed
    )
    # 가벼운 변형 1: 고스트/필 밀도 소폭 증가(매번 다른 결과)
    d_m = _sprinkle_ghosts(d_m, prob=0.08 + r.random()*0.07, r=r)
    return d_m, d_b, d_d, d_l