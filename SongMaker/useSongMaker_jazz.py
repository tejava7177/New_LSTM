# SongMaker/useSongMaker_jazz.py
import sys, os, json, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from ai_song_maker.score_helper import process_and_output_score
from music21 import instrument
from Patterns_Jazz.Drum.jazzDrumPatterns import generate_jazz_drum_pattern
from Patterns_Jazz.Piano.jazzPianoPatterns import style_bass_backing_minimal
from Patterns_Jazz.PointInst.point_inst_list import select_point_instruments
from Patterns_Jazz.Lead.jazzPointLines import generate_point_line
from utils.timing_jazz import fix_beats, clip_and_fill_rests

# 1) 코드 진행 불러오기 (.json)
PROG_PATH = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi/chord_JSON/tmp_selected_progression.json"
with open(PROG_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
chords = data.get("progression", ["Dm7","G7","Cmaj7","Fmaj7"] * 2)
num_bars = len(chords)
total_beats = 4.0 * num_bars
print("🎹 불러온 코드 진행:", chords)

# 2) 드럼 (스타일 랜덤)
style = random.choice(["medium_swing", "up_swing", "two_feel", "shuffle_blues", "brush_ballad"])
d_m, d_b, d_d, d_l = generate_jazz_drum_pattern(
    measures=num_bars, style=style, density="medium", fill_prob=0.12, seed=None
)
# 드럼도 과도 길이 정리(경고 방지)
d_m, d_b, d_d, d_l = fix_beats(d_m, d_b, d_d, d_l, grid=0.25, total_beats=total_beats)
d_m, d_b, d_d, d_l = clip_and_fill_rests(d_m, d_b, d_d, d_l, 2.0, 0.25)

# 3) EP 미니멀 컴핑
p_m, p_b, p_d, p_l = style_bass_backing_minimal(chords, phrase_len=4)
p_m, p_b, p_d, p_l = fix_beats(p_m, p_b, p_d, p_l, grid=0.25, total_beats=total_beats)
p_m, p_b, p_d, p_l = clip_and_fill_rests(p_m, p_b, p_d, p_l, 2.0, 0.25)

# 4) 포인트 악기들(여러 개 가능)
pt_specs = select_point_instruments()  # [(name, instrument), ...]
point_parts = {}
for name, inst in pt_specs:
    # 포인트 라인 생성 (함수 시그니처 변경에 대비해 안전 래퍼 사용)
    try:
        pt_m, pt_b, pt_d, pt_l = generate_point_line(chords, phrase_len=4, density='light', pickup_prob=0.7)
    except TypeError:
        pt_m, pt_b, pt_d, pt_l = generate_point_line(chords, phrase_len=4, density='light')

    pt_m, pt_b, pt_d, pt_l = fix_beats(pt_m, pt_b, pt_d, pt_l, grid=0.25, total_beats=total_beats)
    pt_m, pt_b, pt_d, pt_l = clip_and_fill_rests(pt_m, pt_b, pt_d, pt_l, 2.0, 0.25)

    point_parts[f"Point_{name}"] = {
        "instrument": inst,
        "melodies": pt_m, "beat_ends": pt_b, "dynamics": pt_d, "lyrics": pt_l
    }

# 5) parts_data 조립
parts_data = {
    "JazzDrums": {
        "instrument": instrument.SnareDrum(),
        "melodies": d_m, "beat_ends": d_b, "dynamics": d_d, "lyrics": d_l,
    },
    "CompEP": {
        "instrument": instrument.ElectricPiano(),
        "melodies": p_m, "beat_ends": p_b, "dynamics": p_d, "lyrics": p_l,
    },
}
parts_data.update(point_parts)

# 6) 스코어/저장
score_data = {
    "key": "C",
    "time_signature": "4/4",
    "tempo": 140,
    "clef": "treble"
}

out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi"
os.makedirs(out_dir, exist_ok=True)
musicxml_path = f"{out_dir}/jazz_{style}.xml"
midi_path     = f"{out_dir}/jazz_{style}.mid"

process_and_output_score(parts_data, score_data, musicxml_path=musicxml_path, midi_path=midi_path, show_html=False)
pnames = ", ".join(pt_specs[i][0] for i in range(len(pt_specs))) if pt_specs else "none"
print(f"✅ Jazz 생성 완료! style={style}, point={pnames}")
print("→", midi_path)