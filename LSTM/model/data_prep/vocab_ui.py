# LSTM/model/data_prep/vocab_ui.py
# UI가 허용하는 품질: maj, min, 7, sus4, dim, aug, 5
ALLOWED_QUALS = ["maj", "min", "7", "sus4", "dim", "aug", "5"]

# 12개 루트 (반음 이동용)
ROOTS = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
ENHARM = {"Db":"C#","Eb":"D#","Gb":"F#","Ab":"G#","Bb":"A#"}

def to_root_qual(token: str):
    token = token.strip()
    if not token: return None, None
    # 루트/품질 분리
    root = token[:2] if len(token)>=2 and token[1] in "#b" else token[:1]
    qual = token[len(root):]
    root = ENHARM.get(root, root)
    return root, qual

def to_ui_qual(qual: str) -> str:
    q = qual.lower().replace(" ", "")
    # 넓은 표기 → UI 축소
    if q in ("", "maj", "maj6", "6", "maj9","maj11","maj13","add9","add11","add13"): return "maj"
    if q in ("m","min","min6","m6","m9","m11","m13"): return "min"
    if "m7b5" in q or "ø" in q or "dim7" in q or "dim" in q: return "dim"
    if "aug" in q or "+5" in q or "#5" in q: return "aug"
    if "sus" in q: return "sus4"
    if "7" in q:   return "7"
    if "5" == q:   return "5"
    return "maj"   # 디폴트

def to_ui_token(token: str):
    r,q = to_root_qual(token)
    if r is None: return None
    return r + to_ui_qual(q)

def transpose(token: str, semitones: int):
    r,q = to_root_qual(token)
    if r is None: return None
    i = ROOTS.index(r)
    r2 = ROOTS[(i + semitones) % 12]
    return r2 + to_ui_qual(q)