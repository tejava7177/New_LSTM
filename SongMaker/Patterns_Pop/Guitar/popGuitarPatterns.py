# Patterns_Pop/Guitar/popGuitarPatterns.py
import random

def chord_notes_map(ch):
    base = {
        "C":["C3","E3","G3"], "G":["G3","B3","D4"], "Am":["A3","C4","E4"], "F":["F3","A3","C4"],
        "D":["D3","F#3","A3"], "Em":["E3","G3","B3"], "Bm":["B2","D3","F#3"], "E":["E3","G#3","B3"]
    }
    return base.get(ch, ["C3","E3","G3"])

def _emit(mel, beats, dyn, lyr, t, pitches, dur, vel="mf"):
    if isinstance(pitches, str):
        pitches = [pitches]
    t += dur
    mel.append(pitches); beats.append(t); dyn.append(vel); lyr.append("")
    return t

def generate_pop_rhythm_guitar(chords, style="pm8", seed=None):
    """
    style: 'pm8' | 'clean_arp' | 'chop_off'
      - pm8     : 팜뮤트 8분 스트럼(루트+5도 위주)
      - clean_arp: 클린 아르페지오 8분
      - chop_off : 오프비트(앤드) 짧은 체프
    """
    if seed is not None:
        random.seed(seed)

    mel, beats, dyn, lyr = [], [], [], []
    t = 0.0
    for ch in chords:
        notes = chord_notes_map(ch)
        power = [notes[0], notes[2]]  # 루트+5도 (팝 톤 절제)

        if style == "pm8":
            for i in range(8):
                vel = "mf" if i in (2,6) else "mp"
                t = _emit(mel, beats, dyn, lyr, t, power, 0.5, vel=vel)

        elif style == "clean_arp":
            order = [0,1,2,1,  0,1,2,1]
            for idx in order:
                t = _emit(mel, beats, dyn, lyr, t, [notes[idx]], 0.5, vel="mp")

        elif style == "chop_off":
            # 다운비트는 쉼, 앤드에 짧게(0.5) — 패드/드럼과 충돌 적음
            for beat in range(4):
                t = _emit(mel, beats, dyn, lyr, t, ["rest"], 0.5, vel="mp")
                t = _emit(mel, beats, dyn, lyr, t, power,   0.5, vel="mf")
        else:
            raise ValueError("Unsupported POP guitar style.")

    return mel, beats, dyn, lyr