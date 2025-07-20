# SongMaker/Patterns_Rock/Guitar/randomGuitarPattern.py

import random


def generate_random_guitar_pattern(
        chords,
        beats_per_bar=4,
        pattern="random"  # "random", "strum", "arpeggio" 지원
):
    """
    입력 코드 진행에 따라 기타 패턴(스트로크/아르페지오) 자동 생성

    Args:
        chords (list of str): 코드 리스트
        beats_per_bar (int): 한 마디당 박자 수 (기본 4)
        pattern (str): "strum", "arpeggio", "random" (기본: "random", 마디마다 랜덤)
    Returns:
        melodies, beat_ends, dynamics, lyrics (모두 리스트)
    """
    # 코드별 구성음(예시)
    chord_notes_map = {
        "C": ["C3", "E3", "G3"],
        "G": ["G3", "B3", "D4"],
        "Am": ["A3", "C4", "E4"],
        "F": ["F3", "A3", "C4"]
    }

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    current_beat = 0.0

    for chord in chords:
        notes = chord_notes_map.get(chord, ["C3", "E3", "G3"])
        # 마디별로 랜덤 패턴 결정 (pattern=="random"이면 랜덤)
        use_pattern = pattern
        if pattern == "random":
            use_pattern = random.choice(["arpeggio", "strum"])

        if use_pattern == "strum":
            # 스트로크: 코드 전체를 매 박마다 반복
            for _ in range(beats_per_bar):
                melodies.append(notes)
                current_beat += 1.0
                beat_ends.append(current_beat)
                dynamics.append("mf")
                lyrics.append("")
        elif use_pattern == "arpeggio":
            # 아르페지오: 코드음 하나씩(반복)
            for i in range(beats_per_bar):
                melodies.append([notes[i % len(notes)]])
                current_beat += 1.0
                beat_ends.append(current_beat)
                dynamics.append("mf")
                lyrics.append("")
        else:
            raise ValueError("지원하지 않는 패턴입니다. (strum, arpeggio, random만 가능)")

    return melodies, beat_ends, dynamics, lyrics


# (테스트 코드, 실제 사용 시 아래는 생략/주석)
if __name__ == "__main__":
    test_chords = ["C", "G", "Am", "F"]
    mel, beats, dyn, lyr = generate_random_guitar_pattern(test_chords * 2)
    print("==melodies==")
    print(mel)