# SongMaker/useSongMaker.py
import sys, os, random
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from ai_song_maker.score_helper import process_and_output_score
from instruments.gm_instruments       import get_rock_band_instruments
from Patterns_Rock.Drum.randomDrumPattern   import generate_random_drum_pattern
from Patterns_Rock.Guitar.randomGuitarPattern import generate_random_guitar_pattern
from Patterns_Rock.Piano.randomPianoRhythm    import generate_random_piano_rhythms
from utils.humanize                  import humanize_melody
from utils.debug_utils import inspect_beats

# ─────────────────────────── 입력 코드 진행 ───────────────────────────
predicted_chords = ["C", "G", "Am", "F", "C", "G", "F", "C"]
num_bars         = len(predicted_chords)
insts            = get_rock_band_instruments()                # GM 번호 → Instrument

# ── 1) Piano (신스 역할)
p_m, p_b, _, _   = generate_random_piano_rhythms(predicted_chords, pattern="arpeggio")
p_m, p_b, p_vel  = humanize_melody(p_m, p_b,
                                   len_jitter=0.10, vel_base=72,
                                   vel_jitter=8,  rest_prob=0.10)
p_dyn            = ["mf" if v > 75 else "mp" for v in p_vel]
p_lyr            = [""] * len(p_m)

# ── 2) Rhythm Guitar
g_m, g_b, _, _   = generate_random_guitar_pattern(predicted_chords, pattern="random")
g_m, g_b, g_vel  = humanize_melody(g_m, g_b,
                                   len_jitter=0.08, vel_base=82,
                                   vel_jitter=10, rest_prob=0.05)
g_dyn            = ["f" if v > 88 else "mf" for v in g_vel]
g_lyr            = [""] * len(g_m)

# ── 3) Drums
# --- 3) Drums
d_m, d_b, d_d, d_l = generate_random_drum_pattern(
    measures=num_bars,
    style=random.choice(["rock8", "rock16", "halfTime"]),
    fill_prob=0.08
)
# ───────────────────────── parts_data 조립 ────────────────────────────
parts_data = {
    "Synth": {
        "instrument": insts["synth"],       # GM 81 (Lead 1 Square or 비슷)
        "melodies" : p_m,
        "beat_ends": p_b,
        "dynamics" : p_dyn,
        "lyrics"   : p_lyr
    },
    "RhythmGuitar": {
        "instrument": insts["elec_guitar"], # GM 30 (Overdrive Guitar)
        "melodies" : g_m,
        "beat_ends": g_b,
        "dynamics" : g_dyn,
        "lyrics"   : g_lyr
    },
    "Drums": {
    "instrument": insts["drum"],   # SnareDrum / channel 10
    "melodies" : d_m,
    "beat_ends": d_b,
    "dynamics" : d_d,   # ← 수정: d_dyn → d_d
    "lyrics"   : d_l    # ← 수정: d_lyr → d_l
}
}

score_data = {
    "key": "C",
    "time_signature": "4/4",
    "tempo": 120,
    "clef": "treble"
}

# inspect_beats("Synth", p_b)
# inspect_beats("RhythmGuitar", g_b)
# inspect_beats("Drums", d_b)

out_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi"
os.makedirs(out_dir, exist_ok=True)
musicxml_path = f"{out_dir}/rock_sample.xml"
midi_path     = f"{out_dir}/rock_sample.mid"

process_and_output_score(parts_data,
                         score_data,
                         musicxml_path=musicxml_path,
                         midi_path=midi_path,
                         show_html=False)

print("✅ Humanized MIDI / MusicXML 생성 완료!")