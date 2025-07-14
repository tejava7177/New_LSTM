from music21 import instrument
import sys

# SongMaker 및 drumPattern 경로 추가
sys.path.append('/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker')

from ai_song_maker.score_helper import process_and_output_score
from DrumPattern.randomDrumPattern import generate_random_drum_pattern
from GuitarPattern.randomGuitarPattern import generate_random_guitar_pattern
from PianoPattern.randomPianoRhythm import generate_random_piano_rhythms

# ====== 코드 진행 ======
predicted_chords = ["C", "G", "Am", "F", "C", "G", "F", "C"]
num_bars = len(predicted_chords)

# 🎹 1. 피아노 리듬 랜덤 패턴
piano_rhythms = generate_random_piano_rhythms(num_bars)


parts_data = {
    "Piano": {
        "instrument": instrument.Piano(),
        "melodies": [],
        "beat_ends": [],
        "dynamics": [],
        "lyrics": []
    },
    "Guitar": {
        "instrument": instrument.AcousticGuitar(),
        "melodies": [],
        "beat_ends": [],
        "dynamics": [],
        "lyrics": []
    },
    "Drums": {
        "instrument": instrument.SnareDrum(),
        "melodies": [],
        "beat_ends": [],
        "dynamics": [],
        "lyrics": []
    }
}

# 피아노/기타 - 고정 패턴
chord_patterns_piano = {
    "C": ["C4", "E4", "G4", "E4"],
    "G": ["G3", "B3", "D4", "B3"],
    "Am": ["A3", "C4", "E4", "C4"],
    "F": ["F3", "A3", "C4", "A3"]
}
chord_patterns_guitar = {
    "C": ["C3", "E3", "G3"],
    "G": ["G3", "B3", "D4"],
    "Am": ["A3", "C4", "E4"],
    "F": ["F3", "A3", "C4"]
}

current_beat = 0.0
for bar_idx, chord in enumerate(predicted_chords):
    notes = chord_patterns_piano.get(chord, ["C4", "E4", "G4", "E4"])
    rhythm_for_this_bar = piano_rhythms[bar_idx]
    note_idx = 0
    for dur in rhythm_for_this_bar:
        note_name = notes[note_idx % len(notes)]
        parts_data["Piano"]["melodies"].append(note_name)
        current_beat += dur
        parts_data["Piano"]["beat_ends"].append(current_beat)
        parts_data["Piano"]["dynamics"].append("mf")
        parts_data["Piano"]["lyrics"].append("")
        note_idx += 1
    # 기타: 1마디(4박)마다 화음
    parts_data["Guitar"]["melodies"].append(chord_patterns_guitar.get(chord, ["C3", "E3", "G3"]))
    parts_data["Guitar"]["beat_ends"].append(current_beat)
    parts_data["Guitar"]["dynamics"].append("mf")
    parts_data["Guitar"]["lyrics"].append("")

# 🥁 드럼: 랜덤 패턴 생성 (여기서 적용!)
# 드럼 패턴 생성 (한 번만!)
drum_melodies, drum_beat_ends, drum_dynamics, drum_lyrics = generate_random_drum_pattern(measures=num_bars)

# parts_data에 그대로 할당
parts_data["Drums"]["melodies"] = drum_melodies
parts_data["Drums"]["beat_ends"] = drum_beat_ends
parts_data["Drums"]["dynamics"] = drum_dynamics
parts_data["Drums"]["lyrics"] = drum_lyrics

score_data = {
    'key': 'C',
    'time_signature': '4/4',
    'tempo': 120,
    'clef': 'treble'
}

rand_gtr_mel, rand_gtr_beats, rand_gtr_dyn, rand_gtr_lyr = generate_random_guitar_pattern(predicted_chords)

parts_data["RandomGuitar"] = {
    "instrument": "ElectricGuitar",  # 혹은 "ElectricGuitar" 등으로도 가능
    "melodies": rand_gtr_mel,
    "beat_ends": rand_gtr_beats,
    "dynamics": rand_gtr_dyn,
    "lyrics": rand_gtr_lyr
}

#파일 생성
output_musicxml_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.xml"
output_midi_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.mid"

process_and_output_score(
    parts_data,
    score_data,
    musicxml_path=output_musicxml_path,
    midi_path=output_midi_path,
    show_html=False
)

print("✅ 랜덤 드럼패턴 포함 합주 MIDI, MusicXML 생성 완료!")