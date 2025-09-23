import re

QUAL_MAP = [
    (r'maj9|maj11|maj13', 'maj7'),
    (r'maj7', 'maj7'),
    (r'min9|min11|min13|m9|m11|m13', 'm7'),
    (r'min7|m7', 'm7'),
    (r'dim7', 'dim7'),
    (r'ø|m7b5|half[-_ ]?dim', 'm7b5'),
    (r'7(b5|#5|b9|#9|b13|#11|sus|alt)?', '7'),  # 장식은 접어 7로
    (r'sus2|sus4|sus', 'sus'),
    (r'add\d+', ''),          # add장식 제거
    (r'6|69', '6'),
]

NOTE_MAP = {'Db':'C#','Eb':'D#','Gb':'F#','Ab':'G#','Bb':'A#'}  # 간단한 이명동음 통일

def normalize_chord(token: str) -> str:
    token = token.strip()
    # 루트 음 통일
    m = re.match(r'^([A-G][b#]?)(.*)$', token)
    if not m: return token
    root, qual = m.groups()
    root = NOTE_MAP.get(root, root)
    qual = qual.replace(' ', '')
    for pat, rep in QUAL_MAP:
        qual = re.sub(pat, rep, qual)
    qual = re.sub(r'[^A-Za-z0-9#b]+','', qual)
    return root + qual if qual else root

def is_jazzy(seq):
    # 7계열 비율 체크
    jazzy = sum(1 for t in seq if any(q in t for q in ('7','maj7','m7','m7b5','dim7')))
    return jazzy / max(1,len(seq)) >= 0.4

def too_repetitive(seq):
    if len(seq) < 8: return True
    uniq_ratio = len(set(seq)) / len(seq)
    if uniq_ratio < 0.2: return True
    # 동일 코드 4연속 이상 금지
    run = 1
    for a,b in zip(seq, seq[1:]):
        run = run+1 if a==b else 1
        if run >= 4: return True
    return False

def chunk_8to16(seq):
    # 4/4 기준 코드당 1마디라고 가정 → 8~16마디 블록으로 슬라이딩
    out=[]
    for L in (8,12,16):
        for i in range(0, len(seq)-L+1, L):
            out.append(seq[i:i+L])
    return out