# SongMaker/useSongMaker_Rock.py
import sys, os, json, argparse, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

DEFAULT_ROCK_JSON = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/chord_JSON/tmp_selected_progression.json"

from ai_song_maker.score_helper import process_and_output_score
from instruments.gm_instruments import get_rock_band_instruments
from Patterns_Rock.Drum.rockDrumPatterns import generate_rock_drum_pattern
from Patterns_Rock.Guitar.rythmGuitarPatterns import generate_rock_rhythm_guitar
from Patterns_Rock.Piano.rockKeysPatterns import generate_rock_keys
from utils.humanize import humanize_melody

def load_progression(json_path=None, fallback=None):
    if json_path and os.path.exists(json_path):
        with open(json_path,'r',encoding='utf-8') as f:
            data=json.load(f)
        return data.get("progression") or data.get("rock_chords") or fallback
    return fallback

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--json",
        help="코드 진행 JSON 경로(선택). {'progression':[...], 'genre':'rock'} 형식",
        default=None
    )
    ap.add_argument("--drum", help="드럼 스타일: straight8/straight16/halfTime/punk8/tomGroove", default="auto")
    ap.add_argument("--gtr",  help="기타 스타일: power8/sync16/offChop", default="auto")
    ap.add_argument("--keys", help="키즈 스타일: arp4/blockPad/riffHook", default="auto")
    ap.add_argument("--tempo", type=int, default=120)
    args = ap.parse_args()

    # 1) JSON 경로 결정: 인자로 주면 그걸 우선, 없으면 rock 기본 경로
    json_path = args.json or DEFAULT_ROCK_JSON

    # 2) 진행 불러오기
    chords = load_progression(json_path, fallback=["C","G","Am","F"]*2)

    # (선택) genre 확인: rock 아니면 경고
    try:
        import json, os
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("genre") and meta["genre"].lower() != "rock":
                print(f"⚠️  JSON의 genre='{meta['genre']}' 입니다. rock과 다릅니다. 그래도 진행을 사용합니다.")
    except Exception:
        pass
    args = ap.parse_args()


    num_bars = len(chords)
    insts = get_rock_band_instruments()

    # 스타일 선택
    drum_style = args.drum if args.drum!="auto" else random.choice(["straight8","straight16","halfTime","punk8","tomGroove"])
    gtr_style  = args.gtr  if args.gtr !="auto" else random.choice(["power8","sync16","offChop"])
    keys_style = args.keys if args.keys!="auto" else random.choice(["arp4","blockPad","riffHook"])

    # 1) 드럼
    d_m, d_b, d_d, d_l = generate_rock_drum_pattern(measures=num_bars, style=drum_style, density="med", fill_prob=0.10)

    # 2) 기타
    g_m, g_b, g_d, g_l = generate_rock_rhythm_guitar(chords, style=gtr_style, chug_prob=0.35)
    g_m, g_b, _ = humanize_melody(g_m, g_b, len_jitter=0.04, vel_base=84, vel_jitter=8, rest_prob=0.02)

    # 3) 키즈/신스
    k_m, k_b, k_d, k_l = generate_rock_keys(chords, style=keys_style)
    k_m, k_b, _ = humanize_melody(k_m, k_b, len_jitter=0.06, vel_base=72, vel_jitter=10, rest_prob=0.05)

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
            "instrument": insts["synth"],  # 혹은 insts['piano'] 로 바꿔도 OK
            "melodies": k_m, "beat_ends": k_b, "dynamics": k_d, "lyrics": k_l
        }
    }

    score_data = {"key":"C","time_signature":"4/4","tempo":args.tempo,"clef":"treble"}
    out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi"
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{drum_style}-{gtr_style}-{keys_style}"
    musicxml_path = f"{out_dir}/rock_{tag}.xml"
    midi_path     = f"{out_dir}/rock_{tag}.mid"

    process_and_output_score(parts_data, score_data, musicxml_path, midi_path, show_html=False)
    print(f"✅ ROCK 생성 완료! styles = Drum:{drum_style} / Gtr:{gtr_style} / Keys:{keys_style}")
    print("→", midi_path)

if __name__ == "__main__":
    main()