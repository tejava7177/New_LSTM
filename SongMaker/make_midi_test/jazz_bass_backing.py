# -*- coding: utf-8 -*-
# Standalone: music21만 필요. 재즈 베이스 백킹 생성기
from typing import List, Tuple, Optional
import os, random
from music21 import stream, note, chord, meter, tempo, instrument, key as m21key, harmony, duration

# ===== 설정 =====
BASS_LOW, BASS_HIGH = 28, 48   # E1(28) ~ C3(48) 권장 범위

def _fit_register(m: int, low=BASS_LOW, high=BASS_HIGH) -> int:
    while m < low:  m += 12
    while m > high: m -= 12
    return m

def _parse_cs(sym: str) -> harmony.ChordSymbol:
    s = (sym or "C").strip()
    try:
        cs = harmony.ChordSymbol(s)
        if not cs.pitches:  # 안전 폴백
            cs = harmony.ChordSymbol(s[0].upper())
        return cs
    except Exception:
        return harmony.ChordSymbol("C")

def _root_midi(cs: harmony.ChordSymbol) -> int:
    try:
        return int(cs.root().midi)
    except Exception:
        return 60  # C4

def _chord_tones(cs: harmony.ChordSymbol) -> List[int]:
    r = _root_midi(cs)
    fig = (cs.figure or "").lower()
    is_maj = ("maj" in fig) or cs.isMajorTriad()
    third   = r + (4 if is_maj else 3)
    fifth   = r + 7
    seventh = r + (11 if ("maj7" in fig or "Δ" in fig) else 10)
    out = [r, third, fifth, seventh]
    # dim/alt 계열 보정(무리하지 않고 5도 플랫/샤프만 가끔 대체)
    if "b5" in fig or "dim" in fig:
        out[2] = r + 6
    if "#5" in fig or "+5" in fig or "aug" in fig:
        out[2] = r + 8
    return out

def _approach_to(target: int, prev: int) -> int:
    """다음 마디 루트(target)로 가는 4박 접근음 선택(반음/전음/엔클로저)."""
    cands = [target - 1, target + 1, target - 2, target + 2, target]  # 크로매틱/디아토닉
    # 선율적 부드러움: 이전음에서 가까운 것 우선
    cands = sorted(cands, key=lambda x: abs((_fit_register(x) - _fit_register(prev))))
    return _fit_register(cands[0])

def _step_towards(prev: int, dst: int) -> int:
    """이전음에서 dst 쪽으로 2도 진행(상·하행) 우선."""
    prev = _fit_register(prev)
    dst  = _fit_register(dst)
    return _fit_register(prev + (1 if dst > prev else -1))

def _choose_tone(prev: int, tones: List[int], favor_idx=(0,2,3)) -> int:
    """루트/5도/7도 선호, 직전 음과의 도약 최소화."""
    ranked = [tones[i] for i in favor_idx if i < len(tones)] + tones
    ranked = [t for t in ranked if -24 <= (t - _fit_register(prev)) <= 24]
    ranked = ranked or tones
    ranked = sorted(ranked, key=lambda t: abs((_fit_register(t) - _fit_register(prev))))
    return _fit_register(ranked[0])

def _swing_offset(beat_idx: int, swing_ratio=0.6) -> float:
    """스윙: 8분노트 기준 앞을 길게(기본 60%) — MIDI 타이밍엔 굳이 필요 없지만, 길이 결정을 위해 사용."""
    # 여기서는 길이 산정용 가중치만 사용
    return 0.0

def _bar_notes_walking(cs_now: harmony.ChordSymbol, cs_next: harmony.ChordSymbol, prev_m: int) -> List[int]:
    """워킹 4분×4: 1박 루트, 4박 접근음, 중간은 3·5·7/스텝."""
    tones_now  = _chord_tones(cs_now)
    tones_next = _chord_tones(cs_next)
    root_now   = _fit_register(tones_now[0])
    root_next  = _fit_register(tones_next[0])
    n1 = root_now
    # 2박: 3도/7도 선호, 스텝 보정
    cand2 = _choose_tone(prev_m, tones_now, favor_idx=(3,1,2))
    n2 = _step_towards(cand2, root_next) if abs(cand2 - _fit_register(prev_m)) > 7 else cand2
    # 3박: 5도/3도 선호
    n3 = _choose_tone(n2, tones_now, favor_idx=(2,1,3))
    # 4박: 접근음
    n4 = _approach_to(root_next, n3)
    return [n1, n2, n3, n4]

