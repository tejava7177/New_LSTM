# SongMaker/useSongMaker_pop.py
import os
import random
import tempfile
from typing import Optional, List, Dict

from .ai_song_maker.score_helper import process_and_output_score
from .utils.timing_pop import fix_beats, clip_and_fill_rests
from .Patterns_Pop.Drum.popDrumPatterns import generate_pop_drum_pattern
from .Patterns_Pop.Guitar.popGuitarPatterns import generate_pop_rhythm_guitar
from .Patterns_Pop.Keys.popKeysPatterns import generate_pop_keys
from .Patterns_Rock.Lead.rockPointLines import generate_point_line  # 훅 재사용
from .Patterns_Pop.PointInst.point_inst_list import (
    POINT_CHOICES_POP,
    get_point_instrument,
)
# 장르 공용 GM 세트 사용(프로젝트 상황에 맞게 교체 가능)
from .instruments.gm_instruments import get_rock_band_instruments as get_pop_band_instruments


def _normalize_point_choices(pc) -> List[str]:
    """POINT_CHOICES_POP가 list/set/dict/[(name, obj)] 등 어떤 형태여도 이름 리스트로 정규화."""
    if pc is None:
        return []
    # dict-like: keys
    if hasattr(pc, "keys"):
        return list(pc.keys())
    # iterable 추정
    try:
        it = iter(pc)
        first = next(it)
    except StopIteration:
        return []
    except TypeError:
        return []
    # [(name, obj)] 형태
    if isinstance(first, tuple) and len(first) >= 1:
        names = [t[0] for t in pc]
    else:
        # list/tuple/set of names
        names = list(pc)
    # 재현성/안정적 샘플을 위해 소팅(선택)
    try:
        names = sorted(names)
    except Exception:
        pass
    return names


def generate_pop_track(
    progression: List[str],
    tempo: int = 100,
    drum: str = "auto",           # ["fourFloor","backbeat","halfTime","edm16"]
    gtr: str = "auto",            # ["pm8","clean_arp","chop_off"]
    keys: str = "auto",           # ["pad_block","pop_arp","broken8"]
    point_inst: str = "none",     # "none" | "auto" | "lead_square, brass_section" 등
    point_density: str = "light",
    point_key: str = "C",
    out_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    POP 트랙(드럼/기타/키 + 선택 포인트 라인)을 생성하고 MIDI/MusicXML 경로를 반환한다.
    콘솔 입력/파일 읽기 없이 progression과 옵션만으로 동작한다.
    """
    # 입력 검증
    chords = progression or []
    if not chords:
        raise ValueError("progression(코드 진행)이 비었습니다.")
    num_bars = len(chords)
    total_beats = 4.0 * num_bars

    # 출력 디렉토리
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="pop_output_")
    os.makedirs(out_dir, exist_ok=True)

    # 악기 셋 & 스타일 결정
    insts = get_pop_band_instruments()
    drum_style = drum if drum != "auto" else random.choice(["fourFloor", "backbeat", "halfTime", "edm16"])
    gtr_style  = gtr  if gtr  != "auto" else random.choice(["pm8", "clean_arp", "chop_off"])
    keys_style = keys if keys != "auto" else random.choice(["pad_block", "pop_arp", "broken8"])

    # ---- 드럼 ----
    d_m, d_b, d_d, d_l = generate_pop_drum_pattern(measures=num_bars, style=drum_style, clap_prob=0.5)
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, total_beats=total_beats)
    d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l)

    # ---- 기타 ----
    g_m, g_b, g_d, g_l = generate_pop_rhythm_guitar(chords, style=gtr_style)
    g_m, g_b, g_d, g_l = fix_beats(g_m, g_b, g_d, g_l, total_beats=total_beats)
    g_m, g_b, g_d, g_l = clip_and_fill_rests(g_m, g_b, g_d, g_l)

    # ---- 키즈 ----
    k_m, k_b, k_d, k_l = generate_pop_keys(chords, style=keys_style, add_shell=True)
    k_m, k_b, k_d, k_l = fix_beats(k_m, k_b, k_d, k_l, total_beats=total_beats)
    k_m, k_b, k_d, k_l = clip_and_fill_rests(k_m, k_b, k_d, k_l)

    parts_data = {
        "Drums": {
            "instrument": insts["drum"],
            "melodies": d_m, "beat_ends": d_b, "dynamics": d_d, "lyrics": d_l
        },
        "Guitar": {
            "instrument": insts["elec_guitar"],
            "melodies": g_m, "beat_ends": g_b, "dynamics": g_d, "lyrics": g_l
        },
        "Keys": {
            "instrument": insts["synth"],
            "melodies": k_m, "beat_ends": k_b, "dynamics": k_d, "lyrics": k_l
        }
    }

    # ---- 포인트 라인(옵션) ----
    if point_inst and point_inst.lower() not in ["none", ""]:
        resolved = []
        if point_inst.lower() == "auto":
            names_pool = _normalize_point_choices(POINT_CHOICES_POP)
            pick_n = min(2, len(names_pool))
            if pick_n > 0:
                names = random.sample(names_pool, k=pick_n)
                resolved = [(n, get_point_instrument(n)) for n in names]
        else:
            names = [s.strip() for s in point_inst.split(",") if s.strip()]
            for n in names:
                inst_obj = get_point_instrument(n)  # 유효하지 않으면 ValueError
                resolved.append((n, inst_obj))

        for name, inst_obj in resolved:
            # POP 훅: rockPointLines의 간단 훅을 재사용(프로젝트 맞게 교체 가능)
            try:
                p_m, p_b, p_d, p_l = generate_point_line(chords, phrase_len=4, density=point_density, key=point_key)
            except TypeError:
                # key 인자 없는 버전과 호환
                p_m, p_b, p_d, p_l = generate_point_line(chords, phrase_len=4, density=point_density)
            p_m, p_b, p_d, p_l = fix_beats(p_m, p_b, p_d, p_l, total_beats=total_beats)
            p_m, p_b, p_d, p_l = clip_and_fill_rests(p_m, p_b, p_d, p_l, dur_max=1.0)  # 짧은 훅

            parts_data[f"Point_{name}"] = {
                "instrument": inst_obj,
                "melodies": p_m, "beat_ends": p_b, "dynamics": p_d, "lyrics": p_l
            }

    # ---- 출력 ----
    score_data = {"key": "C", "time_signature": "4/4", "tempo": tempo, "clef": "treble"}
    tag = f"{drum_style}-{gtr_style}-{keys_style}"
    xml_path = os.path.join(out_dir, f"pop_{tag}.xml")
    midi_path = os.path.join(out_dir, f"pop_{tag}.mid")

    process_and_output_score(parts_data, score_data, musicxml_path=xml_path, midi_path=midi_path, show_html=False)

    return {"midi_path": midi_path, "musicxml_path": xml_path, "tag": tag}