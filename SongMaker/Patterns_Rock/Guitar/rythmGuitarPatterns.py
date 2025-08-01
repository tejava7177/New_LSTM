# SongMaker/Patterns_Rock/Guitar/rhythmGuitarPatterns.py
import random

def chord_notes_map(ch):
    base = {
        "C": ["C3","E3","G3"], "G": ["G3","B3","D4"], "Am":["A3","C4","E4"], "F":["F3","A3","C4"],
        "D": ["D3","F#3","A3"], "Em":["E3","G3","B3"], "Bm":["B2","D3","F#3"], "E":["E3","G#3","B3"]
    }
    return base.get(ch, ["C3","E3","G3"])

def _emit(ev, t, pitches, dur):
    if isinstance(pitches, str): pitches=[pitches]
    ev.append((pitches, t+dur)); return t+dur

def generate_rock_rhythm_guitar(chords, style="power8", chug_prob=0.3, accent="2&4"):
    """
    style: "power8" | "sync16" | "offChop"
      - power8 : 8분 파워코드(루트+5도)
      - sync16 : 16분 싱코페이션(백비트/앤드 강조)
      - offChop: 오프비트 체프(앤드에 짧게)
    """
    mel=[]; beats=[]; dyn=[]; lyr=[]; t=0.0

    for ch in chords:
        notes = chord_notes_map(ch)
        power = [notes[0], notes[2]]  # R+5th 간단 파워코드

        if style == "power8":
            for i in range(8):
                dur=0.5
                pitches = power
                # 약간의 척(chug) — 2,4박 전후로 16분 짧게 끊거나 추가
                if random.random() < chug_prob and i in (1,3,5,7):
                    pitches = power  # 동일 음
                t = _emit(mel, t, pitches, dur); beats.append(t); dyn.append("f" if i in (2,6) else "mf"); lyr.append("")

        elif style == "sync16":
            # | 1e & a | 2e & a | ... : 백비트와 & 에 길이 부여
            pattern = [0.25,0.25,0.5,0.25, 0.25,0.25,0.5,0.25,
                       0.25,0.25,0.5,0.25, 0.25,0.25,0.5,0.25]
            for idx,d in enumerate(pattern):
                hits = power if (idx%4 in (2,) or idx%4==1) else power
                t = _emit(mel, t, hits, d); beats.append(t); dyn.append("mf"); lyr.append("")

        elif style == "offChop":
            # 앤드(오프비트)에만 짧게(체프) + 4박 마감 길게
            for beat in range(4):
                # “앤드”만 짧게
                t = _emit(mel, t, ["rest"], 0.5)  # 다운은 비움
                t = _emit(mel, t, power, 0.5)     # & 에 체프
                beats.extend([beats[-1] if beats else t-0.5, t])  # 보정(필요시)
                dyn.extend(["mp","mf"]); lyr.extend(["",""])
            # 4박 마지막은 살짝 길게 유지해도 좋음 (이미 4/4 맞춤)

    return mel, beats, dyn, lyr