def _bar_notes_twofeel(cs_now: harmony.ChordSymbol, cs_next: harmony.ChordSymbol, prev_m: int) -> List[Tuple[int, float]]:
    """two-feel: 1박 루트(하프), 3박 5도·3도(하프). 가끔 4& 접근 8분."""
    tones_now = _chord_tones(cs_now)
    root_now  = _fit_register(tones_now[0])
    fifth     = _fit_register(tones_now[2])
    third     = _fit_register(tones_now[1])
    main3 = _choose_tone(root_now, [fifth, third], favor_idx=(0,1))
    # 기본은 하프+하프, 20% 확률로 4&에 접근 8분 삽입
    return [(root_now, 2.0), (main3, 2.0)]

def _bar_notes_ballad(cs_now: harmony.ChordSymbol, cs_next: harmony.ChordSymbol, prev_m: int) -> List[Tuple[int, float]]:
    """발라드: 하프노트 위주, 마지막 8분 접근 확률적."""
    tones_now = _chord_tones(cs_now)
    r = _fit_register(tones_now[0])
    t = _choose_tone(r, tones_now, favor_idx=(3,1,2))
    return [(r, 2.0), (t, 2.0)]

def _bar_notes_bossa(cs_now: harmony.ChordSymbol, cs_next: harmony.ChordSymbol, prev_m: int) -> List[Tuple[int, float]]:
    """보사: 루트–5도 교대 + 2&/4& 살짝 전치(여기선 단순화해 하프노트)."""
    tones_now = _chord_tones(cs_now)
    r = _fit_register(tones_now[0])
    f = _fit_register(tones_now[2])
    return [(r, 2.0), (f, 2.0)]

def generate_bass_stream(
    progression: List[str],
    style: str = "walking",     # "walking"|"two_feel"|"ballad"|"bossa"
    tempo_bpm: int = 140,
    swing: bool = True,
    seed: Optional[int] = None,
) -> stream.Stream:
    rng = random.Random(seed)
    s = stream.Stream()
    s.append(tempo.MetronomeMark(number=tempo_bpm))
    s.append(meter.TimeSignature("4/4"))
    s.append(instrument.AcousticBass())

    # 키는 굳이 지정하지 않지만, 멜로디 처리에 도움될 수 있음
    # s.append(m21key.Key('C'))

    prev_m = _fit_register(40)  # 시작 기준(E1 근처)
    n_bars = len(progression)
    for i, sym_now in enumerate(progression):
        cs_now  = _parse_cs(sym_now)
        cs_next = _parse_cs(progression[i+1]) if i+1 < n_bars else cs_now

        if style == "walking":
            mids = _bar_notes_walking(cs_now, cs_next, prev_m)
            for m in mids:
                n = note.Note(_fit_register(m))
                n.quarterLength = 1.0
                s.append(n)
            prev_m = mids[-1]

        elif style == "two_feel":
            pairs = _bar_notes_twofeel(cs_now, cs_next, prev_m)
            for m, ql in pairs:
                n = note.Note(_fit_register(m))
                n.quarterLength = ql
                s.append(n)
            prev_m = pairs[-1][0]

        elif style == "ballad":
            pairs = _bar_notes_ballad(cs_now, cs_next, prev_m)
            for m, ql in pairs:
                n = note.Note(_fit_register(m))
                n.quarterLength = ql
                s.append(n)
            prev_m = pairs[-1][0]

        elif style == "bossa":
            pairs = _bar_notes_bossa(cs_now, cs_next, prev_m)
            for m, ql in pairs:
                n = note.Note(_fit_register(m))
                n.quarterLength = ql
                s.append(n)
            prev_m = pairs[-1][0]

        else:
            raise ValueError(f"Unknown style: {style}")

    return s

def render_bass_midi(
    progression: List[str],
    style: str = "walking",
    tempo_bpm: int = 140,
    out_dir: Optional[str] = None,
    seed: Optional[int] = None,
) -> Tuple[str, str]:
    if out_dir is None:
        base = os.path.dirname(__file__)  # make_midi_test
        out_dir = os.path.join(base, "out")
    os.makedirs(out_dir, exist_ok=True)

    s = generate_bass_stream(progression, style=style, tempo_bpm=tempo_bpm, seed=seed)

    tag = f"bass_{style}_bpm{tempo_bpm}"
    midi_path = os.path.join(out_dir, f"{tag}.mid")
    xml_path  = os.path.join(out_dir, f"{tag}.musicxml")

    s.write("midi", fp=midi_path)
    s.write("musicxml", fp=xml_path)
    return midi_path, xml_path

# ===== quick test =====
if __name__ == "__main__":
    prog = ["Cmaj7","Am7","Dm7","G7"]*2
    print(render_bass_midi(prog, style="walking", tempo_bpm=140))