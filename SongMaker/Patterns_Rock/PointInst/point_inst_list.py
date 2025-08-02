# SongMaker/Patterns_Rock/PointInst/point_inst_list.py
from music21 import instrument

# ─────────────────────────────────────────────────────────────
# GM Program 참고(표준): 27 Jazz Gtr, 28 Clean Gtr, 29 Overdrive, 30 Distortion,
# 81 Lead 1 (Square), 82 Lead 2 (Saw), 61 Brass Section, 62 Synth Brass 1, 22 Harmonica
# ※ DAW/사운드폰트에 따라 약간 다를 수 있음. 필요시 숫자만 바꿔 쓰면 됨.
# ─────────────────────────────────────────────────────────────

_POINT_DEF = {
    "overdrive_guitar":  (29, "guitar"),     # Overdriven Guitar
    "distortion_guitar": (30, "guitar"),     # Distortion Guitar
    "clean_guitar":      (28, "guitar"),     # Electric Guitar (Clean)
    "jazz_guitar":       (27, "guitar"),     # Electric Guitar (Jazz)
    "lead_square":       (81, "synth"),      # Lead 1 (Square)
    "lead_saw":          (82, "synth"),      # Lead 2 (Saw)
    "brass_section":     (61, "generic"),    # Brass Section
    "synth_brass":       (62, "generic"),    # Synth Brass 1
    "harmonica":         (22, "generic"),    # Harmonica
}

POINT_CHOICES_ROCK = list(_POINT_DEF.keys())

def get_point_instrument(name: str):
    """
    name: POINT_CHOICES_ROCK 중 하나.
    반환: music21 Instrument (midiProgram 지정)
    """
    name = (name or "").lower()
    if name not in _POINT_DEF:
        raise ValueError(f"지원하지 않는 포인트 악기: {name}. 선택지={POINT_CHOICES_ROCK}")

    prog, base = _POINT_DEF[name]

    # 베이스 타입에 따라 무난한 클래스 선택
    if base == "guitar":
        inst = instrument.ElectricGuitar()
    elif base == "synth":
        inst = instrument.Instrument()  # 일반 Instrument에 GM 프로그램만 지정
    else:
        inst = instrument.Instrument()

    inst.midiProgram = prog
    inst.partName = name
    return inst