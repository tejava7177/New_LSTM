# SongMaker/useSongMaker_pop.py
import sys, os, json, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from ai_song_maker.score_helper import process_and_output_score
from instruments.gm_instruments import get_rock_band_instruments   # 공용 세트 사용
from Patterns_Pop.Drum.popDrumPatterns import generate_pop_drum_pattern
from Patterns_Pop.Guitar.popGuitarPatterns import generate_pop_rhythm_guitar
from Patterns_Pop.Keys.popKeysPatterns import generate_pop_keys
from Patterns_Rock.Lead.rockPointLines import generate_point_line   # 간단 훅 재사용
from Patterns_Pop.PointInst.point_inst_list import select_point_instruments
from utils.timing_pop import fix_beats, clip_and_fill_rests

# 1) 코드 진행 로드
PROG_PATH = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/chord_JSON/tmp_selected_progression.json"
with open(PROG_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
chords = data.get("progression", ["C","Am","F","G"]*2)
num_bars = len(chords); total_beats = 4.0 * num_bars
print("🎧 POP 코드 진행:", chords)

# 2) 스타일 선택(POP 지향)
drum_style = random.choice(["fourFloor","backbeat","halfTime","edm16"])
gtr_style  = random.choice(["pm8","clean_arp","chop_off"])
keys_style = random.choice(["pad_block","pop_arp","broken8"])

# 3) 드럼
d_m, d_b, d_d, d_l = generate_pop_drum_pattern(measures=num_bars, style=drum_style, clap_prob=0.5)
d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, grid=0.25, total_beats=total_beats)
d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l, 2.0, 0.25)

# 4) 기타
g_m, g_b, g_d, g_l = generate_pop_rhythm_guitar(chords, style=gtr_style)
g_m, g_b, g_d, g_l = fix_beats(g_m, g_b, g_d, g_l, grid=0.25, total_beats=total_beats)
g_m, g_b, g_d, g_l = clip_and_fill_rests(g_m, g_b, g_d, g_l, 2.0, 0.25)

# 5) 키즈(패드/아르페지오)
k_m, k_b, k_d, k_l = generate_pop_keys(chords, style=keys_style, add_shell=True)
k_m, k_b, k_d, k_l = fix_beats(k_m, k_b, k_d, k_l, grid=0.25, total_beats=total_beats)
k_m, k_b, k_d, k_l = clip_and_fill_rests(k_m, k_b, k_d, k_l, 2.0, 0.25)

# 6) 포인트 악기(여러 개 선택 가능)
pt_specs = select_point_instruments()
point_parts = {}
for name, inst in pt_specs:
    try:
        p_m, p_b, p_d, p_l = generate_point_line(chords, phrase_len=4, density="light", pickup_prob=0.6)
    except TypeError:
        p_m, p_b, p_d, p_l = generate_point_line(chords, phrase_len=4, density="light")
    p_m, p_b, p_d, p_l = fix_beats(p_m, p_b, p_d, p_l, grid=0.25, total_beats=total_beats)
    p_m, p_b, p_d, p_l = clip_and_fill_rests(p_m, p_b, p_d, p_l, 1.0, 0.25)  # 짧은 훅

    point_parts[f"Point_{name}"] = {
        "instrument": inst,
        "melodies": p_m, "beat_ends": p_b, "dynamics": p_d, "lyrics": p_l
    }

# 7) 파트 조립/출력
insts = get_rock_band_instruments()  # drum/synth/guitar 공용
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
parts_data.update(point_parts)

score_data = {"key": "C", "time_signature": "4/4", "tempo": 100, "clef": "treble"}
out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi"
os.makedirs(out_dir, exist_ok=True)
tag = f"{drum_style}-{gtr_style}-{keys_style}"
musicxml_path = f"{out_dir}/pop_{tag}.xml"
midi_path     = f"{out_dir}/pop_{tag}.mid"

from ai_song_maker.score_helper import process_and_output_score
process_and_output_score(parts_data, score_data, musicxml_path, midi_path, show_html=False)

pnames = ", ".join(n for n,_ in pt_specs) if pt_specs else "none"
print(f"✅ POP 생성 완료! Drum:{drum_style} / Gtr:{gtr_style} / Keys:{keys_style} / Point:{pnames}")
print("→", midi_path)