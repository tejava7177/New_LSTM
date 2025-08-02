# SongMaker/utils/timing.py
from typing import List, Tuple, Optional

def quantize(x: float, grid: float = 0.25) -> float:
    """x를 grid(기본 16분=0.25) 단위로 반올림."""
    return round(x / grid) * grid

def fix_beats(
    melodies: List[List[str]],
    beat_ends: List[float],
    dynamics: List[str],
    lyrics: List[str],
    *,
    grid: float = 0.25,
    total_beats: Optional[float] = None,
) -> Tuple[List[List[str]], List[float], List[str], List[str]]:
    """
    - beat_ends를 그리드에 스냅 + 단조증가 강제
    - 길이 불일치(리스트 길이) 정리
    - total_beats가 주어지면 마지막을 정확히 거기에 맞춤
    """
    n = min(len(melodies), len(beat_ends), len(dynamics), len(lyrics))
    melodies, beat_ends, dynamics, lyrics = melodies[:n], beat_ends[:n], dynamics[:n], lyrics[:n]

    fixed = []
    prev = 0.0
    for b in beat_ends:
        bq = quantize(b, grid)
        if bq <= prev:           # 단조 증가 보장
            bq = prev + grid
        bq = round(bq, 6)        # 미세 오차 제거
        fixed.append(bq)
        prev = bq

    if total_beats is not None:
        total_beats = quantize(total_beats, grid)
        while fixed and fixed[-1] > total_beats:
            melodies.pop(); dynamics.pop(); lyrics.pop(); fixed.pop()
        if not fixed or fixed[-1] < total_beats:
            melodies.append(["rest"])
            dynamics.append("mp")
            lyrics.append("")
            fixed.append(total_beats)

    return melodies, fixed, dynamics, lyrics