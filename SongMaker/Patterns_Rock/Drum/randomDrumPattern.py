# SongMaker/Patterns_Rock/Drum/randomDrumPattern.py
from SongMaker.utils.humanize import snap_beats
import random

def generate_random_drum_pattern(measures=8, style="rock8", fill_prob=0.1):
    """
    반환: melodies, beat_ends, dynamics, lyrics
    beat_ends 는 반드시 **오름차순 & 0.25 배수** 로 만들어 줌
    """
    KICK, SNARE, HAT = "C2", "D2", "F#2"

    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    cur = 0.0

    for m in range(measures):
        if style == "rock8":
            grid = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        elif style == "rock16":
            grid = [i * 0.25 for i in range(16)]
        elif style == "halfTime":
            grid = [0.0, 1.0, 2.0, 3.0]
        else:
            raise ValueError("unknown style")

        for idx, off in enumerate(grid):
            drums = [HAT] if random.random() < 0.85 else []

            # 백비트
            if idx % 4 == 2:
                drums.append(SNARE)
            # 다운비트
            if idx % 4 == 0 and random.random() < 0.9:
                drums.append(KICK)
            # 변형 킥
            if idx % 4 == 3 and random.random() < 0.4:
                drums.append(KICK)

            if random.random() < fill_prob:
                drums.append(random.choice([KICK, SNARE]))

            if not drums:
                continue                       # 이 틱은 쉬어 간다

            melodies.append(drums)
            beat_ends.append(cur + off + 0.25)  # off 끝나는 위치
            dynamics.append("mf")
            lyrics.append("")

        cur += 4.0

    # ▲ 생성 후 스냅‧정렬
    beat_ends = snap_beats(beat_ends, 0.25)
    return melodies, beat_ends, dynamics, lyrics