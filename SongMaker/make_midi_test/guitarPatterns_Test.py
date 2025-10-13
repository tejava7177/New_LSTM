# make_midi_test/guitarPatterns_Test.py
# -*- coding: utf-8 -*-
from typing import List, Tuple, Optional, Union
import random
from music21 import harmony, pitch as m21pitch

# 기타 안전 레인지 대략 (E2 ~ D5)
E2, D5 = 40, 74

def _fit_register(midi: int, low: int = E2, high: int = D5) -> int:
    """주어진 MIDI 번호를 기타 레인지로 옮겨 맞춤(옥타브 시프팅)."""
    if midi is None:
        return 64  # E4 fallback
    while midi < low:
        midi += 12
    while midi > high:
        midi -= 12
    return midi

def _parse_chord_symbol(sym: Optional[str]) -> harmony.ChordSymbol:
    """music21 파싱 실패 대비: 루트만 가진 단순 코드로 폴백."""
    try:
        s = sym.strip() if sym else "C"
        cs = harmony.ChordSymbol(s)
        if not cs.pitches:
            cs = harmony.ChordSymbol(s[0].upper())
        return cs
    except Exception:
        return harmony.ChordSymbol("C")

def _tension_candidates(cs: harmony.ChordSymbol, root_m: int) -> List[int]:
    """9th/13th 중심의 텐션 후보(질감만 살짝). 숫자 MIDI 반환."""
    tens: List[int] = []
    tens.append(root_m + 14)  # 9th
    tens.append(root_m + 21)  # 13th
    return tens

def generate_guitar_points(
    chords: List[str],
    seed: Optional[int] = None,
    per_bar_minmax: Tuple[int, int] = (1, 2),  # 마디당 단일 노트 개수 범위
    register_low: int = 52,   # G3
    register_high: int = 76,  # E5
    tension_prob: float = 0.20,  # 텐션 채택 확률
) -> Tuple[List[List[str]], List[float], List[Union[int, str]], List[str]]:
    """
    재즈스러운 '포인트 노트'만 생성(각 이벤트는 단일 음).
    Returns:
      melodies: List[List[str]]  # [['E4'], ['A4'], ...] 형태
      beat_ends: List[float]
      dynamics: List[int|str]
      lyrics: List[str]
    """
    r = random.Random(seed)
    m: List[List[str]] = []
    b: List[float] = []
    d: List[Union[int, str]] = []
    l: List[str] = []

    beat = 0.0
    for sym in chords:
        cs = _parse_chord_symbol(sym)
        try:
            root_m = int(cs.root().midi) if cs.root() else 60
        except Exception:
            root_m = 60

        # 코드톤 후보 (R, 3, 5, 7)
        is_maj = (cs.isMajorTriad() or ('maj' in (cs.figure or '').lower()))
        third   = root_m + (4 if is_maj else 3)
        fifth   = root_m + 7
        seventh = root_m + (11 if ('maj7' in (cs.figure or '').lower() or 'Δ' in (cs.figure or '')) else 10)
        chord_midis = [root_m, third, fifth, seventh]

        # 텐션 후보 (낮은 확률로 섞기)
        tens_midis = _tension_candidates(cs, root_m)

        # 스윙 포인트 위치 후보에서 1~2개 추출
        pos_pool = [0.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        r.shuffle(pos_pool)
        n_notes = r.randint(per_bar_minmax[0], per_bar_minmax[1])
        picks = sorted(pos_pool[:n_notes])

        bar_start, bar_end = beat, beat + 4.0
        last_end = bar_start

        for idx, pos in enumerate(picks):
            pool = (tens_midis + chord_midis) if r.random() < tension_prob else chord_midis
            note_m = _fit_register(r.choice(pool), register_low, register_high)
            note_name = m21pitch.Pitch(note_m).nameWithOctave

            onset = bar_start + pos
            dur   = r.choice([0.25, 0.5])  # 짧게만
            end   = min(max(onset + dur, last_end + 0.1), bar_end - 1e-6)

            m.append([note_name])                  # ★ 단일음 이벤트
            b.append(end)
            d.append(80 + (6 if idx == 0 else 0))  # 첫 음 살짝 강조
            l.append("gtr_point")
            last_end = end

        beat += 4.0

    return m, b, d, l