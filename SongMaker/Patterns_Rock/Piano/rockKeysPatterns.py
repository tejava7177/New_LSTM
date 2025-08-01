# SongMaker/Patterns_Rock/Keys/rockKeysPatterns.py
import random

def chord_to_arp_notes(ch):
    base = {
        "C":["C4","E4","G4","E4"], "G":["G3","B3","D4","B3"], "Am":["A3","C4","E4","C4"], "F":["F3","A3","C4","A3"],
        "D":["D4","F#4","A4","F#4"], "Em":["E3","G3","B3","G3"], "E":["E3","G#3","B3","G#3"], "Bm":["B3","D4","F#4","D4"]
    }
    return base.get(ch, ["C4","E4","G4","E4"])

def _emit(ev,t,p,d): ev.append((p,t+d)); return t+d

def generate_rock_keys(chords, style="arp4", pad_prob=0.2):
    """
    style: "arp4" | "blockPad" | "riffHook"
    - arp4     : 1마디 내 4음 아르페지오(길이 랜덤화)
    - blockPad : 블록 코드(패드 느낌)
    - riffHook : 간단 훅(1마디 2~4음 반복)
    """
    mel=[]; beats=[]; dyn=[]; lyr=[]; t=0.0
    for ch in chords:
        notes = chord_to_arp_notes(ch)
        if style=="arp4":
            durs = random.choice([[1.0,1.0,1.0,1.0],[0.5,0.5,1.0,2.0],[0.75,0.75,0.5,2.0]])
            idx=0
            for d in durs:
                p = notes[idx%len(notes)]; t = _emit(mel,t,p,d); beats.append(t); dyn.append("mp"); lyr.append(""); idx+=1
        elif style=="blockPad":
            # 2박+2박 or 4박 유지
            if random.random() < pad_prob:
                t = _emit(mel,t,notes,2.0); beats.append(t); dyn.append("mp"); lyr.append("")
                t = _emit(mel,t,notes,2.0); beats.append(t); dyn.append("mp"); lyr.append("")
            else:
                t = _emit(mel,t,notes,4.0); beats.append(t); dyn.append("mp"); lyr.append("")
        else:  # riffHook
            riff = [notes[0], notes[1], notes[0], notes[2]]
            for d in [0.5,0.5,1.0,2.0]:
                p = riff[0]; riff = riff[1:]+riff[:1]
                t = _emit(mel,t,p,d); beats.append(t); dyn.append("mf"); lyr.append("")
    return mel, beats, dyn, lyr