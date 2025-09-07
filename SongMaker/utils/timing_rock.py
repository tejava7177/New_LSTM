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


def clip_and_fill_rests(
    melodies: List[List[str]],
    beat_ends: List[float],
    dynamics: List[str],
    lyrics: List[str],
    *,
    bar_len: float = 4.0,
    total_beats: Optional[float] = None,
    grid: float = 0.25,
) -> Tuple[List[List[str]], List[float], List[str], List[str]]:
    """
    각 노트의 지속시간이 bar_len(기본 4.0 beat)을 초과하면 bar_len 단위로 분할.
    중간 경계에는 placeholder rest를 삽입하여 리더블하게 맞춘다.
    fix_beats() 이후에 호출하는 것을 권장.
    """
    if not beat_ends:
        return melodies, beat_ends, dynamics, lyrics

    new_mel, new_be, new_dyn, new_lyr = [], [], [], []
    prev = 0.0

    for i, end in enumerate(beat_ends):
        dur = end - prev
        cur_mel, cur_dyn, cur_lyr = melodies[i], dynamics[i], lyrics[i]

        # 필요 시 여러 마디에 걸친 노트를 분할
        while dur > bar_len + 1e-6:
            split_at = prev + bar_len
            # 첫 조각: 기존 노트 유지
            new_mel.append(cur_mel)
            new_dyn.append(cur_dyn)
            new_lyr.append(cur_lyr)
            new_be.append(round(split_at, 6))

            # 다음 구간으로 이동
            prev = split_at
            dur = end - prev

            # 경계 구간에 placeholder rest 삽입 (가독성/도구 호환성)
            rest_end = min(prev + grid, end)  # 너무 짧지 않게 grid만큼
            new_mel.append(["rest"])
            new_dyn.append("mp")
            new_lyr.append("")
            new_be.append(round(rest_end, 6))
            prev = rest_end
            dur = end - prev

        # 남은 마지막 조각(정상 길이)
        if end > prev:
            new_mel.append(cur_mel)
            new_dyn.append(cur_dyn)
            new_lyr.append(cur_lyr)
            new_be.append(round(end, 6))
            prev = end

    # 총 길이 맞추기(옵션)
    if total_beats is not None:
        total_beats = quantize(total_beats, grid)
        # 초과분 잘라내기
        while new_be and new_be[-1] > total_beats + 1e-6:
            new_mel.pop(); new_dyn.pop(); new_lyr.pop(); new_be.pop()
        # 부족하면 rest로 채우기
        if not new_be or new_be[-1] < total_beats - 1e-6:
            new_mel.append(["rest"])
            new_dyn.append("mp")
            new_lyr.append("")
            new_be.append(total_beats)

    return new_mel, new_be, new_dyn, new_lyr