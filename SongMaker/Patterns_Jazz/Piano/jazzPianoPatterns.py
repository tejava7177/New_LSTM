# SongMaker/Patterns_Jazz/Piano/jazzPianoPatterns.py
import random
from fractions import Fraction

# ------------------------------------------------------------
# 보이싱 생성 유틸 (루트 없이 3-7-9-13 중심, 또는 셸/쿼털)
# pitch 계산을 간단히 하기 위해 반음 단위 오프셋 테이블을 사용
# ------------------------------------------------------------

# C 기준 반음 오프셋
SEMITONES = {
    'C': 0, 'C#': 1, 'Db': 1,
    'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'Fb': 4, 'E#': 5,
    'F': 5, 'F#': 6, 'Gb': 6,
    'G': 7, 'G#': 8, 'Ab': 8,
    'A': 9, 'A#': 10, 'Bb': 10,
    'B': 11, 'Cb': 11, 'B#': 0,
}

# 간단한 코드유형 판별
def _quality(ch):
    s = ch.lower()
    if 'maj7' in s or 'ma7' in s or 'maj' in s:
        return 'maj7'
    if 'm7' in s or ('m' in s and 'maj' not in s and 'dim' not in s):
        return 'm7'
    if 'dim' in s or 'o' in s:        # dim, dim7, o
        return 'dim'
    if 'sus' in s:
        return 'sus'
    if '7' in s:
        return '7'
    if '6' in s:
        return '6'
    return 'triad'

def _parse_root(ch):
    # 루트만 추출 (A, Bb, F#, ...)
    if len(ch) >= 2 and ch[1] in ['#', 'b']:
        return ch[:2]
    return ch[:1]

def _pc_to_note(pc, target_oct):
    """
    pitch class(0-11)와 옥타브로 대략적인 노트명 생성
    - 옥타브는 대략 C4~B4 중심으로 보이싱 모으기 위함
    """
    NAME = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    name = NAME[pc % 12]
    return f"{name}{target_oct}"

def _choose_register(pcs, center_oct=4):
    """
    피치클래스 배열을 3~5옥타브 근처로 정리.
    보이싱을 3.5~5 사이에 모으도록 간단히 보정.
    """
    notes = []
    for i, pc in enumerate(pcs):
        # 위쪽으로 적당히 펼치기
        octv = center_oct
        # 너무 낮으면 한 옥타브 ↑
        if i > 0 and pcs[i] - pcs[i-1] < 0:  # 단순 정렬 보정
            octv += 1
        notes.append(_pc_to_note(pc, octv))
    return notes

def _voicing_rootless(chord):
    """
    루트리스 보이싱 (기본: 3-7-9-(13))
    - 베이스가 따로 있다고 가정(사용자 연주) → 피아노가 루트 생략
    """
    root = _parse_root(chord)
    qual = _quality(chord)
    if root not in SEMITONES:
        root = 'C'
    r = SEMITONES[root]

    # 반음 오프셋 (루트 기준)
    i3  = r + (3 if qual in ['m7','dim'] else 4)     # b3 or 3
    i5  = r + (6 if qual=='dim' else 7)              # b5 or 5
    i7  = r + (10 if qual in ['7','m7','dim'] else 11)  # b7 or 7
    i9  = r + 14                                     # 9
    i13 = r + 21                                     # 13

    if qual == 'dim':
        pcs = [i3%12, i5%12, i7%12]                 # dim 계열은 간결
    elif qual == 'sus':
        # sus: 4-5-b7-9 느낌
        i4 = r + 5
        pcs = [i4%12, i5%12, (r+10)%12, i9%12]
    elif qual == '6':
        # 3-6-9
        i6 = r + 9
        pcs = [i3%12, i6%12, i9%12]
    elif qual == 'maj7':
        pcs = [i3%12, i7%12, i9%12, i13%12]
    elif qual == 'm7':
        pcs = [i3%12, i7%12, i9%12, i13%12]
    elif qual == '7':
        pcs = [i3%12, i7%12, i9%12, i13%12]
    else:  # triad
        pcs = [i3%12, i5%12, i7%12]                 # 3-5-7

    return _choose_register(pcs, center_oct=4)

