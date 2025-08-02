# SongMaker/useSongMaker_rock.py
import sys, os, json, argparse, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from utils.timing import fix_beats
from ai_song_maker.score_helper import process_and_output_score
from instruments.gm_instruments import get_rock_band_instruments
from Patterns_Rock.Drum.rockDrumPatterns import generate_rock_drum_pattern
from Patterns_Rock.Guitar.rhythmGuitarPatterns import generate_rock_rhythm_guitar
from Patterns_Rock.Piano.rockKeysPatterns import generate_rock_keys
from Patterns_Rock.PointInst.point_inst_list import POINT_CHOICES_ROCK, get_point_instrument
from Patterns_Rock.Lead.rockPointLines import generate_point_line

DEFAULT_ROCK_JSON = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/chord_JSON/tmp_selected_progression.json"


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

    # ⇩ 기본값 ask: 실행 중에 물어봄
    ap.add_argument(
        "--point-inst",
        help=f"포인트 악기 선택({', '.join(POINT_CHOICES_ROCK)}). "
             f"'none'이면 추가 안함, 'ask'면 실행 중에 입력 받음",
        default="ask"
    )
    ap.add_argument("--point-density", help="포인트 라인 밀도: light/med", default="light")
    ap.add_argument("--point-key", help="포인트 라인용 간단 키(C/Am 등) - 펜타토닉 기준", default="C")
    ap.add_argument("--tempo", type=int, default=120)
    args = ap.parse_args()

    # 진행 로드
    json_path = args.json or DEFAULT_ROCK_JSON
    chords = load_progression(json_path, fallback=["C", "G", "Am", "F"] * 2)
    if not chords:
        raise ValueError("코드 진행을 불러오지 못했습니다.")
    num_bars = len(chords)
    total_beats = 4.0 * num_bars

    # 악기 세팅 / 스타일 결정
    insts = get_rock_band_instruments()
    drum_style = args.drum if args.drum != "auto" else random.choice(
        ["straight8", "straight16", "halfTime", "punk8", "tomGroove", "rock8"]
    )
    gtr_style = args.gtr if args.gtr != "auto" else random.choice(
        ["power8", "sync16", "offChop"]
    )
    keys_style = args.keys if args.keys != "auto" else random.choice(
        ["arp4", "blockPad", "riffHook"]
    )

    # 드럼
    d_m, d_b, d_d, d_l = generate_rock_drum_pattern(
        measures=num_bars, style=drum_style, fill_prob=0.08
    )
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, grid=0.25, total_beats=total_beats)

    # 기타
    g_m, g_b, g_d, g_l = generate_rock_rhythm_guitar(chords, style=gtr_style)
    g_m, g_b, g_d, g_l = fix_beats(g_m, g_b, g_d, g_l, grid=0.25, total_beats=total_beats)

    # 키즈/신스
    k_m, k_b, k_d, k_l = generate_rock_keys(chords, style=keys_style, add_shell=args.keys_shell)
    k_m, k_b, k_d, k_l = fix_beats(k_m, k_b, k_d, k_l, grid=0.25, total_beats=total_beats)

    # 포인트 악기 선택(ask 모드면 인터랙티브)
    point_spec = (args.point_inst or "ask").lower()
    if point_spec == "ask":
        print("\n🎯 포인트 악기를 선택하세요. 쉼표로 여러 개 가능")
        print("   선택지:", ", ".join(POINT_CHOICES_ROCK))
        print("   (아무것도 입력하지 않으면 'none'으로 처리)")
        user_in = input("포인트 악기 입력 (예: lead_guitar, synth_lead): ").strip()
        point_spec = user_in.lower() if user_in else "none"

    # parts_data 조립
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
            "instrument": insts["synth"],  # 필요 시 insts["piano"]로 교체 가능
            "melodies": k_m, "beat_ends": k_b, "dynamics": k_d, "lyrics": k_l
        }
    }

    # 포인트 트랙(여러 개 가능)
    if point_spec != "none":
        for name in [s.strip() for s in point_spec.split(",") if s.strip()]:
            inst = get_point_instrument(name)
            if not inst:
                print(f"⚠️  알 수 없는 포인트 악기: {name} (건너뜀)")
                continue
            pt_mel, pt_beats, pt_dyn, pt_lyr = generate_point_line(
                chords, phrase_len=4, density=args.point_density, key=args.point_key
            )
            pt_mel, pt_beats, pt_dyn, pt_lyr = fix_beats(
                pt_mel, pt_beats, pt_dyn, pt_lyr, grid=0.25, total_beats=total_beats
            )
            parts_data[f"Point_{name}"] = {
                "instrument": inst,
                "melodies": pt_mel, "beat_ends": pt_beats,
                "dynamics": pt_dyn, "lyrics": pt_lyr
            }

    # 출력
    score_data = {"key": "C", "time_signature": "4/4", "tempo": args.tempo, "clef": "treble"}
    out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi"
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{drum_style}-{gtr_style}-{keys_style}{'-shell' if args.keys_shell else ''}"
    musicxml_path = f"{out_dir}/rock_{tag}.xml"
    midi_path = f"{out_dir}/rock_{tag}.mid"

    process_and_output_score(parts_data, score_data, musicxml_path, midi_path, show_html=False)
    print(f"✅ ROCK 생성 완료! Drum:{drum_style} / Gtr:{gtr_style} / Keys:{keys_style}{' (+shell)' if args.keys_shell else ''}")
    if point_spec != "none":
        print(f"   PointInst: {point_spec}")
    print("→", midi_path)


if __name__ == "__main__":
    main()