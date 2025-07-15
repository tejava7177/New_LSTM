import random

def get_scale_notes(key, scale_type="major"):
    # 아주 기본 C메이저, A마이너만 예시로
    if key == "C" and scale_type == "major":
        return ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
    elif key == "A" and scale_type == "minor":
        return ["A3", "B3", "C4", "D4", "E4", "F4", "G4"]
    # ... 실제는 모든 키 지원하도록 확장 가능
    return ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]

def random_guitar_solo_pattern(num_bars=8, key="C", scale_type="major"):
    melodies = []
    beat_ends = []
    dynamics = []
    lyrics = []
    current_beat = 0.0

    scale = get_scale_notes(key, scale_type)

    prev_note_idx = random.randint(0, len(scale)-1)
    for bar in range(num_bars):
        num_notes = random.choice([2, 3, 4])  # 한마디에 2~4음
        bar_rhythms = []
        total_beat = 0.0
        while total_beat < 4.0 and len(bar_rhythms) < num_notes:
            remain = 4.0 - total_beat
            dur = round(random.choice([0.5, 1.0, 1.5]), 2)
            if dur > remain: dur = remain
            bar_rhythms.append(dur)
            total_beat += dur
        # 음정 진행
        for i, dur in enumerate(bar_rhythms):
            # 2~4도 이내의 움직임
            move = random.choice([-2, -1, 0, 1, 2])
            new_idx = min(max(prev_note_idx + move, 0), len(scale)-1)
            # 첫음, 마지막음은 코드톤 확률↑
            if i == 0 or i == len(bar_rhythms)-1:
                note = random.choice([scale[0], scale[2], scale[4]])  # 코드톤 선택
            else:
                note = scale[new_idx]
            melodies.append(note)
            current_beat += dur
            beat_ends.append(current_beat)
            dynamics.append(random.choice(["mf", "f", "mp"]))
            lyrics.append("")
            prev_note_idx = new_idx

    return melodies, beat_ends, dynamics, lyrics