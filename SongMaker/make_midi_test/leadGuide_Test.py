# make_midi_test/leadGuide_Test.py
# -*- coding: utf-8 -*-
from typing import List, Tuple, Optional, Union
import random
from music21 import harmony, pitch as m21pitch

def _parse_cs(sym: Optional[str]) -> harmony.ChordSymbol:
    try:
        s = sym.strip() if sym else "C"
        cs = harmony.ChordSymbol(s)
        if not cs.pitches:
            cs = harmony.ChordSymbol(s[0].upper())
        return cs
    except Exception:
        return harmony.ChordSymbol("C")

def _fit_register(midi: int, low: int, high: int) -> int:
    if midi is None:
        midi = 72  # C5 fallback
    while midi < low:
        midi += 12
    while midi > high:
        midi -= 12
    return midi

def _pick_tones(cs: harmony.ChordSymbol) -> List[int]:
    try:
        root_m = int(cs.root().midi) if cs.root() else 60
    except Exception:
        root_m = 60
    fig = (cs.figure or "").lower()
    is_maj = ("maj" in fig) or cs.isMajorTriad()
    third   = root_m + (4 if is_maj else 3)
    fifth   = root_m + 7
    seventh = root_m + (11 if ("maj7" in fig or "Δ" in fig) else 10)
    ninth   = root_m + 14
    thirteenth = root_m + 21
    return [root_m, third, fifth, seventh, ninth, thirteenth]

def generate_lead_sax_points(
    chords: List[str],
    seed: Optional[int] = None,
    per_bar_minmax: Tuple[int, int] = (1, 1),   # 기본: 마디당 1음
    register_low: int = 64,    # E4
    register_high: int = 81,   # A5-
    tension_prob: float = 0.10 # 텐션(9,13) 사용 낮춤
) -> Tuple[List[List[str]], List[float], List[Union[int, str]], List[str]]:
    """
    단일음 중심의 '가이드 멜로디'(색소폰 느낌).
    각 이벤트는 [음이름] 한 개만 포함. beat_end는 절대시간(박 단위).
    """
    r = random.Random(seed)
    melodies: List[List[str]] = []
    beat_ends: List[float] = []
    dynamics: List[Union[int, str]] = []
    lyrics:   List[str] = []

    beat = 0.0
    n_bars = len(chords)
    for i, sym in enumerate(chords):
        cs_now  = _parse_cs(sym)
        cs_next = _parse_cs(chords[i+1]) if (i+1) < n_bars else cs_now

        tones = _pick_tones(cs_now)
        core      = tones[:4]    # R,3,5,7
        tensions  = tones[4:]    # 9,13

        # 포인트 위치 후보(재즈스럽게): downbeat+anticipation 쪽만
        pos_pool = [0.0, 2.5, 3.0, 3.5]
        r.shuffle(pos_pool)
        n_notes = max(per_bar_minmax[0], min(per_bar_minmax[1], 1))  # 안전장치
        picks = sorted(pos_pool[:n_notes])

        bar_start, bar_end = beat, beat + 4.0
        last_end = bar_start

        for j, pos in enumerate(picks):
            pool = core + tensions if (r.random() < tension_prob) else core
            pitch_m = _fit_register(r.choice(pool), register_low, register_high)
            name = m21pitch.Pitch(pitch_m).nameWithOctave

            onset = bar_start + pos
            dur   = r.choice([0.25, 0.5, 0.75])  # 짧게만
            end   = min(max(onset + dur, last_end + 0.10), bar_end - 1e-6)

            melodies.append([name])
            beat_ends.append(end)
            dynamics.append(78 + (6 if j == 0 else 0))  # 첫음 살짝 강조
            lyrics.append("sax_point")
            last_end = end

        # 픽업(낮은 확률, 짧게) — 겹침 방지
        if (i+1) < n_bars and r.random() < 0.15:
            try:
                target_root = int(cs_next.root().midi) if cs_next.root() else 60
            except Exception:
                target_root = 60
            pickup = target_root + (1 if r.random() < 0.5 else -1)
            pickup = _fit_register(pickup, register_low, register_high)
            name   = m21pitch.Pitch(pickup).nameWithOctave

            onset = bar_end - 0.5
            if beat_ends and onset <= beat_ends[-1]:
                onset = min(bar_end - 0.25, beat_ends[-1] + 0.12)
            end   = min(bar_end - 1e-6, onset + 0.25)

            melodies.append([name])
            beat_ends.append(end)
            dynamics.append(82)
            lyrics.append("pickup")

        beat += 4.0

    return melodies, beat_ends, dynamics, lyrics