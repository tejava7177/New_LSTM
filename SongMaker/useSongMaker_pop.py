# SongMaker/useSongMaker_pop.py
import os
import random
import tempfile
from typing import Optional, List, Dict

from dotenv import load_dotenv
load_dotenv()

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
    seed: Optional[int] = None,
) -> Dict[str, str]:
    """
    POP 트랙(드럼/기타/키 + 선택 포인트 라인)을 생성하고 MIDI/MusicXML 경로를 반환한다.
    콘솔 입력/파일 읽기 없이 progression과 옵션만으로 동작한다.
    """
    # 재현성: 시드 고정(옵션)
    if seed is not None:
        random.seed(seed)

    # 입력 검증
    chords = progression or []
    if not chords:
        raise ValueError("progression(코드 진행)이 비었습니다.")
    num_bars = len(chords)
    total_beats = 4.0 * num_bars

    # 출력 디렉토리 (우선순위: 함수 인자 > 환경변수 > 임시폴더)
    if out_dir is None:
        out_dir = os.environ.get("CBB_RECORDINGS_DIR")
    if not out_dir:
        out_dir = tempfile.mkdtemp(prefix="pop_output_")
    os.makedirs(out_dir, exist_ok=True)

    # 악기 셋 & 스타일 결정
    insts = get_pop_band_instruments()
    drum_style = drum if drum != "auto" else random.choice(["fourFloor", "backbeat", "halfTime", "edm16"])
    gtr_style  = gtr  if gtr  != "auto" else random.choice(["pm8", "clean_arp", "chop_off"])
    keys_style = keys if keys != "auto" else random.choice(["pad_block", "pop_arp", "broken8"])

    # ---- 드럼 ----
    try:
        d_m, d_b, d_d, d_l = generate_pop_drum_pattern(measures=num_bars, style=drum_style, clap_prob=0.5, seed=seed)
    except TypeError:
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


# CLI 엔트리포인트: progression/--use-last 인자, 환경변수 기본값, 타임스탬프 결과 저장
if __name__ == "__main__":
    import argparse, json, time, inspect as _inspect
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Generate Pop track (MIDI/MusicXML)")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--progression", type=str, help='8개 이상 코드: 예) "C G Am F C G Am F"')
    src.add_argument("--use-last", action="store_true", help="predict_next_chord.py가 저장한 tmp_selected_progression.json 사용")

    ap.add_argument("--tempo", type=int, default=100)
    ap.add_argument("--drum", type=str, default="auto", choices=["auto","fourFloor","backbeat","halfTime","edm16"])
    ap.add_argument("--gtr",  type=str, default="auto", choices=["auto","pm8","clean_arp","chop_off"])
    ap.add_argument("--keys", type=str, default="auto", choices=["auto","pad_block","pop_arp","broken8"])
    ap.add_argument("--point-inst", type=str, default="none", help='예: "auto" | "lead_square, brass_section" | "none"')
    ap.add_argument("--point-density", type=str, default="light")
    ap.add_argument("--point-key", type=str, default="C")

    ap.add_argument("--outdir", type=str, default=os.environ.get("CBB_RECORDINGS_DIR", "/Users/simjuheun/Desktop/myProject/New_LSTM/recordings"),
                    help="결과 저장 폴더")
    ap.add_argument("--name", type=str, default="take", help="파일 접두사(겹치지 않게 타임스탬프가 뒤에 붙습니다)")
    ap.add_argument("--seed", type=int, default=None, help="랜덤 시드(재현성)")

    args = ap.parse_args()

    # 인자 없이 실행되면 pop tmp_selected_progression.json 자동 사용
    if not args.progression and not args.use_last:
        default_tmp = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/chord_JSON/tmp_selected_progression.json"
        if os.path.exists(default_tmp):
            args.use_last = True
            print("ℹ️ 인자 없이 실행되어 pop tmp_selected_progression.json 를 사용합니다 (--use-last).")
        else:
            raise SystemExit("진행 입력이 없습니다. --use-last 또는 --progression 을 지정하세요.")

    # 진행 소스 결정
    progression: List[str] = []
    if args.use_last:
        candidates = [
            "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/chord_JSON/tmp_selected_progression.json",
            "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi/chord_JSON/tmp_selected_progression.json",
            "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/chord_JSON/tmp_selected_progression.json",
        ]
        found = None
        for p in candidates:
            if os.path.exists(p):
                found = p; break
        if not found:
            raise SystemExit("tmp_selected_progression.json 을 찾지 못했습니다. --progression 으로 직접 입력하세요.")
        with open(found, "r", encoding="utf-8") as f:
            data = json.load(f)
        progression = data.get("progression", [])
        if not progression:
            raise SystemExit(f"JSON에 progression이 없습니다: {found}")
        print(f"✓ tmp progression 로드: {found}")
    else:
        text = args.progression.strip()
        toks = [t.strip() for t in (text.split(",") if "," in text else text.split())]
        if len(toks) < 4:
            raise SystemExit("진행은 최소 4코드 이상을 권장합니다.")
        progression = toks

    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    # 시그니처 체크(옵션 인자 유연성)
    sig = _inspect.signature(generate_pop_track)
    extra_kwargs = {}
    if "seed" in sig.parameters and args.seed is not None:
        extra_kwargs["seed"] = args.seed

    result = generate_pop_track(
        progression=progression,
        tempo=args.tempo,
        drum=args.drum,
        gtr=args.gtr,
        keys=args.keys,
        point_inst=args.point_inst,
        point_density=args.point_density,
        point_key=args.point_key,
        out_dir=str(outdir),
        **extra_kwargs
    )

    ts = time.strftime("%Y%m%d-%H%M%S")
    tag = result.get("tag", "pop")
    midi_src = Path(result["midi_path"])
    xml_src  = Path(result["musicxml_path"])
    midi_dst = outdir / f"{args.name}_{tag}_{ts}.mid"
    xml_dst  = outdir / f"{args.name}_{tag}_{ts}.xml"

    try:
        if midi_src.exists(): midi_src.rename(midi_dst)
        if xml_src.exists():  xml_src.rename(xml_dst)
        print(f"🎵 MIDI 저장: {midi_dst}")
        print(f"📄 MusicXML 저장: {xml_dst}")
    except Exception as e:
        print(f"파일 이름 변경 중 경고: {e}")
        print(f"원본 경로\n  MIDI: {midi_src}\n  XML : {xml_src}")