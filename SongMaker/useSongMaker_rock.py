# SongMaker/useSongMaker_rock.py
import os, json, argparse, random, tempfile
# ※ 경로 보정은 app/core/pipeline_generate.py에서 처리하므로 여긴 추가 sys.path 불필요

# 공통 유틸(rock 전용 timing 모듈을 쓰는 현재 구조 유지)
from .utils.timing_rock import fix_beats, clip_and_fill_rests
from .ai_song_maker.score_helper import process_and_output_score
from .instruments.gm_instruments import get_rock_band_instruments
from .Patterns_Rock.Drum.rockDrumPatterns import generate_rock_drum_pattern
from .Patterns_Rock.Guitar.rhythmGuitarPatterns import generate_rock_rhythm_guitar
from .Patterns_Rock.Piano.rockKeysPatterns import generate_rock_keys
from .Patterns_Rock.PointInst.point_inst_list import POINT_CHOICES_ROCK, get_point_instrument
from .Patterns_Rock.Lead.rockPointLines import generate_point_line

DEFAULT_ROCK_JSON = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/chord_JSON/tmp_selected_progression.json"

def generate_rock_track(
    progression,
    tempo=120,
    drum="auto",
    gtr="auto",
    keys="auto",
    keys_shell=False,
    point_inst="none",
    point_density="light",
    point_key="C",
    out_dir=None
):
    """
    [역할] 코드 진행과 옵션을 받아 Rock 장르 MIDI/MusicXML을 생성한다.
    [반환] dict(midi_path, musicxml_path, tag, used_styles)
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

    # 스타일 자동/선택
    insts = get_rock_band_instruments()
    drum_style = drum if drum != "auto" else random.choice(
        ["straight8", "straight16", "halfTime", "punk8", "tomGroove", "rock8"]
    )
    gtr_style = gtr if gtr != "auto" else random.choice(["power8", "sync16", "offChop"])
    keys_style = keys if keys != "auto" else random.choice(["arp4", "blockPad", "riffHook"])

    # ---- 드럼 ----
    d_m, d_b, d_d, d_l = generate_rock_drum_pattern(
        measures=num_bars, style=drum_style, fill_prob=0.08
    )
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, grid=0.25, total_beats=total_beats)
    d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l, bar_len=4.0, total_beats=total_beats, grid=0.25)

    # ---- 기타 ----
    g_m, g_b, g_d, g_l = generate_rock_rhythm_guitar(chords, style=gtr_style)
    g_m, g_b, g_d, g_l = fix_beats(g_m, g_b, g_d, g_l, grid=0.25, total_beats=total_beats)
    g_m, g_b, g_d, g_l = clip_and_fill_rests(g_m, g_b, g_d, g_l, bar_len=4.0, total_beats=total_beats, grid=0.25)

    # ---- 키즈/신스 ----
    k_m, k_b, k_d, k_l = generate_rock_keys(chords, style=keys_style, add_shell=keys_shell)
    k_m, k_b, k_d, k_l = fix_beats(k_m, k_b, k_d, k_l, grid=0.25, total_beats=total_beats)
    k_m, k_b, k_d, k_l = clip_and_fill_rests(k_m, k_b, k_d, k_l, bar_len=4.0, total_beats=total_beats, grid=0.25)

    # ---- 포인트 라인(옵션) ----
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
            "instrument": insts["synth"],
            "melodies": k_m, "beat_ends": k_b, "dynamics": k_d, "lyrics": k_l
        }
    }

    if point_inst and point_inst.lower() not in ["none", ""]:
        for name in [s.strip() for s in point_inst.split(",") if s.strip()]:
            inst = get_point_instrument(name)  # 잘못된 이름이면 내부에서 ValueError
            pt_mel, pt_beats, pt_dyn, pt_lyr = generate_point_line(
                chords, phrase_len=4, density=point_density, key=point_key
            )
            pt_mel, pt_beats, pt_dyn, pt_lyr = fix_beats(pt_mel, pt_beats, pt_dyn, pt_lyr, grid=0.25, total_beats=total_beats)
            pt_mel, pt_beats, pt_dyn, pt_lyr = clip_and_fill_rests(pt_mel, pt_beats, pt_dyn, pt_lyr, bar_len=4.0, total_beats=total_beats, grid=0.25)
            parts_data[f"Point_{name}"] = {
                "instrument": inst,
                "melodies": pt_mel, "beat_ends": pt_beats, "dynamics": pt_dyn, "lyrics": pt_lyr
            }

    # ---- 출력 ----
    score_data = {"key": "C", "time_signature": "4/4", "tempo": tempo, "clef": "treble"}
    tag = f"{drum_style}-{gtr_style}-{keys_style}{'-shell' if keys_shell else ''}"
    musicxml_path = os.path.join(out_dir, f"rock_{tag}.xml")
    midi_path     = os.path.join(out_dir, f"rock_{tag}.mid")

    process_and_output_score(parts_data, score_data, musicxml_path, midi_path, show_html=False)

    return {
        "midi_path": midi_path,
        "musicxml_path": musicxml_path,
        "tag": tag,
        "used_styles": {
            "drum": drum_style, "gtr": gtr_style, "keys": keys_style,
            "keys_shell": keys_shell, "point_inst": point_inst
        }
    }

# ------------------ 이하: 기존 CLI 유지(선택) ------------------

def load_progression(json_path=None, fallback=None):
    if json_path and os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("progression") or data.get("rock_chords") or fallback
    return fallback

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="코드 진행 JSON 경로", default=None)
    ap.add_argument("--drum", help="straight8/straight16/halfTime/punk8/tomGroove/rock8", default="auto")
    ap.add_argument("--gtr",  help="power8/sync16/offChop", default="auto")
    ap.add_argument("--keys", help="arp4/blockPad/riffHook", default="auto")
    ap.add_argument("--keys-shell", action="store_true", help="2&4 쉘 보이싱 추가")
    ap.add_argument("--point-inst", default="ask",
                    help=f"포인트 악기 선택({', '.join(POINT_CHOICES_ROCK)}). 'none'이면 추가 안함, 'ask'면 실행 중 입력")
    ap.add_argument("--point-density", default="light", help="포인트 라인 밀도: light/med")
    ap.add_argument("--point-key", default="C", help="포인트 라인용 간단 키(C/Am 등)")
    ap.add_argument("--tempo", type=int, default=120)
    args = ap.parse_args()

    # 진행 로드
    chords = load_progression(args.json, fallback=["C", "G", "Am", "F"] * 2)
    if not chords:
        raise ValueError("코드 진행을 불러오지 못했습니다.")

    # ask 모드 처리
    point_spec = args.point_inst
    if point_spec == "ask":
        print("\n🎯 포인트 악기를 선택하세요. 쉼표로 여러 개 가능")
        print("   선택지:", ", ".join(POINT_CHOICES_ROCK))
        print("   (아무것도 입력하지 않으면 'none')")
        user_in = input("포인트 악기 입력 (예: distortion_guitar, lead_square): ").strip()
        point_spec = user_in.lower() if user_in else "none"

    # 함수 호출
    result = generate_rock_track(
        progression=chords, tempo=args.tempo,
        drum=args.drum, gtr=args.gtr, keys=args.keys, keys_shell=args.keys_shell,
        point_inst=point_spec, point_density=args.point_density, point_key=args.point_key,
        out_dir="/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi"
    )

    print(f"✅ ROCK 생성 완료! → {result['midi_path']}")

if __name__ == "__main__":
    main()