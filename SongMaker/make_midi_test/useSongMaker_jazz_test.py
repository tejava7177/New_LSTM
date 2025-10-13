# make_midi_test/useSongMaker_jazz_test.py
# -*- coding: utf-8 -*-
import os, random, tempfile
from typing import Optional, List, Dict, Tuple
from music21 import instrument, harmony, pitch as m21pitch

# 공용 출력 유틸(프로젝트 기존 모듈 재사용)
from SongMaker.ai_song_maker.score_helper import process_and_output_score
from SongMaker.utils.timing_jazz import fix_beats, clip_and_fill_rests

# 테스트 전용(드럼/리드)
from SongMaker.make_midi_test.jazzDrumPatterns_Test import generate_jazz_drum_pattern_variation
from SongMaker.make_midi_test.leadGuide_Test import generate_lead_sax_points

# variation plan이 있으면 쓰고, 없으면 간단 폴백
try:
    from SongMaker.make_midi_test.variation.variation_engine import sample_variation
except Exception:
    def sample_variation(num_bars: int, seed: Optional[int] = None):
        r = random.Random(seed)
        class P: pass
        p = P()
        p.seed = seed if seed is not None else r.randint(1, 1_000_000_000)
        p.drum_style = r.choice(["brush_ballad","two_feel","medium_swing","shuffle_blues"])
        p.comp_style = "shell"
        class H: pass
        p.humanize = H(); p.humanize.vel_jitter = 6
        p.fill_prob = 0.10
        p.phrase_len = 4
        p.point_inst = None
        p.point_density = "light"
        return p

# -------------------
# 내부 헬퍼 (공간·정합 보장)
# -------------------
def _sanitize_sequence(m, b, d, l, total_beats: float, default_dyn: int = 80):
    """
    - beat_end 단조 증가/상한(total_beats-ε) 보정
    - dynamics를 int(1~127)로 매핑
    - 리스트 길이 동기화(최소 길이에 맞춤)
    """
    n = min(len(m), len(b), len(d), len(l))
    m, b, d, l = m[:n], b[:n], d[:n], l[:n]
    out_m, out_b, out_d, out_l = [], [], [], []
    last = 0.0
    eps = 1e-6
    for i in range(n):
        end = float(b[i])
        if end <= last:
            end = last + 0.12
        end = min(end, total_beats - eps)
        last = end

        dv = d[i]
        if isinstance(dv, str):
            mp = {"pp": 40,"p":55,"mp":70,"mf":80,"f":95,"ff":110}
            dv = mp.get(dv.lower(), default_dyn)
        try:
            dv = int(dv)
        except Exception:
            dv = default_dyn
        dv = max(1, min(127, dv))

        out_m.append(m[i])
        out_b.append(end)
        out_d.append(dv)
        out_l.append(l[i])
    return out_m, out_b, out_d, out_l

def _parse_cs(sym: Optional[str]) -> harmony.ChordSymbol:
    try:
        s = sym.strip() if sym else "C"
        cs = harmony.ChordSymbol(s)
        if not cs.pitches:
            cs = harmony.ChordSymbol(s[0].upper())
        return cs
    except Exception:
        return harmony.ChordSymbol("C")

def _fit_register(midi: int, low: int = 52, high: int = 84) -> int:
    if midi is None: midi = 64
    while midi < low: midi += 12
    while midi > high: midi -= 12
    return midi

def _shell_voicing(cs: harmony.ChordSymbol) -> List[str]:
    """3·7 중심 얇은 보이싱을 문자열 리스트로 반환."""
    try:
        root_m = int(cs.root().midi) if cs.root() else 60
    except Exception:
        root_m = 60
    fig = (cs.figure or "").lower()
    is_maj = ("maj" in fig) or cs.isMajorTriad()
    third   = _fit_register(root_m + (4 if is_maj else 3), 48, 76)
    seventh = _fit_register(root_m + (11 if ("maj7" in fig or "Δ" in fig) else 10), 48, 76)

    names = [m21pitch.Pitch(third).nameWithOctave,
             m21pitch.Pitch(seventh).nameWithOctave]
    # 가끔 9th 추가(희박)
    if "9" in fig and random.random() < 0.25:
        ninth = _fit_register(root_m + 14, 52, 84)
        names.append(m21pitch.Pitch(ninth).nameWithOctave)
    # 중복 제거 + 정렬은 크게 의미 없지만 안전 차원
    return sorted(list(dict.fromkeys(names)))

def style_shell_sparse(
    chords: List[str],
    seed: Optional[int] = None
) -> Tuple[List[List[str]], List[float], List[int], List[str]]:
    """
    '희박·롱서스테인' 재즈 EP/Piano 컴핑:
      - 마디당 1~2타
      - 타점 패턴: [0.0, 2.5] 또는 [1.0, 3.0] 또는 [0.0]
      - 길이: 1.5~2.5박
      - 쉘 보이싱(3·7) 중심
    """
    r = random.Random(seed)
    m, b, d, l = [], [], [], []
    beat = 0.0
    for sym in chords:
        cs = _parse_cs(sym)
        v  = _shell_voicing(cs)
        times = r.choice([[0.0, 2.5], [1.0, 3.0], [0.0]])
        bar_start, bar_end = beat, beat + 4.0
        last_end = bar_start

        for t in times:
            onset = bar_start + t
            dur   = r.choice([1.5, 2.0, 2.5])
            end   = min(max(onset + dur, last_end + 0.12), bar_end - 1e-6)
            m.append(v)
            b.append(end)
            d.append(72)      # 중간 다이내믹
            l.append("comp")
            last_end = end
        beat += 4.0
    return m, b, d, l

