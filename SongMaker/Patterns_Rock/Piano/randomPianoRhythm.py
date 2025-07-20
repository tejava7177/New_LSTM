# SongMaker/Patterns_Rock/Piano/randomPianoRhythm.py
import random

# 피아노 코드 진행 → 각 마디마다 랜덤 리듬 + 아르페지오(혹은 단순 코드) 자동 생성
def generate_random_piano_rhythms(
    chords,
    allowed_durations=None,
    pattern="arpeggio"  # "arpeggio" 또는 "block"
):
    """
    chords: 코드 진행 리스트 (예: ["C", "G", ...])
    allowed_durations: 각 음표 길이 (기본: [0.25, 0.5, 1.0, 1.5, 2.0])
    pattern: "arpeggio" (음 하나씩) 또는 "block" (코드 한 번에)
    return: melodies, beat_ends, dynamics, lyrics
    """
    if allowed_durations is None:
        allowed_durations = [0.25, 0.5, 1.0, 1.5, 2.0]

    # 코드별 피아노 음 패턴(변형 가능)
    chord_to_notes = {
        "C":  ["C4", "E4", "G4", "E4"],
        "G":  ["G3", "B3", "D4", "B3"],
        "Am": ["A3", "C4", "E4", "C4"],
        "F":  ["F3", "A3", "C4", "A3"],
        # 더 추가 가능
    }

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    current_beat = 0.0

    for bar_chord in chords:
        notes = chord_to_notes.get(bar_chord, ["C4", "E4", "G4", "E4"])
        # 1. 랜덤 리듬 생성 (총합 4박)
        durations = []
        remain = 4.0
        while remain > 0:
            possible = [d for d in allowed_durations if d <= remain]
            dur = random.choice(possible)
            durations.append(dur)
            remain -= dur
        # 2. 멜로디/화음 추가
        if pattern == "arpeggio":
            note_idx = 0
            for dur in durations:
                melodies.append(notes[note_idx % len(notes)])
                current_beat += dur
                beat_ends.append(current_beat)
                dynamics.append("mf")
                lyrics.append("")
                note_idx += 1
        elif pattern == "block":
            # 마디 내 모든 리듬마다 같은 코드(화음) 반복
            for dur in durations:
                melodies.append(notes)  # 화음(코드)로 삽입
                current_beat += dur
                beat_ends.append(current_beat)
                dynamics.append("mf")
                lyrics.append("")
        else:
            raise ValueError("지원하지 않는 패턴입니다. ('arpeggio' 또는 'block'만 사용)")

    return melodies, beat_ends, dynamics, lyrics