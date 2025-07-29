# jazzPianoPatterns.py 안에 추가
from fractions import Fraction
import random

def _swing_pair():
    return Fraction(2,3), Fraction(1,3)

def _append(mel, be, dyn, lyr, cur, notes, dur, d='mf'):
    if not notes:
        notes = ["rest"]
    mel.append(notes)
    cur += dur
    be.append(cur)
    dyn.append(d)
    lyr.append("")
    return cur

def _parse_root(ch):
    if len(ch) >= 2 and ch[1] in ['#', 'b']:
        return ch[:2]
    return ch[:1]

SEMITONES = {'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'F':5,'F#':6,'Gb':6,'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,'B':11}

def _quality(s):
    s = s.lower()
    if 'maj7' in s or 'ma7' in s or 'maj' in s: return 'maj7'
    if 'm7' in s or ('m' in s and 'maj' not in s and 'dim' not in s): return 'm7'
    if 'dim' in s or 'o' in s: return 'dim'
    if 'sus' in s: return 'sus'
    if '7' in s:   return '7'
    if '6' in s:   return '6'
    return 'triad'

def _pc_to_note(pc, octv):
    NAME = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    return f"{NAME[pc%12]}{octv}"

def _choose_register(pcs, center_oct=4):
    # 상중음역(4~5옥타브)에 묶어서 EP가 “얇게” 들리도록
    return [_pc_to_note(pc, center_oct if i<2 else center_oct+1) for i, pc in enumerate(pcs)]

def _voicing_shell(chord):
    root = _parse_root(chord)
    qual = _quality(chord)
    if root not in SEMITONES: root = 'C'
    r = SEMITONES[root]
    i3 = r + (3 if qual in ['m7','dim'] else 4)
    i7 = r + (10 if qual in ['7','m7','dim'] else 11)
    i9 = r + 14
    pcs = [i3%12, i7%12]
    if random.random() < 0.35:
        pcs.append(i9%12)
    return _choose_register(pcs, center_oct=4)

def style_bass_backing_minimal(chords, phrase_len=4, seed=None):
    """
    베이스 백킹 트랙용 미니멀 EP 컴핑:
      - 스윙 그리드(2/3,1/3), 2/4에만 주로 히트
      - 프레이즈 마지막 마디(예: 4, 8, …) 4&에 아주 짧은 마커
    반환: melodies, beat_ends, dynamics, lyrics
    """
    if seed is not None:
        random.seed(seed)

    mel, be, dyn, lyr = [], [], [], []
    cur = Fraction(0,1)
    d1, d2 = _swing_pair()  # 2/3, 1/3

    for bar_idx, ch in enumerate(chords, start=1):
        V = _voicing_shell(ch)

        # beat1: 전부 쉼 → 베이스 공간
        cur = _append(mel, be, dyn, lyr, cur, ["rest"], d1, 'mp')
        cur = _append(mel, be, dyn, lyr, cur, ["rest"], d2, 'mp')

        # beat2: 주 히트(강세는 살짝만)
        cur = _append(mel, be, dyn, lyr, cur, V, d1, 'mf')
        # 2& 는 대부분 쉼 (가끔 탑노트 15~20%)
        if random.random() < 0.2:
            cur = _append(mel, be, dyn, lyr, cur, [V[-1]], d2, 'mp')
        else:
            cur = _append(mel, be, dyn, lyr, cur, ["rest"], d2, 'mp')

        # beat3: 대체로 쉼
        cur = _append(mel, be, dyn, lyr, cur, ["rest"], d1, 'mp')
        # 3& 아주 가끔 약한 탑노트(10%)
        if random.random() < 0.1:
            cur = _append(mel, be, dyn, lyr, cur, [V[-1]], d2, 'mp')
        else:
            cur = _append(mel, be, dyn, lyr, cur, ["rest"], d2, 'mp')

        # beat4: 주 히트
        cur = _append(mel, be, dyn, lyr, cur, V, d1, 'mf')

        # 4&: 프레이즈 마지막 바에만 '짧은 마커(탑노트 단발)'
        if (bar_idx % phrase_len) == 0 and random.random() < 0.8:
            cur = _append(mel, be, dyn, lyr, cur, [V[-1]], d2, 'mf')
        else:
            # 그 외에는 대부분 쉼(가끔 10%만 탑노트)
            if random.random() < 0.1:
                cur = _append(mel, be, dyn, lyr, cur, [V[-1]], d2, 'mp')
            else:
                cur = _append(mel, be, dyn, lyr, cur, ["rest"], d2, 'mp')

    return mel, be, dyn, lyr

