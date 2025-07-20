import sys
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from ai_song_maker.score_helper import process_and_output_score
from instruments.gm_instruments import get_rock_band_instruments
from Patterns_Rock.Drum.randomDrumPattern import generate_random_drum_pattern
from Patterns_Rock.Guitar.randomGuitarPattern import generate_random_guitar_pattern
from Patterns_Rock.Piano.randomPianoRhythm import generate_random_piano_rhythms

# 1. 코드 진행 예시
predicted_chords = ["C", "G", "Am", "F", "C", "G", "F", "C"]
num_bars = len(predicted_chords)

# 2. 악기 세팅
insts = get_rock_band_instruments()

# 3. 피아노 패턴 생성 (아르페지오 리듬)
piano_mel, piano_beat, piano_dyn, piano_lyr = generate_random_piano_rhythms(
    predicted_chords,
    allowed_durations=[0.25, 0.5, 1.0, 1.5, 2.0],  # 리듬 다양화
    pattern="arpeggio"  # "arpeggio" or "block"
)

# 4. 기타 패턴 생성 (랜덤: 스트로크/아르페지오 믹스)
gtr_mel, gtr_beat, gtr_dyn, gtr_lyr = generate_random_guitar_pattern(
    predicted_chords,
    beats_per_bar=4,  # 한 마디 4박 기준
    pattern="random"  # "arpeggio" or "strum" or "random"
)

# 5. 드럼 패턴 생성 (랜덤)
drum_mel, drum_beat, drum_dyn, drum_lyr = generate_random_drum_pattern(
    measures=num_bars, beats_per_measure=4
)

# (디버깅용) -- 실제로 길이 맞는지 체크!
print("== piano_mel ==", piano_mel)
print("== piano_beat ==", piano_beat)
print("== gtr_mel ==", gtr_mel)
print("== gtr_beat ==", gtr_beat)
print("== drum_mel ==", drum_mel)
print("== drum_beat ==", drum_beat)
print("피아노 길이:", len(piano_mel), len(piano_beat))
print("기타 길이:", len(gtr_mel), len(gtr_beat))
print("드럼 길이:", len(drum_mel), len(drum_beat))

# 6. parts_data 구성 (각 파트별 배열 반드시 길이 일치해야 함)
parts_data = {
    "Synth": {   # 피아노 대신 신디로 명명
        "instrument": insts['synth'],
        "melodies": piano_mel,
        "beat_ends": piano_beat,
        "dynamics": piano_dyn,
        "lyrics": piano_lyr
    },
    "RhythmGuitar": {
        "instrument": insts['elec_guitar'],
        "melodies": gtr_mel,
        "beat_ends": gtr_beat,
        "dynamics": gtr_dyn,
        "lyrics": gtr_lyr
    },
    "Drums": {
        "instrument": insts['drum'],
        "melodies": drum_mel,
        "beat_ends": drum_beat,
        "dynamics": drum_dyn,
        "lyrics": drum_lyr
    }
}

score_data = {
    'key': 'C',
    'time_signature': '4/4',
    'tempo': 120,
    'clef': 'treble'
}

output_musicxml_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.xml"
output_midi_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.mid"

process_and_output_score(
    parts_data,
    score_data,
    musicxml_path=output_musicxml_path,
    midi_path=output_midi_path,
    show_html=False
)

print("✅ 합주 MIDI/MusicXML 생성 완료!")