# -------------------
# 메인 생성기 (베이스 없는 백킹)
# -------------------
def _choose_comp_instrument(comp_style: str):
    mapping = {
        "shell"  : [instrument.ElectricPiano(), instrument.Vibraphone(), instrument.Piano()],
        "minimal": [instrument.ElectricPiano(), instrument.Piano()],
        "drop2"  : [instrument.Piano(), instrument.ElectricPiano()],
    }
    return random.choice(mapping.get(comp_style, [instrument.ElectricPiano()]))

def _ensure_out_dir(out_dir: Optional[str]) -> str:
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="jazz_output_test_")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir

def generate_jazz_track_test(
    progression: List[str],
    tempo: int = 140,
    drum: str = "auto",
    comp: str = "shell",
    guitar: str = "none",                 # 사용 안 함(튀지 않게)
    lead: str = "sax",                    # "sax" | "none"
    lead_per_bar: Tuple[int, int] = (1, 1),
    lead_register: Tuple[int, int] = (64, 81),
    lead_tension_prob: float = 0.10,
    out_dir: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict[str, str]:
    if not progression:
        raise ValueError("progression(코드 진행)이 비었습니다.")
    num_bars = len(progression)
    total_beats = 4.0 * num_bars

    plan = sample_variation(num_bars=num_bars, seed=seed)
    out_dir = _ensure_out_dir(out_dir)

    drum_style = drum if drum != "auto" else plan.drum_style
    comp_style = comp if comp != "auto" else plan.comp_style

    # --- DRUMS (단일 파트) ---
    d_m, d_b, d_d, d_l = generate_jazz_drum_pattern_variation(
        measures=num_bars, style=drum_style, density="medium",
        fill_prob=plan.fill_prob, seed=plan.seed
    )
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, total_beats=total_beats)
    d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l)
    d_m, d_b, d_d, d_l = _sanitize_sequence(d_m, d_b, d_d, d_l, total_beats, default_dyn=90)

    # --- COMP (희박 EP/Piano) ---
    p_m, p_b, p_d, p_l = style_shell_sparse(progression, seed=plan.seed)
    p_m, p_b, p_d, p_l = fix_beats(p_m, p_b, p_d, p_l, total_beats=total_beats)
    p_m, p_b, p_d, p_l = clip_and_fill_rests(p_m, p_b, p_d, p_l)
    p_m, p_b, p_d, p_l = _sanitize_sequence(p_m, p_b, p_d, p_l, total_beats, default_dyn=74)
    comp_inst = _choose_comp_instrument(comp_style)

    parts_data = {
        "JazzDrums": {
            "instrument": instrument.SnareDrum(),
            "melodies": d_m, "beat_ends": d_b, "dynamics": d_d, "lyrics": d_l,
        },
        "Comp": {
            "instrument": comp_inst,
            "melodies": p_m, "beat_ends": p_b, "dynamics": p_d, "lyrics": p_l,
        },
    }

    # --- LEAD (절제된 색소폰, 단일 파트) ---
    if lead and lead.lower() == "sax":
        lx_m, lx_b, lx_d, lx_l = generate_lead_sax_points(
            progression,
            seed=plan.seed,
            per_bar_minmax=lead_per_bar,
            register_low=lead_register[0],
            register_high=lead_register[1],
            tension_prob=lead_tension_prob
        )
        lx_m, lx_b, lx_d, lx_l = fix_beats(lx_m, lx_b, lx_d, lx_l, total_beats=total_beats)
        lx_m, lx_b, lx_d, lx_l = clip_and_fill_rests(lx_m, lx_b, lx_d, lx_l)
        lx_m, lx_b, lx_d, lx_l = _sanitize_sequence(lx_m, lx_b, lx_d, lx_l, total_beats, default_dyn=80)

        # 중복 파트 방지: 항상 하나의 LeadSax만
        parts_data["LeadSax"] = {
            "instrument": instrument.TenorSaxophone(),
            "melodies": lx_m, "beat_ends": lx_b, "dynamics": lx_d, "lyrics": lx_l,
        }

    # --- 파일 출력 ---
    score_data = {"key": "C", "time_signature": "4/4", "tempo": tempo, "clef": "treble"}
    tag = f"{drum_style}-{comp_style}-BASSLESS{'-sax' if (lead and lead=='sax') else ''}-seed{plan.seed}"
    xml_path = os.path.join(out_dir, f"jazz_test_{tag}.xml")
    midi_path = os.path.join(out_dir, f"jazz_test_{tag}.mid")

    process_and_output_score(parts_data, score_data, musicxml_path=xml_path, midi_path=midi_path, show_html=False)
    return {"midi_path": midi_path, "musicxml_path": xml_path, "tag": tag}