# SongMaker/Patterns_Jazz/Lead/jazzPointLines.py
from fractions import Fraction
import random

SEMITONES = {'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'F':5,'F#':6,'Gb':6,'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,'B':11}

def _parse_root(ch):
    if len(ch) >= 2 and ch[1] in ['#','b']:
        return ch[:2]
    return ch[:1]

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

def _target_tones(chord):
    """현재 코드에서 포인트로 쓰기 좋은 음(9, 3, 5, 6 위주) 반환 (pitch class 리스트)"""
    root = _parse_root(chord)
    qual = _quality(chord)
    r = SEMITONES.get(root, 0)

    if qual == 'maj7':
        pool = [r+14, r+4, r+7, r+9]      # 9, 3, 5, 6
    elif qual == 'm7':
        pool = [r+14, r+3, r+7, r+10]     # 9, b3, 5, b7
    elif qual == '7':
        pool = [r+14, r+4, r+10, r+7]     # 9, 3, b7, 5
    elif qual == 'dim':
        pool = [r+3, r+6, r+9]            # b3, b5, bb7(=6)
    elif qual == 'sus':
        pool = [r+5, r+7, r+14]           # 4, 5, 9
    else:  # triad 등
        pool = [r+4, r+7, r+14]           # 3, 5, 9

    return [p % 12 for p in pool]

def _choose_note(pc_list, octave=5):
    pc = random.choice(pc_list)
    return _pc_to_note(pc, octave)

def _append(mel, be, dyn, lyr, cur, notes, dur, d='mp'):
    if not notes:
        notes = ['rest']
    mel.append(notes if isinstance(notes, list) else [notes])
    cur += dur
    be.append(float(cur))  # music21 쪽에서 Fraction도 OK이지만 float로 고정
    dyn.append(d)
    lyr.append("")
    return cur

def generate_point_line(
    chords,
    phrase_len=4,
    density='sparse',     # 'sparse' | 'light' | 'medium'
    seed=None,
    mid_prob=None,        # 중간마디 2& 히트 확률 (override)
    cad_prob=None,        # 프레이즈 끝 리크 확률 (override)
    pickup_prob=0.6       # 프레이즈 끝에서 4박에 8분 리크 넣을 확률
):
    if seed is not None:
        random.seed(seed)

    # 기본 확률 테이블(살짝 더 촘촘하게)
    if density == 'sparse':
        base_mid, base_cad = 0.15, 0.85
    elif density == 'light':
        base_mid, base_cad = 0.30, 0.92
    elif density == 'medium':
        base_mid, base_cad = 0.45, 0.96
    else:
        base_mid, base_cad = 0.30, 0.92

    mid_p = base_mid if mid_prob is None else mid_prob
    cad_p = base_cad if cad_prob is None else cad_prob

    mel, be, dyn, lyr = [], [], [], []
    cur = Fraction(0, 1)

    for i, ch in enumerate(chords, start=1):
        tones = _target_tones(ch)
        is_cad = (i % phrase_len) == 0

        # beat 1
        cur = _append(mel, be, dyn, lyr, cur, 'rest', 1.0, 'mp')

        # beat 2  (가끔 2&에 한 번)
        if random.random() < mid_p:
            cur = _append(mel, be, dyn, lyr, cur, 'rest', 0.5, 'mp')       # 2
            note_2and = _choose_note(tones, octave=5)
            cur = _append(mel, be, dyn, lyr, cur, note_2and, 0.5, 'mp')    # 2&
        else:
            cur = _append(mel, be, dyn, lyr, cur, 'rest', 1.0, 'mp')

        # beat 3
        cur = _append(mel, be, dyn, lyr, cur, 'rest', 1.0, 'mp')

        # beat 4  (프레이즈 끝이면 접근→타깃, 아니면 가끔 4&에 한 번)
        if is_cad and random.random() < cad_p:
            approach = _choose_note(tones, octave=5)
            target   = _choose_note(tones, octave=5)
            if random.random() < pickup_prob:
                cur = _append(mel, be, dyn, lyr, cur, approach, 0.5, 'mp') # 4
                cur = _append(mel, be, dyn, lyr, cur, target,   0.5, 'mf') # 4&
            else:
                cur = _append(mel, be, dyn, lyr, cur, 'rest',    0.5, 'mp')
                cur = _append(mel, be, dyn, lyr, cur, target,    0.5, 'mf')
        else:
            if random.random() < (mid_p * 0.5):
                cur = _append(mel, be, dyn, lyr, cur, 'rest', 0.5, 'mp')
                hit_4and = _choose_note(tones, octave=5)
                cur = _append(mel, be, dyn, lyr, cur, hit_4and, 0.5, 'mp')
            else:
                cur = _append(mel, be, dyn, lyr, cur, 'rest', 1.0, 'mp')

    return mel, be, dyn, lyr