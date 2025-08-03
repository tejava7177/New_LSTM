# SongMaker/useSongMaker_rock.py
import os
import random
import tempfile
from typing import Optional, List, Dict

from .ai_song_maker.score_helper import process_and_output_score
from .utils.timing_rock import fix_beats, clip_and_fill_rests
from .Patterns_Rock.Drum.rockDrumPatterns import generate_rock_drum_pattern
from .Patterns_Rock.Guitar.rhythmGuitarPatterns import generate_rock_rhythm_guitar
from .Patterns_Rock.Piano.rockKeysPatterns import generate_rock_keys
from .Patterns_Rock.PointInst.point_inst_list import (
    POINT_CHOICES_ROCK,
    get_point_instrument,
)
from .Patterns_Rock.Lead.rockPointLines import generate_point_line
from .instruments.gm_instruments import get_rock_band_instruments


def _normalize_point_choices(pc) -> List[str]:
    """POINT_CHOICES_ROCK가 list/set/dict/[(name, obj)] 등 어떤 형태여도 이름 리스트로 정규화."""
    if pc is None:
        return []
    if hasattr(pc, "keys"):                 # dict-like
        return list(pc.keys())
    try:
        it = iter(pc)
        first = next(it)
    except StopIteration:
        return []
    except TypeError:
        return []
    if isinstance(first, tuple) and len(first) >= 1:  # [(name, obj), ...]
        names = [t[0] for t in pc]
    else:                                             # list/tuple/set of names
        names = list(pc)
    try:
        names = sorted(names)
    except Exception:
        pass
    return names


def generate_rock_track(
    progression: List[str],
    tempo: int = 120,
    drum: str = "auto",           # ["straight8","straight16","halfTime","punk8","tomGroove","rock8"]
    gtr: str = "auto",            # ["power8","sync16","offChop"]
    keys: str = "auto",           # ["arp4","blockPad","riffHook"]
    point_inst: str = "none",     # "none" | "auto" | "distortion_guitar, lead_square"
    point_density: str = "light",
    point_key: str = "C",
    keys_shell: bool = False,     # EP/Keys의 쉘 보이싱 옵션
    out_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    ROCK 트랙(드럼/기타/키 + 선택 포인트 라인)을 생성하고 MIDI/MusicXML 경로를 반환한다.
    콘솔 입력 없이 options만으로 동작. Jazz/Pop과 동일한 서명/반환 형식.
    """
    # 입력 검증
    chords = progression or []
    if not chords:
        raise ValueError("progression(코드 진행)이 비었습니다.")
    num_bars = len(chords)
    total_beats = 4.0 * num_bars

    # 출력 디렉토리
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="rock_output_")
    os.makedirs(out_dir, exist_ok=True)

    # 악기 셋 & 스타일 결정
    insts = get_rock_band_instruments()
    drum_style = drum if drum != "auto" else random.choice(
        ["straight8", "straight16", "halfTime", "punk8", "tomGroove", "rock8"]
    )
    gtr_style  = gtr  if gtr  != "auto" else random.choice(["power8", "sync16", "offChop"])
    keys_style = keys if keys != "auto" else random.choice(["arp4", "blockPad", "riffHook"])

    # ---- 드럼 ----
    d_m, d_b, d_d, d_l = generate_rock_drum_pattern(
        measures=num_bars, style=drum_style, fill_prob=0.08
    )
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, total_beats=total_beats)
    d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l, bar_len=4.0, total_beats=total_beats)

    # ---- 기타 ----
    g_m, g_b, g_d, g_l = generate_rock_rhythm_guitar(chords, style=gtr_style)
    g_m, g_b, g_d, g_l = fix_beats(g_m, g_b, g_d, g_l, total_beats=total_beats)
    g_m, g_b, g_d, g_l = clip_and_fill_rests(g_m, g_b, g_d, g_l, bar_len=4.0, total_beats=total_beats)

    # ---- 키즈/신스 ----
    k_m, k_b, k_d, k_l = generate_rock_keys(chords, style=keys_style, add_shell=keys_shell)
    k_m, k_b, k_d, k_l = fix_beats(k_m, k_b, k_d, k_l, total_beats=total_beats)
    k_m, k_b, k_d, k_l = clip_and_fill_rests(k_m, k_b, k_d, k_l, bar_len=4.0, total_beats=total_beats)

    parts_data = {
        "Drums": {
            "instrument": insts["drum"],
            "melodies": d_m, "beat_ends": d_b, "dynamics": d_d, "lyrics": d_l
        },
        "RhythmGuitar": {
            "instrument": insts["elec_guitar"],
            "melodies": g_m, "beat_ends": g_b, "dynamics": g_d, "lyrics": g_l
        },
        "Keys": {
            "instrument": insts["synth"],  # 필요시 insts["piano"]로 교체 가능
            "melodies": k_m, "beat_ends": k_b, "dynamics": k_d, "lyrics": k_l
        }
    }

    # ---- 포인트 라인(옵션) ----
    if point_inst and point_inst.lower() not in ["none", ""]:
        resolved = []
        if point_inst.lower() == "auto":
            names_pool = _normalize_point_choices(POINT_CHOICES_ROCK)
            pick_n = min(2, len(names_pool))
            if pick_n > 0:
                names = random.sample(names_pool, k=pick_n)
                resolved = [(n, get_point_instrument(n)) for n in names]
        else:
            names = [s.strip() for s in point_inst.split(",") if s.strip()]
            for n in names:
                inst_obj = get_point_instrument(n)  # 유효하지 않으면 ValueError 발생
                resolved.append((n, inst_obj))

        for name, inst_obj in resolved:
            pt_m, pt_b, pt_d, pt_l = generate_point_line(
                chords, phrase_len=4, density=point_density, key=point_key
            )
            pt_m, pt_b, pt_d, pt_l = fix_beats(pt_m, pt_b, pt_d, pt_l, total_beats=total_beats)
            pt_m, pt_b, pt_d, pt_l = clip_and_fill_rests(
                pt_m, pt_b, pt_d, pt_l, bar_len=4.0, total_beats=total_beats
            )
            parts_data[f"Point_{name}"] = {
                "instrument": inst_obj,
                "melodies": pt_m, "beat_ends": pt_b, "dynamics": pt_d, "lyrics": pt_l
            }

    # ---- 출력 ----
    score_data = {"key": "C", "time_signature": "4/4", "tempo": tempo, "clef": "treble"}
    tag = f"{drum_style}-{gtr_style}-{keys_style}{'-shell' if keys_shell else ''}"
    xml_path = os.path.join(out_dir, f"rock_{tag}.xml")
    midi_path = os.path.join(out_dir, f"rock_{tag}.mid")

    process_and_output_score(parts_data, score_data, musicxml_path=xml_path, midi_path=midi_path, show_html=False)

    return {"midi_path": midi_path, "musicxml_path": xml_path, "tag": tag}