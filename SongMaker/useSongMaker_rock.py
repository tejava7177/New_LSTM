# SongMaker/useSongMaker_Rock.py
import sys, os, json, argparse, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from utils.timing import fix_beats
from ai_song_maker.score_helper import process_and_output_score
from instruments.gm_instruments import get_rock_band_instruments
from Patterns_Rock.Drum.rockDrumPatterns import generate_rock_drum_pattern
from Patterns_Rock.Guitar.rhythmGuitarPatterns import generate_rock_rhythm_guitar
from Patterns_Rock.Piano.rockKeysPatterns import generate_rock_keys

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
    ap.add_argument("--tempo", type=int, default=120)
    args = ap.parse_args()

    json_path = args.json or DEFAULT_ROCK_JSON
    chords = load_progression(json_path, fallback=["C","G","Am","F"]*2)
    if not chords:
        raise ValueError("코드 진행을 불러오지 못했습니다.")
    num_bars = len(chords)
    total_beats = 4.0 * num_bars

    insts = get_rock_band_instruments()
    drum_style = args.drum if args.drum != "auto" else random.choice(
        ["straight8", "straight16", "halfTime", "punk8", "tomGroove", "rock8"]
    )
    gtr_style  = args.gtr  if args.gtr  != "auto" else random.choice(
        ["power8", "sync16", "offChop"]
    )
    keys_style = args.keys if args.keys != "auto" else random.choice(
        ["arp4", "blockPad", "riffHook"]
    )

    # Drums
    d_m, d_b, d_d, d_l = generate_rock_drum_pattern(
        measures=num_bars, style=drum_style, fill_prob=0.08
    )
    d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, grid=0.25, total_beats=total_beats)

    # Guitar
    g_m, g_b, g_d, g_l = generate_rock_rhythm_guitar(chords, style=gtr_style)
    g_m, g_b, g_d, g_l = fix_beats(g_m, g_b, g_d, g_l, grid=0.25, total_beats=total_beats)

    # Keys
    k_m, k_b, k_d, k_l = generate_rock_keys(chords, style=keys_style, add_shell=args.keys_shell)
    k_m, k_b, k_d, k_l = fix_beats(k_m, k_b, k_d, k_l, grid=0.25, total_beats=total_beats)

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
            "instrument": insts["synth"],         # 필요하면 piano로 변경 가능
            "melodies": k_m, "beat_ends": k_b, "dynamics": k_d, "lyrics": k_l
        }
    }

    score_data = {"key": "C", "time_signature": "4/4", "tempo": args.tempo, "clef": "treble"}
    out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi"
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{drum_style}-{gtr_style}-{keys_style}{'-shell' if args.keys_shell else ''}"
    musicxml_path = f"{out_dir}/rock_{tag}.xml"
    midi_path     = f"{out_dir}/rock_{tag}.mid"

    process_and_output_score(parts_data, score_data, musicxml_path, midi_path, show_html=False)
    print(f"✅ ROCK 생성 완료! Drum:{drum_style} / Gtr:{gtr_style} / Keys:{keys_style}{' (+shell)' if args.keys_shell else ''}")
    print("→", midi_path)

if __name__ == "__main__":
    main()