def _voicing_shell(chord):
    """
    셸 보이싱: 3도와 7도 중심(간혹 9 추가)
    """
    root = _parse_root(chord)
    qual = _quality(chord)
    if root not in SEMITONES:
        root = 'C'
    r = SEMITONES[root]

    i3  = r + (3 if qual in ['m7','dim'] else 4)
    i7  = r + (10 if qual in ['7','m7','dim'] else 11)
    i9  = r + 14

    pcs = [i3%12, i7%12]
    if random.random() < 0.4:
        pcs.append(i9%12)
    return _choose_register(pcs, center_oct=4)

def _voicing_quartal(chord):
    """
    4도堆積(모달풍): 루트 기준으로 4도씩 2~3개
    """
    root = _parse_root(chord)
    if root not in SEMITONES:
        root = 'C'
    r = SEMITONES[root]
    pcs = [r%12, (r+5)%12, (r+10)%12]  # 루트/4도/♭7(=4도 또 올리면 10)
    if random.random() < 0.4:
        pcs.append((r+15)%12)          # 한 번 더 4도(=9)
    return _choose_register(pcs, center_oct=4)

# ------------------------------------------------------------
# 시간/리듬 유틸
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# 스타일 템플릿
# ------------------------------------------------------------
def _style_swing_shells(chords, density="medium", seed=None):
    """
    스윙 컴핑 (셸보이싱 중심): 2,4에 강세 + 가끔 안티시페이션
    """
    if seed is not None:
        random.seed(seed)

    mel, be, dyn, lyr = [], [], [], []
    cur = Fraction(0,1)
    d1, d2 = _swing_pair()  # 2/3, 1/3

    for ch in chords:
        V = _voicing_shell(ch)

        # 한 마디 패턴 설계
        hits = []
        # beat 2 strong
        hits.append(("on", 2))
        # beat 4 strong
        hits.append(("on", 4))
        # 가끔 beat2 앞 1/3 앞당김
        if random.random() < (0.35 if density!="low" else 0.2):
            hits.append(("anticip", 2))
        # 가끔 beat3 또는 beat1 off
        if random.random() < (0.25 if density=="high" else 0.15):
            hits.append(("off", random.choice([1,3])))

        # 시간축 구성(스윙)
        # 각 beat는 [d1(2/3), d2(1/3)]로 나눠짐
        events = []
        for b in range(1,5):
            # on-beat 첫 조각(강세 후보)
            events.append((b, "first"))
            # 두 번째 조각(리바운드/쉼)
            events.append((b, "second"))

        # 이벤트 채우기
        for (b, part) in events:
            place_hit = False
            accent = False
            dur = d1 if part == "first" else d2

            if ("on", b) in hits and part == "first":
                place_hit = True; accent = True
            if ("off", b) in hits and part == "second":
                place_hit = True
            if ("anticip", 2) in hits and b == 1 and part == "second":
                # beat2를 앞당겨 1두번째 조각에 찍음
                place_hit = True

            if place_hit:
                cur = _append(mel, be, dyn, lyr, cur, V, dur, d=('f' if accent else 'mf'))
            else:
                # 리바운드/쉼 (가끔 톱노트만)
                if part == "second" and random.random() < 0.25:
                    top = [V[-1]]
                    cur = _append(mel, be, dyn, lyr, cur, top, dur, d='mp')
                else:
                    cur = _append(mel, be, dyn, lyr, cur, ["rest"], dur, d='mp')

    return mel, be, dyn, lyr

def _style_swing_block(chords, density="medium", seed=None):
    """
    스윙 블록(루트리스 보이싱, 블록코드) : 1, 2&, 3, 4& 중심
    """
    if seed is not None:
        random.seed(seed)

    mel, be, dyn, lyr = [], [], [], []
    cur = Fraction(0,1)
    d1, d2 = _swing_pair()

    for ch in chords:
        V = _voicing_rootless(ch)

        for beat in range(1,5):
            # on (강세)
            cur = _append(mel, be, dyn, lyr, cur, V, d1, d='mf' if beat in (1,3) else 'f')
            # & (리바운드/쉼)
            if random.random() < (0.45 if density!="low" else 0.25):
                # 가끔 상성음만(탑노트)
                if random.random() < 0.35:
                    cur = _append(mel, be, dyn, lyr, cur, [V[-1]], d2, d='mp')
                else:
                    cur = _append(mel, be, dyn, lyr, cur, V, d2, d='mp')
            else:
                cur = _append(mel, be, dyn, lyr, cur, ["rest"], d2, d='mp')

    return mel, be, dyn, lyr

