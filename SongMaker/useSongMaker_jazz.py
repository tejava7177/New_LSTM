# SongMaker/useSongMaker_jazz.py
import sys, os, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from ai_song_maker.score_helper import process_and_output_score
from music21 import instrument
from Patterns_Jazz.Drum.jazzDrumPatterns import generate_jazz_drum_pattern
from Patterns_Jazz.Piano.jazzPianoPatterns import generate_jazz_piano_pattern
from utils.humanize import humanize_melody  # 있으면 약간만 사용


# 사용자 입력(또는 고정)
predicted_chords = ["Dm7", "G7", "Cmaj7", "Fmaj7"] * 2
num_bars = len(predicted_chords)

# Jazz 드럼 생성 (스타일 랜덤)
style   = random.choice(["medium_swing", "up_swing", "two_feel", "shuffle_blues", "brush_ballad"])
mel, beats, dyn, lyr = generate_jazz_drum_pattern(
    measures=num_bars,
    style=style,          # None이면 내부에서 랜덤
    density="medium",     # "low"/"medium"/"high"
    fill_prob=0.12,       # measure 끝에 fill 확률
    seed=None             # 재현 원하면 정수 지정
)

# 피아노
pn_style = random.choice(["swing_shells","swing_block","bossa_like","ballad_2","quartal_modal"])
p_m, p_b, p_d, p_l = generate_jazz_piano_pattern(predicted_chords, style=pn_style, density="medium")

# (원한다면 아주 약하게 휴먼라이즈)
# p_m, p_b, _ = humanize_melody(p_m, p_b, len_jitter=0.04, vel_base=72, vel_jitter=6, rest_prob=0.03)

parts_data = {
    "JazzDrums": {
        "instrument": instrument.SnareDrum(),  # percussion 파트. (RideCymbals()도 OK)
        "melodies" : mel,
        "beat_ends": beats,
        "dynamics" : dyn,
        "lyrics"   : lyr,
    },

    "JazzPiano": {
        "instrument": instrument.Piano(),   # 또는 ElectricPiano()
        "melodies": p_m,
        "beat_ends": p_b,
        "dynamics": p_d,
        "lyrics": p_l
    }
}

score_data = {
    "key": "C",
    "time_signature": "4/4",
    "tempo": 140,     # 스윙/업스윙 템포
    "clef": "treble"
}

out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi"
os.makedirs(out_dir, exist_ok=True)
musicxml_path = f"{out_dir}/jazz_drums_{style}.xml"
midi_path     = f"{out_dir}/jazz_drums_{style}.mid"

process_and_output_score(parts_data,
                         score_data,
                         musicxml_path=musicxml_path,
                         midi_path=midi_path,
                         show_html=False)

print(f"✅ Jazz Drum 생성 완료! style={style}, + Piano({pn_style}) 생성 완료!")
print("→", midi_path)