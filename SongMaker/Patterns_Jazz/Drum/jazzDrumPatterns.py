# SongMaker/Patterns_Jazz/Drum/jazzDrumPatterns.py
import random
from fractions import Fraction

# ─────────────────────────────
# GM Drum (music21에서 썼던 이름과 일관되게)
KICK  = "C2"   # Kick
SNARE = "D2"   # Snare
HAT   = "F#2"  # Closed Hi-hat (스윙에서는 Ride를 주로 쓰지만, 호환용으로 둠)
RIDE  = "A#2"  # Ride Cymbal 1 (GM 58) -- 일부 환경에서 "A2"로 써도 됨
CRASH = "C#3"  # Crash Cymbal 1

# dynamics는 score_helper가 문자로 받아서 볼륨화하므로 "mf","f" 등 문자열 사용
ACCENT = "f"
NORM   = "mf"
SOFT   = "mp"

def _swing_pair():
    """
    스윙 8분 느낌: 2/3 + 1/3 (분수로 반환)
    """
    return Fraction(2, 3), Fraction(1, 3)

def _append_event(melodies, beat_ends, dynamics, lyrics, current_beat, event_notes, dur, dyn=NORM):
    """
    event_notes: ['A#2'] or ['A#2','D2'] 등 동시 타격
    dur: Fraction 혹은 float (분수 권장)
    current_beat + dur -> beat_ends 누적 (score_helper 규칙: '끝나는 박' 누적값)
    """
    if not event_notes:
        event_notes = ["rest"]
    melodies.append(event_notes)
    current_beat += dur
    beat_ends.append(current_beat)
    dynamics.append(dyn)
    lyrics.append("")
    return current_beat

# ─────────────────────────────
# 템플릿 패턴 (핵심 반복 규칙)
# style 목록: 'medium_swing', 'up_swing', 'two_feel', 'shuffle_blues', 'brush_ballad'
def _pattern_medium_swing(measures, density="medium", fill_prob=0.10, seed=None):
    """
    가장 기본: Ride가 메인, 2/4 스네어 백비트, 킥은 드물게.
    스윙 그리드(2/3, 1/3) 사용.
    """
    if seed is not None:
        random.seed(seed)

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    current = Fraction(0, 1)

    d1, d2 = _swing_pair()  # 2/3, 1/3

    for bar in range(measures):
        for beat in range(1, 5):  # 4/4
            # 기본 Ride on 첫 부분(2/3)
            notes_first = [RIDE]
            # 2와 4에서 스네어 백비트
            if beat in (2, 4):
                notes_first.append(SNARE)
            # 킥은 가끔(첫 박에 약간), density에 따라
            if beat == 1 and random.random() < (0.4 if density != "low" else 0.2):
                notes_first.append(KICK)

            current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                    current, notes_first, d1,
                                    dyn=ACCENT if beat in (2, 4) else NORM)

            # 두 번째 부분(1/3)은 대부분 Ride sustain/쉼표
            if random.random() < 0.6:
                notes_second = [RIDE]  # ride 리바운드
                dyn2 = SOFT
            else:
                notes_second = ["rest"]
                dyn2 = SOFT

            # 간간히 킥/스네어 유도(밀도 높으면 조금 더 추가)
            if density == "high" and random.random() < 0.2:
                if random.random() < 0.5:
                    if "rest" in notes_second: notes_second = []
                    notes_second = list(set(notes_second + [KICK]))
                else:
                    if "rest" in notes_second: notes_second = []
                    notes_second = list(set(notes_second + [SNARE]))

            # 마지막 박에서 fill 확률
            if beat == 4 and random.random() < fill_prob:
                # 3개의 triplet으로 작은 스네어 필(각 1/3)
                for _ in range(3):
                    current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                            current, [SNARE], Fraction(1, 3), dyn=NORM)
            else:
                current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                        current, notes_second, d2, dyn=dyn2)

    return melodies, beat_ends, dynamics, lyrics


def _pattern_up_swing(measures, density="high", fill_prob=0.15, seed=None):
    """
    약간 업템포 느낌: ride는 더 꾸준, 킥은 더 자주, 스네어 고스트(약하게) 조금 추가.
    """
    if seed is not None:
        random.seed(seed)

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    current = Fraction(0, 1)
    d1, d2 = _swing_pair()

    for bar in range(measures):
        for beat in range(1, 5):
            # ride + (2/4에서는 snare 강)
            notes_first = [RIDE]
            dyn_first = ACCENT if beat in (2, 4) else NORM
            if beat in (2, 4):
                notes_first.append(SNARE)
            # 킥 빈도 ↑
            if random.random() < 0.5:
                notes_first.append(KICK)

            current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                    current, notes_first, d1, dyn=dyn_first)

            # 두 번째 부분: ride or rest + 고스트 스네어 (약)
            notes_second = [RIDE] if random.random() < 0.7 else ["rest"]
            if random.random() < 0.25:
                if "rest" in notes_second: notes_second = []
                notes_second = list(set(notes_second + [SNARE]))
            dyn2 = SOFT

            # 간단 fill
            if beat == 4 and random.random() < fill_prob:
                for _ in range(3):
                    current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                            current, [SNARE], Fraction(1, 3), dyn=NORM)
            else:
                current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                        current, notes_second, d2, dyn=dyn2)
    return melodies, beat_ends, dynamics, lyrics


