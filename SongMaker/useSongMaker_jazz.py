import sys, os, json, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from ai_song_maker.score_helper import process_and_output_score
from music21 import instrument
from Patterns_Jazz.Drum.jazzDrumPatterns import generate_jazz_drum_pattern
from Patterns_Jazz.Piano.jazzPianoPatterns import style_bass_backing_minimal
from Patterns_Jazz.PointInst.point_inst_list import select_point_instrument
from Patterns_Jazz.Lead.jazzPointLines import generate_point_line
from utils.humanize import humanize_melody




# ──────────────────────────────────────────────
# 1) **여기서 tmp_selected_progression.json 불러오기**
PROG_PATH = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi/chord_JSON/tmp_selected_progression.json"
with open(PROG_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
predicted_chords = data["progression"]
num_bars = len(predicted_chords)
print(f"🎹 불러온 코드 진행: {predicted_chords}")

# ──────────────────────────────────────────────
# 2) Jazz 드럼 생성 (랜덤 스타일)
style   = random.choice(["medium_swing", "up_swing", "two_feel", "shuffle_blues", "brush_ballad"])
mel, beats, dyn, lyr = generate_jazz_drum_pattern(
    measures=num_bars,
    style=style,
    density="medium",
    fill_prob=0.12,
    seed=None
)

# 3) 피아노(=EP) 미니멀 컴핑
p_m, p_b, p_d, p_l = style_bass_backing_minimal(predicted_chords, phrase_len=4)

# 4) 포인트 악기
point_inst = select_point_instrument()
pt_m, pt_b, pt_d, pt_l = generate_point_line(predicted_chords, phrase_len=4, density='light', pickup_prob=0.7)

# parts_data 구성
parts_data = {
    "JazzDrums": {
        "instrument": instrument.SnareDrum(),
        "melodies" : mel,
        "beat_ends": beats,
        "dynamics" : dyn,
        "lyrics"   : lyr,
    },
    "CompEP": {
        "instrument": instrument.ElectricPiano(),
        "melodies": p_m,
        "beat_ends": p_b,
        "dynamics": p_d,
        "lyrics": p_l
    },
    "PointVibes": {
        "instrument": point_inst,
        "melodies": pt_m,
        "beat_ends": pt_b,
        "dynamics": pt_d,
        "lyrics": pt_l
    }
}

score_data = {
    "key": "C",
    "time_signature": "4/4",
    "tempo": 140,
    "clef": "treble"
}

# 결과물 저장 위치
out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi"
os.makedirs(out_dir, exist_ok=True)
musicxml_path = f"{out_dir}/jazz_drums_{style}.xml"
midi_path     = f"{out_dir}/jazz_drums_{style}.mid"

process_and_output_score(parts_data, score_data, musicxml_path=musicxml_path, midi_path=midi_path, show_html=False)

print(f"✅ Jazz Drum 생성 완료! style={style}, 미니멀 EP 컴핑 생성 완료!")
print("→", midi_path)