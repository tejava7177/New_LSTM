from music21 import instrument

predicted_chords = ["C", "G", "Am", "F", "C", "G", "F", "C"]
num_bars = len(predicted_chords)

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
        "instrument": instrument.SnareDrum(),  # 또는 "Percussion" (문자열, 내부에서 클래스로 변환됨)
        "melodies": [],
        "beat_ends": [],
        "dynamics": [],
        "lyrics": []
    }
}

# 1. 피아노/기타: 이전 코드처럼 작성 (아르페지오/화음)
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
for chord in predicted_chords:
    # 피아노(아르페지오)
    piano_notes = chord_patterns_piano.get(chord, ["C4", "E4", "G4", "E4"])
    for note_name in piano_notes:
        duration = 1.0
        parts_data["Piano"]["melodies"].append(note_name)
        current_beat += duration
        parts_data["Piano"]["beat_ends"].append(current_beat)
        parts_data["Piano"]["dynamics"].append("mf")
        parts_data["Piano"]["lyrics"].append("")
    # 기타(화음)
    guitar_chord = chord_patterns_guitar.get(chord, ["C3", "E3", "G3"])
    parts_data["Guitar"]["melodies"].append(guitar_chord)
    parts_data["Guitar"]["beat_ends"].append(current_beat)
    parts_data["Guitar"]["dynamics"].append("mf")
    parts_data["Guitar"]["lyrics"].append("")

# 2. 드럼 트랙: 8마디 반복 패턴 (4/4, 4분음표 4개씩)
drum_pattern = [
    ("C2", 1.0),   # 1박 Kick
    ("F#2", 1.0),  # 2박 HiHat
    ("D2", 1.0),   # 3박 Snare
    ("F#2", 1.0)   # 4박 HiHat
]
drum_total_beat = 0.0
for _ in range(num_bars):
    for pitch, dur in drum_pattern:
        parts_data["Drums"]["melodies"].append(pitch)
        drum_total_beat += dur
        parts_data["Drums"]["beat_ends"].append(drum_total_beat)
        parts_data["Drums"]["dynamics"].append("mf")
        parts_data["Drums"]["lyrics"].append("")

score_data = {
    'key': 'C',
    'time_signature': '4/4',
    'tempo': 120,
    'clef': 'treble'
}

output_musicxml_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.xml"
output_midi_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.mid"

from ai_song_maker.score_helper import process_and_output_score

process_and_output_score(
    parts_data,
    score_data,
    musicxml_path=output_musicxml_path,
    midi_path=output_midi_path,
    show_html=False
)