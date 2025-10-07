# make_midi_test/useSongMaker_jazz_test.py
# -*- coding: utf-8 -*-
import os, sys, random, tempfile
from typing import Optional, List, Dict

# ----------------------- dual-run bootstrap -----------------------
# (1) 모듈 실행: python -m SongMaker.make_midi_test.generate_jazz_variants
# (2) 스크립트 실행: python /.../make_midi_test/useSongMaker_jazz_test.py
_THIS_DIR = os.path.dirname(__file__)
# New_LSTM 디렉토리를 sys.path[0]에 넣어 패키지/스크립트 모드 모두 지원
sys.path.insert(0, os.path.abspath(os.path.join(_THIS_DIR, "..", "..")))
# ---------------------------------------------------------------

from music21 import instrument

# 본 프로젝트 공용 모듈(절대 임포트 고정)
from SongMaker.ai_song_maker.score_helper import process_and_output_score
from SongMaker.Patterns_Jazz.Piano.jazzPianoPatterns import style_bass_backing_minimal
from SongMaker.Patterns_Jazz.PointInst.point_inst_list import get_point_instrument
from SongMaker.Patterns_Jazz.Lead.jazzPointLines import generate_point_line
from SongMaker.utils.timing_jazz import fix_beats, clip_and_fill_rests

# 테스트용(이 디렉토리 안의 래퍼/변주 샘플러)
try:
    # 권장: 패키지 경로
    from SongMaker.make_midi_test.variation.variation_engine import sample_variation
    from SongMaker.make_midi_test.jazzDrumPatterns_Test import generate_jazz_drum_pattern_variation
except Exception:
    # 폴백: 스크립트 모드에서 직접 폴더 참조
    from variation.variation_engine import sample_variation                      # make_midi_test/variation/variation_engine.py
    from jazzDrumPatterns_Test import generate_jazz_drum_pattern_variation      # make_midi_test/jazzDrumPatterns_Test.py

# ----------------------- dynamics utils -----------------------
DYN_MAP = {
    "pp": 40, "p": 55, "mp": 70, "mf": 85, "f": 100, "ff": 115
}

def _to_velocity(v, default=85) -> int:
    """문자열/숫자/None/복합형을 1..127 범위 int 벨로시티로 안전 변환"""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return int(max(1, min(127, int(v))))
    if isinstance(v, str):
        vs = v.strip().lower()
        if vs.isdigit():
            return int(max(1, min(127, int(vs))))
        if vs in DYN_MAP:
            return DYN_MAP[vs]
        return default
    if isinstance(v, dict) and "vel" in v:
        return _to_velocity(v["vel"], default=default)
    if isinstance(v, (list, tuple)) and v:
        return _to_velocity(v[0], default=default)
    return default

def _sanitize_dynamics(dynamics: List, target_len: int, default=85) -> List[int]:
    """다이내믹 리스트를 숫자화 + 길이 보정(pad/trim)"""
    if not dynamics:
        vals = [default] * target_len
    else:
        vals = [_to_velocity(x, default=default) for x in dynamics]
        if len(vals) < target_len:
            vals = vals + [default] * (target_len - len(vals))
        elif len(vals) > target_len:
            vals = vals[:target_len]
    return vals

def _apply_humanize(dynamics: List[int], vel_jitter: int) -> List[int]:
    """숫자화된 다이내믹에만 지터 적용"""
    out = []
    for v in dynamics:
        jitter = random.randint(-vel_jitter, vel_jitter)
        out.append(max(1, min(127, int(v) + jitter)))
    return out
# --------------------------------------------------------------

def _choose_comp_instrument(comp_style: str):
    """컴핑 악기를 스타일 가중으로 스위칭 → 청감 다양화"""
    mapping = {
        "minimal": [instrument.ElectricPiano(), instrument.Piano()],
        "shell"  : [instrument.Piano(), instrument.ElectricPiano()],
        "drop2"  : [instrument.Piano()],
        "quartal": [instrument.Vibraphone(), instrument.ElectricPiano()],
    }
    return random.choice(mapping.get(comp_style, [instrument.ElectricPiano()]))