def _style_bossa_like(chords, density="medium", seed=None):
    """
    보사/라틴풍(스윙X, even 8th 느낌) : 1 (&) 3 (&) 중심
    """
    if seed is not None:
        random.seed(seed)

    mel, be, dyn, lyr = [], [], [], []
    cur = Fraction(0,1)
    e = Fraction(1,2)  # 8분음표(균등)

    for ch in chords:
        V = _voicing_rootless(ch)
        for beat in range(1,5):
            # on
            cur = _append(mel, be, dyn, lyr, cur, V, e, d='mf')
            # &
            if random.random() < (0.6 if density!="low" else 0.4):
                cur = _append(mel, be, dyn, lyr, cur, [V[-1]], e, d='mp')
            else:
                cur = _append(mel, be, dyn, lyr, cur, ["rest"], e, d='mp')

    return mel, be, dyn, lyr

def _style_ballad_2(chords, density="low", seed=None):
    """
    발라드 2분음표 중심(길게 유지, 가끔 분산/탑노트)
    """
    if seed is not None:
        random.seed(seed)

    mel, be, dyn, lyr = [], [], [], []
    cur = Fraction(0,1)
    h = Fraction(2,1)   # 2분음표
    q = Fraction(1,1)   # 4분음표

    for ch in chords:
        V = _voicing_rootless(ch)

        # 1~2 박 지속
        if random.random() < 0.25:
            # 짧게 탑노트 → 전체
            cur = _append(mel, be, dyn, lyr, cur, [V[-1]], Fraction(1,3), d='mp')
            cur = _append(mel, be, dyn, lyr, cur, V, h - Fraction(1,3), d='mf')
        else:
            cur = _append(mel, be, dyn, lyr, cur, V, h, d='mf')

        # 3~4 박
        if random.random() < 0.35:
            cur = _append(mel, be, dyn, lyr, cur, V, q, d='mp')
            cur = _append(mel, be, dyn, lyr, cur, ["rest"], q, d='mp')
        else:
            cur = _append(mel, be, dyn, lyr, cur, V, h, d='mp')

    return mel, be, dyn, lyr

def _style_quartal_modal(chords, density="medium", seed=None):
    """
    모달/쿼털 풍 4도堆積 보이싱, off-beat 중심
    """
    if seed is not None:
        random.seed(seed)

    mel, be, dyn, lyr = [], [], [], []
    cur = Fraction(0,1)
    d1, d2 = _swing_pair()

    for ch in chords:
        V = _voicing_quartal(ch)
        for beat in range(1,5):
            # on
            cur = _append(mel, be, dyn, lyr, cur, V, d1, d='mf')
            # & : 쿼털 탑노트만 또는 쉼
            if random.random() < (0.5 if density!="low" else 0.3):
                cur = _append(mel, be, dyn, lyr, cur, [V[-1]], d2, d='mp')
            else:
                cur = _append(mel, be, dyn, lyr, cur, ["rest"], d2, d='mp')

    return mel, be, dyn, lyr

_STYLES = {
    "swing_shells":   _style_swing_shells,
    "swing_block":    _style_swing_block,
    "bossa_like":     _style_bossa_like,
    "ballad_2":       _style_ballad_2,
    "quartal_modal":  _style_quartal_modal,
}

def generate_jazz_piano_pattern(chords,
                                style=None,        # None이면 랜덤
                                density="medium",  # low/medium/high
                                seed=None):
    """
    반환: (melodies, beat_ends, dynamics, lyrics)
    - melodies: ['E4'] or ['E4','A4','D5', ...] 등 (코드=리스트)
    - beat_ends: 누적 박(분수 권장) — 항상 단조 증가
    """
    if style is None:
        style = random.choice(list(_STYLES.keys()))
    if style not in _STYLES:
        raise ValueError(f"지원하지 않는 스타일: {style} / {list(_STYLES.keys())}")

    return _STYLES[style](chords, density=density, seed=seed)