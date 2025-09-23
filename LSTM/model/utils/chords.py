# LSTM/model/utils/chords.py
import re

_PITCH_PC = {
    "C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,
    "G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11
}

_ENHARM_JAZZ = {"G#":"Ab", "D#":"Eb", "A#":"Bb"}  # 재즈 표기 선호

_BAD_SHARP_MAJ = {"G#", "D#", "A#"}

def parse_chord(ch):
    """'Cmaj7' -> ('C','maj7'), 'G5' -> ('G','5')"""
    if not ch:
        return None, ""
    m = re.match(r'^([A-G](?:#|b)?)(.*)$', ch.strip())
    if not m:
        return None, ""
    root, qual = m.group(1), (m.group(2) or "").strip()
    return root, qual

def pc(root):
    return _PITCH_PC.get(root, None)

def down_fifth(a_root, b_root):
    """a -> b가 완전5도 하행(=4도 상행)인지"""
    pa, pb = pc(a_root), pc(b_root)
    if pa is None or pb is None:
        return False
    return (pa - pb) % 12 == 7

def is_seventh_quality(qual):
    q = (qual or "").lower()
    return ("7" in q) or ("ø" in q) or ("dim7" in q) or ("m7b5" in q)

def is_power_or_plain(qual):
    q = (qual or "").lower()
    if "5" in q:  # 파워코드
        return True
    # 7/9/11/13/ø/°/dim/aug/sus 등이 없으면 '맨몸'으로 간주
    return (("7" not in q) and all(k not in q for k in ["9","11","13","ø","°","dim","aug","sus"]))

def norm_enharm_jazz(ch):
    r, q = parse_chord(ch)
    if not r:
        return ch
    if r in _ENHARM_JAZZ:
        r = _ENHARM_JAZZ[r]
    return r + (q or "")

def is_bad_sharp_maj(ch):
    r, q = parse_chord(ch)
    if not r:
        return False
    ql = (q or "").lower()
    return (r in _BAD_SHARP_MAJ) and ("maj" in ql or q == "")