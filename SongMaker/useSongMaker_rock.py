# SongMaker/useSongMaker_rock.py
import os
import random
import tempfile
from typing import Optional, List, Dict

from dotenv import load_dotenv
load_dotenv()

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
    seed: Optional[int] = None,
) -> Dict[str, str]:
    """
    ROCK 트랙(드럼/기타/키 + 선택 포인트 라인)을 생성하고 MIDI/MusicXML 경로를 반환한다.
    콘솔 입력 없이 options만으로 동작. Jazz/Pop과 동일한 서명/반환 형식.
    """
    # 시드 고정(재현성)
    if seed is not None:
        random.seed(seed)

    # 입력 검증
    chords = progression or []
    if not chords:
        raise ValueError("progression(코드 진행)이 비었습니다.")
    num_bars = len(chords)
    total_beats = 4.0 * num_bars

    # 출력 디렉토리(.env -> 인자 -> 임시폴더 순)
    if out_dir is None:
        env_dir = os.getenv("CBB_RECORDINGS_DIR")
        out_dir = env_dir or tempfile.mkdtemp(prefix="rock_output_")
    os.makedirs(out_dir, exist_ok=True)

    # 악기 셋 & 스타일 결정
    insts = get_rock_band_instruments()
    drum_style = drum if drum != "auto" else random.choice(
        ["straight8", "straight16", "halfTime", "punk8", "tomGroove", "rock8"]
    )
    gtr_style  = gtr  if gtr  != "auto" else random.choice(["power8", "sync16", "offChop"])
    keys_style = keys if keys != "auto" else random.choice(["arp4", "blockPad", "riffHook"])

    # ---- 드럼 ----
    try:
        d_m, d_b, d_d, d_l = generate_rock_drum_pattern(
            measures=num_bars, style=drum_style, fill_prob=0.08, seed=seed
        )
    except TypeError:
        # 오래된 시그니처 호환
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


# ─────────────────────────────────────────────────────────
# CLI entry: 선택한 진행으로 MIDI/MusicXML 생성해서 원하는 폴더에 저장
if __name__ == "__main__":
    import argparse, json, time
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Generate Rock track (MIDI/MusicXML)")
    src = ap.add_mutually_exclusive_group()
    # 1) 직접 진행 전달
    src.add_argument("--progression", type=str,
                     help='8개 이상 코드: 예) "C5 G5 A5 F5 C5 G5 A5 F5"')
    # 2) LSTM CLI가 만든 임시 JSON 사용 (가장 흔한 경로)
    src.add_argument("--use-last", action="store_true",
                     help="predict_next_chord.py가 저장한 tmp_selected_progression.json 사용")

    ap.add_argument("--tempo", type=int, default=120)
    ap.add_argument("--drum",  type=str, default="auto",
                    choices=["auto","straight8","straight16","halfTime","punk8","tomGroove","rock8"])
    ap.add_argument("--gtr",   type=str, default="auto",
                    choices=["auto","power8","sync16","offChop"])
    ap.add_argument("--keys",  type=str, default="auto",
                    choices=["auto","arp4","blockPad","riffHook"])
    ap.add_argument("--keys-shell", action="store_true",
                    help="Keys에 쉘 보이싱 추가")
    ap.add_argument("--point-inst", type=str, default="none",
                    help='예: "auto" | "distortion_guitar, lead_square" | "none"')
    ap.add_argument("--point-density", type=str, default="light")
    ap.add_argument("--point-key", type=str, default="C")

    ap.add_argument("--outdir", type=str,
                    default=os.getenv("CBB_RECORDINGS_DIR", "/Users/simjuheun/Desktop/myProject/New_LSTM/recordings"),
                    help="결과 저장 폴더 (.env의 CBB_RECORDINGS_DIR 우선)")
    ap.add_argument("--name", type=str, default="take",
                    help="파일 접두사(겹치지 않게 타임스탬프가 뒤에 붙습니다)")
    ap.add_argument("--seed", type=int, default=None,
                    help="랜덤 시드(재현성)")

    args = ap.parse_args()

    # 인자 없이 실행되면 rock용 tmp_selected_progression.json 자동 사용
    if not args.progression and not args.use_last:
        default_tmp = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/chord_JSON/tmp_selected_progression.json"
        if os.path.exists(default_tmp):
            args.use_last = True
            print("ℹ️ 인자 없이 실행되어 tmp_selected_progression.json 를 사용합니다 (--use-last).")
        else:
            raise SystemExit("진행 입력이 없습니다. --use-last 또는 --progression 을 지정하세요.")

    # 진행 소스 결정
    progression: List[str] = []
    if args.use_last:
        # LSTM 예측 CLI가 저장한 tmp 파일들 중 존재하는 것 검색
        candidates = [
            "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/chord_JSON/tmp_selected_progression.json",
            "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi/chord_JSON/tmp_selected_progression.json",
            "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/chord_JSON/tmp_selected_progression.json",
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
        # 공백/콤마 구분 허용
        text = args.progression.strip()
        toks = [t.strip() for t in (text.split(",") if "," in text else text.split())]
        if len(toks) < 4:
            raise SystemExit("진행은 최소 4코드 이상을 권장합니다.")
        progression = toks

    # 출력 폴더 준비
    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    # 트랙 생성
    result = generate_rock_track(
        progression=progression,
        tempo=args.tempo,
        drum=args.drum,
        gtr=args.gtr,
        keys=args.keys,
        point_inst=args.point_inst,
        point_density=args.point_density,
        point_key=args.point_key,
        keys_shell=args.keys_shell,
        out_dir=str(outdir),
        seed=args.seed,
    )

    # 결과 파일 이름을 접두사+타임스탬프로 보기 좋게 변경(겹침 방지)
    ts = time.strftime("%Y%m%d-%H%M%S")
    tag = result.get("tag", "rock")
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