# Patterns_Pop/Keys/popKeysPatterns.py
import random

def chord_notes_map(ch):
    base = {
        "C":["C4","E4","G4","E4"], "G":["G3","B3","D4","B3"],
        "Am":["A3","C4","E4","C4"], "F":["F3","A3","C4","A3"],
        "D":["D3","F#3","A3","F#3"], "Em":["E3","G3","B3","G3"], "Bm":["B2","D3","F#3","D3"],
        "E":["E3","G#3","B3","G#3"]
    }
    return base.get(ch, ["C4","E4","G4","E4"])

def _emit(mel, beats, dyn, lyr, t, pitches, dur, vel="mp"):
    if isinstance(pitches, str):
        pitches = [pitches]
    t += dur
    mel.append(pitches); beats.append(t); dyn.append(vel); lyr.append("")
    return t

def generate_pop_keys(chords, style="pad_block", add_shell=True, seed=None):
    """
    style: 'pad_block' | 'pop_arp' | 'broken8'
      - pad_block: 코드 패드식(길이 다양) + (옵션) 2&4 쉘 보이싱 on-top
      - pop_arp  : 8분 아르페지오
      - broken8  : 분산코드 8분
    """
    if seed is not None:
        random.seed(seed)

    mel, beats, dyn, lyr = [], [], [], []
    t = 0.0

    for ch in chords:
        notes = chord_notes_map(ch)

        if style == "pad_block":
            # 2박 유지 + 2박 유지 → 한 마디 두 번
            for _ in range(2):
                t = _emit(mel, beats, dyn, lyr, t, notes, 2.0, vel="mp")
            if add_shell:
                # 2,4 박의 후반(앤드)에 8분 쉘 보이싱(3rd/7th) 살짝
                shell = [notes[1], notes[3]] if len(notes) >= 4 else notes[:2]
                # 박자 2& (한 마디마다 한 번, 두 번째 블록 막판에 붙임)
                mel[-1] = mel[-1]  # no-op, 가독성
                # 앤드에 얹는 방식: 짧게 한 번 더
                mel.append(shell);   beats.append(beats[-1]); dyn.append("mp"); lyr.append("")
        elif style == "pop_arp":
            for _ in range(2):  # 마디당 8개(8분)
                order = [0,1,2,1]
                for idx in order:
                    t = _emit(mel, beats, dyn, lyr, t, [notes[idx % len(notes)]], 0.5, vel="mp")
        elif style == "broken8":
            order = [0,2,1,2,  0,1,2,1]
            for idx in order:
                t = _emit(mel, beats, dyn, lyr, t, [notes[idx % len(notes)]], 0.5, vel="mp")
        else:
            raise ValueError("Unsupported POP keys style.")

    return mel, beats, dyn, lyr