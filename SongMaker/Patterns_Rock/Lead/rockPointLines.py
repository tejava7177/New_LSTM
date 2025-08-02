# SongMaker/Patterns_Rock/Lead/rockPointLines.py
import random

# C 메이저/Am 펜타토닉 대략치(필요 시 키 대응 로직 확장)
PENTA_C = ["C5", "D5", "E5", "G5", "A5", "C6", "D6", "E6", "G6", "A6"]
PENTA_A = ["A4", "C5", "D5", "E5", "G5", "A5", "C6", "D6", "E6", "G6"]

def _emit(mel, beats, dyn, lyr, t, pitches, dur, d="mf"):
    if isinstance(pitches, str): pitches = [pitches]
    t += dur
    mel.append(pitches); beats.append(t); dyn.append(d); lyr.append("")
    return t

def generate_point_line(chords, phrase_len=4, density="light", key="C"):
    """
    chords: 코드 리스트
    phrase_len: 4 마디마다 간단히 훅/필
    density: "light"|"med" (라이트 권장)
    key: 간단 키. "C"면 C 펜타, Am 진행이 많으면 "Am" 등 지정 가능
    """
    mel, beats, dyn, lyr = [], [], [], []
    t = 0.0

    scale = PENTA_A if key.lower() in ("a", "am", "amin") else PENTA_C
    light_notes = 2  # 1마디당 노출 수(라이트)

    for i, _ in enumerate(chords):
        bar_start = t
        # 기본은 쉼(존재감 과하지 않게)
        t += 4.0

        # 프레이즈 끝(phrase_len의 배수)과 루프 시작에만 짧게 훅
        if (i + 1) % phrase_len == 0 or i == 0:
            t = bar_start
            n_notes = light_notes if density == "light" else light_notes + 1
            # 3&, 4 박 정도에 8분/4분 배치
            spots = [3.5, 3.75, 4.0][:n_notes]
            for s in spots:
                # 음 선택
                p = random.choice(scale)
                dur = 0.5 if s < 4.0 else 0.5  # 너무 길게 두지 말자
                # 이벤트 작성
                mel.append([p]); beats.append(bar_start + s + dur); dyn.append("mf"); lyr.append("")
            # 마디 끝으로 커서 이동 보정
            t = bar_start + 4.0

    return mel, beats, dyn, lyr