def _pattern_two_feel(measures, density="low", fill_prob=0.05, seed=None):
    """
    2-feel: ride는 유지하되 킥/스네어 sparse. 스윙을 약화(Quarter 중심).
    """
    if seed is not None:
        random.seed(seed)

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    current = Fraction(0, 1)
    # Quarter 중심(스윙 대신 1.0 + 0.0 구조)
    q = Fraction(1, 1)

    for bar in range(measures):
        for beat in range(1, 5):
            notes = [RIDE]
            if beat in (2, 4) and random.random() < 0.6:
                notes.append(SNARE)
            if beat == 1 and random.random() < 0.3:
                notes.append(KICK)

            current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                    current, notes, q,
                                    dyn=ACCENT if beat in (2, 4) else NORM)

        # bar 마지막 fill(드물게)
        if random.random() < fill_prob:
            # 1박(=Quarter) 안을 triplet 3개로 쪼개 작은 fill (다음 마디로 넘어가기 전에)
            for _ in range(3):
                current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                        current, [SNARE], Fraction(1, 3), dyn=NORM)
    return melodies, beat_ends, dynamics, lyrics


def _pattern_shuffle_blues(measures, density="medium", fill_prob=0.12, seed=None):
    """
    Shuffle Blues 풍: 강한 백비트, 킥은 간간히.
    """
    if seed is not None:
        random.seed(seed)

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    current = Fraction(0, 1)
    d1, d2 = _swing_pair()

    for bar in range(measures):
        for beat in range(1, 5):
            # 첫 분할: ride + (2/4 snare 강)
            notes_first = [RIDE]
            if beat in (2, 4):
                notes_first.append(SNARE)
            if random.random() < 0.35:
                notes_first.append(KICK)
            current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                    current, notes_first, d1,
                                    dyn=ACCENT if beat in (2, 4) else NORM)

            # 두 번째 분할: 대부분 ride, 가끔 킥 추가
            notes_second = [RIDE] if random.random() < 0.8 else ["rest"]
            if random.random() < 0.15:
                if "rest" in notes_second: notes_second = []
                notes_second.append(KICK)
            current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                    current, notes_second, d2, dyn=SOFT)

        # bar 끝 fill
        if random.random() < fill_prob:
            for _ in range(3):
                melodies.append([SNARE])
                current += Fraction(1, 3)
                beat_ends.append(current)
                dynamics.append(NORM)
                lyrics.append("")
    return melodies, beat_ends, dynamics, lyrics


def _pattern_brush_ballad(measures, density="low", fill_prob=0.05, seed=None):
    """
    느린 발라드 브러쉬 느낌(엄밀한 브러쉬 음색은 GM map/사운드에 좌우)
    여기서는 soft ride + 드문 snare/kick.
    """
    if seed is not None:
        random.seed(seed)

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    current = Fraction(0, 1)
    q = Fraction(1, 1)

    for bar in range(measures):
        for beat in range(1, 5):
            notes = [RIDE]  # brush ride 대체
            dyn = SOFT
            if beat in (2, 4) and random.random() < 0.4:
                notes.append(SNARE); dyn = NORM
            if beat == 1 and random.random() < 0.2:
                notes.append(KICK)

            current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                    current, notes, q, dyn=dyn)

        if random.random() < fill_prob:
            for _ in range(2):  # 짧은 fill
                current = _append_event(melodies, beat_ends, dynamics, lyrics,
                                        current, [SNARE], Fraction(1, 2), dyn=NORM)

    return melodies, beat_ends, dynamics, lyrics

# ─────────────────────────────
_STYLES = {
    "medium_swing": _pattern_medium_swing,
    "up_swing": _pattern_up_swing,
    "two_feel": _pattern_two_feel,
    "shuffle_blues": _pattern_shuffle_blues,
    "brush_ballad": _pattern_brush_ballad,
}

def generate_jazz_drum_pattern(measures=8,
                               style=None,        # None이면 랜덤 선택
                               density="medium",  # "low" | "medium" | "high"
                               fill_prob=0.10,
                               seed=None):
    """
    반환: (melodies, beat_ends, dynamics, lyrics)
    - melodies: [['A#2'], ['A#2','D2'], ...] 형태 (여러 타격 동시 가능)
    - beat_ends: Fraction/float 누적(항상 단조 증가)
    - dynamics: ['mf','f','mp'...]
    - lyrics: ['','','',...]
    """
    if style is None:
        style = random.choice(list(_STYLES.keys()))
    if style not in _STYLES:
        raise ValueError(f"지원하지 않는 style: {style} ({list(_STYLES.keys())} 중 선택)")

    return _STYLES[style](measures, density=density, fill_prob=fill_prob, seed=seed)