import random

def generate_random_guitar_pattern(chords, beats_per_bar=4):
    """
    입력 코드 진행에 따라 기타 패턴을 랜덤하게 생성.
    - 코드별로 '스트로크' 또는 '아르페지오' 중 하나 랜덤 선택 (나중엔 장르/스타일별로 세분화 가능)
    - 반환: (melodies, beat_ends, dynamics, lyrics)
    """
    # 기본 코드별 구성음 (저음부터)
    chord_notes_map = {
        "C":  ["C3", "E3", "G3"],
        "G":  ["G3", "B3", "D4"],
        "Am": ["A3", "C4", "E4"],
        "F":  ["F3", "A3", "C4"]
        # 필요하면 더 추가!
    }

    melodies = []
    beat_ends = []
    dynamics = []
    lyrics = []
    current_beat = 0.0

    for chord in chords:
        notes = chord_notes_map.get(chord, ["C3", "E3", "G3"])
        # 랜덤: 스트로크 or 아르페지오 선택
        if random.random() < 0.5:
            # 스트로크 (한 박에 코드 전체)
            for i in range(beats_per_bar):
                melodies.append(notes)
                current_beat += 1.0
                beat_ends.append(current_beat)
                dynamics.append("mf")
                lyrics.append("")
        else:
            # 아르페지오 (코드음 하나씩)
            for i in range(beats_per_bar):
                melodies.append([notes[i % len(notes)]])  # 각 박마다 코드음 순환
                current_beat += 1.0
                beat_ends.append(current_beat)
                dynamics.append("mf")
                lyrics.append("")
    return melodies, beat_ends, dynamics, lyrics

# 직접 테스트용 코드 (본 모듈에서는 아래 부분은 삭제/주석해도 무방)
if __name__ == "__main__":
    test_chords = ["C", "G", "Am", "F"]
    mel, beats, dyn, lyr = generate_random_guitar_pattern(test_chords * 2)
    print(mel)