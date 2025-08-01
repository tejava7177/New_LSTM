# SongMaker/Patterns_Rock/Piano/rockKeysPatterns.py
import random

# 간단한 코드 -> 음정 매핑
def chord_notes_map(ch):
    base = {
        "C": ["C4","E4","G4"], "G": ["G3","B3","D4"], "Am":["A3","C4","E4"], "F":["F3","A3","C4"],
        "D": ["D3","F#3","A3"], "Em":["E3","G3","B3"], "Bm":["B2","D3","F#3"], "E":["E3","G#3","B3"]
    }
    return base.get(ch, ["C4","E4","G4"])

def _emit(mel, beats, dyn, lyr, t, pitches, dur, d="mp"):
    if isinstance(pitches, str): pitches = [pitches]
    t += dur
    mel.append(pitches); beats.append(t); dyn.append(d); lyr.append("")
    return t

def _add_shell_2and4(mel, beats, dyn, lyr, t_bar_start, root, third, seventh, vel="mp"):
    """ 2, 4박 '앤드'에 8분 쉘 보이싱(3rd/7th) 작은 스탭 """
    # 2&, 4&  위치: 1.5, 3.5
    for off in (1.5, 3.5):
        mel.append([third, seventh])
        beats.append(t_bar_start + off + 0.5)  # 8분
        dyn.append(vel); lyr.append("")

def generate_rock_keys(
    chords,
    style="arp4",               # "arp4" | "blockPad" | "riffHook"
    add_shell=False,            # 2&4 쉘 보이싱 가볍게 추가
    shell_vel="mp"
):
    mel, beats, dyn, lyr = [], [], [], []
    t = 0.0

    for ch in chords:
        notes = chord_notes_map(ch)
        root, third, fifth = notes[0], notes[1], notes[2]

        if style == "arp4":
            # 마디(4박)를 8분 아르페지오로 채움: R-3-5-3 / R-3-5-3 ...
            pattern = [root, third, fifth, third, root, third, fifth, third]
            for p in pattern:
                t = _emit(mel, beats, dyn, lyr, t, p, 0.5, d="mp")
            if add_shell:
                _add_shell_2and4(mel, beats, dyn, lyr, t - 4.0, root, third, fifth)  # fifth를 7th로 바꿔도 OK

        elif style == "blockPad":
            # 마디마다 코드 패드(2박+2박)로 받쳐주기
            t = _emit(mel, beats, dyn, lyr, t, notes, 2.0, d="mp")
            t = _emit(mel, beats, dyn, lyr, t, notes, 2.0, d="mp")
            if add_shell:
                _add_shell_2and4(mel, beats, dyn, lyr, t - 4.0, root, third, fifth)

        elif style == "riffHook":
            # 간단한 훅(록에서 자주 쓰는 루트-5도-6도-5도 느낌)
            # 루트는 옥타브 아래, 나머지는 근처
            r_lo = root[:-1] + str(int(root[-1]) - 1) if root[-1].isdigit() else root
            sixth = {"C":"A3","G":"E3","F":"D3","Am":"F4","Em":"C4"}.get(ch, third)
            seq = [r_lo, fifth, sixth, fifth, r_lo, fifth, third, root]
            for p in seq:
                t = _emit(mel, beats, dyn, lyr, t, p, 0.5, d="mf")
            if add_shell:
                _add_shell_2and4(mel, beats, dyn, lyr, t - 4.0, root, third, fifth)

        else:
            # 기본: blockPad
            t = _emit(mel, beats, dyn, lyr, t, notes, 2.0, d="mp")
            t = _emit(mel, beats, dyn, lyr, t, notes, 2.0, d="mp")

    return mel, beats, dyn, lyr