def generate_jazz_track_test(
    progression: List[str],
    tempo: int = 140,
    drum: str = "auto",
    comp: str = "auto",
    point_inst: str = "none",   # "none" | "auto" | "trumpet, flute"
    point_density: str = "light",
    out_dir: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict[str, str]:

    if not progression:
        raise ValueError("progression(코드 진행)이 비었습니다.")
    num_bars = len(progression)
    total_beats = 4.0 * num_bars

    # 변주 플랜(편성/폼/휴먼라이즈 등) 샘플링
    plan = sample_variation(num_bars=num_bars, seed=seed)

    # 출력 경로
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="jazz_output_test_")
    os.makedirs(out_dir, exist_ok=True)

    # 스타일 확정(사용자 지정 우선)
    drum_style = drum if drum != "auto" else plan.drum_style
    comp_style = comp if comp != "auto" else plan.comp_style

    # -------------------- DRUMS --------------------
    d_m, d_b, d_d, d_l = generate_jazz_drum_pattern_variation(
        measures=num_bars, style=drum_style, density="medium",
        fill_prob=plan.fill_prob, seed=plan.seed
    )
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, total_beats=total_beats)
    d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l)
    # 다이내믹 숫자화 + 길이 보정 + 휴먼라이즈
    d_d = _sanitize_dynamics(d_d, target_len=len(d_m), default=85)
    d_d = _apply_humanize(d_d, plan.humanize.vel_jitter)

    # -------------------- COMP --------------------
    p_m, p_b, p_d, p_l = style_bass_backing_minimal(progression, phrase_len=plan.phrase_len)
    p_m, p_b, p_d, p_l = fix_beats(p_m, p_b, p_d, p_l, total_beats=total_beats)
    p_m, p_b, p_d, p_l = clip_and_fill_rests(p_m, p_b, p_d, p_l)
    p_d = _sanitize_dynamics(p_d, target_len=len(p_m), default=82)
    p_d = _apply_humanize(p_d, plan.humanize.vel_jitter)
    comp_inst = _choose_comp_instrument(comp_style)

    parts_data = {
        "JazzDrums": {
            "instrument": instrument.SnareDrum(),  # 렌더 단계에서 Ride/HH 매핑 가능
            "melodies": d_m, "beat_ends": d_b, "dynamics": d_d, "lyrics": d_l,
        },
        "Comp": {
            "instrument": comp_inst,
            "melodies": p_m, "beat_ends": p_b, "dynamics": p_d, "lyrics": p_l,
        },
    }

    # -------------------- POINT INST --------------------
    resolved = []
    if point_inst and point_inst.lower() not in ["none", ""]:
        # 사용자가 직접 지정
        names = [s.strip() for s in point_inst.split(",") if s.strip()]
        resolved = [(n, get_point_instrument(n)) for n in names]
    elif plan.point_inst:
        # 변주 플랜 자동 편성
        resolved = [(n, get_point_instrument(n)) for n in plan.point_inst]

    for name, inst_obj in resolved:
        try:
            m, b, d, l = generate_point_line(
                progression, phrase_len=plan.phrase_len,
                density=plan.point_density, pickup_prob=0.7
            )
        except TypeError:
            m, b, d, l = generate_point_line(
                progression, phrase_len=plan.phrase_len,
                density=plan.point_density
            )
        m, b, d, l = fix_beats(m, b, d, l, total_beats=total_beats)
        m, b, d, l = clip_and_fill_rests(m, b, d, l)
        d = _sanitize_dynamics(d, target_len=len(m), default=80)
        d = _apply_humanize(d, plan.humanize.vel_jitter)
        parts_data[f"Point_{name}"] = {
            "instrument": inst_obj,
            "melodies": m, "beat_ends": b, "dynamics": d, "lyrics": l,
        }

    # -------------------- OUTPUT --------------------
    score_data = {"key": "C", "time_signature": "4/4", "tempo": tempo, "clef": "treble"}
    tag = f"{drum_style}-{comp_style}-seed{plan.seed}"
    xml_path = os.path.join(out_dir, f"jazz_test_{tag}.xml")
    midi_path = os.path.join(out_dir, f"jazz_test_{tag}.mid")

    process_and_output_score(
        parts_data, score_data,
        musicxml_path=xml_path, midi_path=midi_path, show_html=False
    )
    return {"midi_path": midi_path, "musicxml_path": xml_path, "tag": tag}