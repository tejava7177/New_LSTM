import random

def get_scale_notes(key="C", scale_type="major"):
    # C 메이저 or A 마이너 등 원하는 스케일로 확장 가능
    scale_table = {
        "C_major": ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"],
        "A_minor": ["A3", "B3", "C4", "D4", "E4", "F4", "G4", "A4"]
    }
    return scale_table.get(f"{key}_{scale_type}", scale_table["C_major"])

def random_guitar_solo_pattern(num_bars, key="C", scale_type="major"):
    melodies, beat_ends, dynamics, lyrics = [], [], [], []
    allowed_durations = [0.25, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0]  # 16/8/4분음표, 부점 등 랜덤하게
    scale_notes = get_scale_notes(key, scale_type)
    current_beat = 0.0
    for bar in range(num_bars):
        remain = 4.0
        while remain > 0:
            dur = random.choice([d for d in allowed_durations if d <= remain])
            # 확률적으로 점프, 반복, 상행, 하행, 쉬는음 섞기
            if random.random() < 0.15:
                note = "rest"
            else:
                note = random.choice(scale_notes)
            melodies.append(note)
            current_beat += dur
            beat_ends.append(current_beat)
            dynamics.append(random.choice(["mf", "f", "mp", "ff"]))  # 다이내믹도 다양하게
            lyrics.append("")
            remain -= dur
    return melodies, beat_ends, dynamics, lyrics