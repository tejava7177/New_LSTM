# SongMaker/useSongMaker_jazz.py
import os
import random
import tempfile
from typing import Optional, List, Dict

from music21 import instrument

# 패키지 상대 임포트 (SongMaker가 패키지여야 함: 하위 폴더에 __init__.py 필요)
from .ai_song_maker.score_helper import process_and_output_score
from .Patterns_Jazz.Drum.jazzDrumPatterns import generate_jazz_drum_pattern
from .Patterns_Jazz.Piano.jazzPianoPatterns import style_bass_backing_minimal
from .Patterns_Jazz.PointInst.point_inst_list import (
    POINT_CHOICES_JAZZ,
    get_point_instrument,
)
from .Patterns_Jazz.Lead.jazzPointLines import generate_point_line
from .utils.timing_jazz import fix_beats, clip_and_fill_rests


def generate_jazz_track(
    progression: List[str],
    tempo: int = 140,
    drum: str = "auto",         # ["medium_swing","up_swing","two_feel","shuffle_blues","brush_ballad"]
    comp: str = "auto",         # 현재 minimal 고정(확장 가능)
    point_inst: str = "none",   # "none" | "auto" | "trumpet, flute" (쉼표 구분)
    point_density: str = "light",
    point_key: str = "C",
    out_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    progression/옵션을 받아 Jazz 트랙을 생성하고 MIDI/MusicXML 경로를 반환한다.
    콘솔 입력 없이 동작한다.
    """
    # 입력 검증
    chords = progression or []
    if not chords:
        raise ValueError("progression(코드 진행)이 비었습니다.")
    num_bars = len(chords)
    total_beats = 4.0 * num_bars

    # 출력 디렉토리
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="jazz_output_")
    os.makedirs(out_dir, exist_ok=True)

    # 스타일 결정
    drum_style = drum if drum != "auto" else random.choice(
        ["medium_swing", "up_swing", "two_feel", "shuffle_blues", "brush_ballad"]
    )
    comp_style = comp if comp != "auto" else "minimal"

    # ---- 드럼 ----
    d_m, d_b, d_d, d_l = generate_jazz_drum_pattern(
        measures=num_bars, style=drum_style, density="medium", fill_prob=0.12, seed=None
    )
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, total_beats=total_beats)  # grid=0.5 기본
    d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l)                 # dur_max=2.0 기본

    # ---- EP 컴핑 ----
    p_m, p_b, p_d, p_l = style_bass_backing_minimal(chords, phrase_len=4)
    p_m, p_b, p_d, p_l = fix_beats(p_m, p_b, p_d, p_l, total_beats=total_beats)
    p_m, p_b, p_d, p_l = clip_and_fill_rests(p_m, p_b, p_d, p_l)

    # ---- 파트 조립 ----
    parts_data = {
        "JazzDrums": {
            "instrument": instrument.SnareDrum(),          # 필요시 프로젝트 규칙에 맞춰 교체
            "melodies": d_m, "beat_ends": d_b, "dynamics": d_d, "lyrics": d_l,
        },
        "CompEP": {
            "instrument": instrument.ElectricPiano(),
            "melodies": p_m, "beat_ends": p_b, "dynamics": p_d, "lyrics": p_l,
        },
    }

    # ---- 포인트 악기(옵션) ----
    if point_inst and point_inst.lower() not in ["none", ""]:
        resolved = []
        if point_inst.lower() == "auto":
            pick_n = 2
            names = random.sample(POINT_CHOICES_JAZZ, k=min(pick_n, len(POINT_CHOICES_JAZZ)))
            resolved = [(n, get_point_instrument(n)) for n in names]
        else:
            names = [s.strip() for s in point_inst.split(",") if s.strip()]
            for n in names:
                inst_obj = get_point_instrument(n)  # 유효하지 않으면 ValueError 발생
                resolved.append((n, inst_obj))

        for name, inst_obj in resolved:
            try:
                m, b, d, l = generate_point_line(chords, phrase_len=4, density=point_density, pickup_prob=0.7)
            except TypeError:
                m, b, d, l = generate_point_line(chords, phrase_len=4, density=point_density)
            m, b, d, l = fix_beats(m, b, d, l, total_beats=total_beats)
            m, b, d, l = clip_and_fill_rests(m, b, d, l)
            parts_data[f"Point_{name}"] = {
                "instrument": inst_obj,
                "melodies": m, "beat_ends": b, "dynamics": d, "lyrics": l,
            }

    # ---- 출력 ----
    score_data = {"key": "C", "time_signature": "4/4", "tempo": tempo, "clef": "treble"}
    tag = f"{drum_style}-{comp_style}"
    xml_path = os.path.join(out_dir, f"jazz_{tag}.xml")
    midi_path = os.path.join(out_dir, f"jazz_{tag}.mid")

    process_and_output_score(parts_data, score_data, musicxml_path=xml_path, midi_path=midi_path, show_html=False)

    return {"midi_path": midi_path, "musicxml_path": xml_path, "tag": tag}