from music21 import instrument

# 코드별 아르페지오(피아노)와 코드톤(기타)
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

predicted_chords = ["C", "G", "Am", "F", "C", "G", "F", "C"]

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
    }
}

current_beat = 0.0
for chord in predicted_chords:
    # 피아노: 아르페지오 (4분음표 4개)
    piano_notes = chord_patterns_piano.get(chord, ["C4", "E4", "G4", "E4"])
    for note_name in piano_notes:
        duration = 1.0
        parts_data["Piano"]["melodies"].append(note_name)
        current_beat += duration
        parts_data["Piano"]["beat_ends"].append(current_beat)
        parts_data["Piano"]["dynamics"].append("mf")
        parts_data["Piano"]["lyrics"].append("")
    # 기타: 화음(코드) (한 마디 길이만큼)
    guitar_chord = chord_patterns_guitar.get(chord, ["C3", "E3", "G3"])
    # 한 마디의 마지막 beat_end에 맞춰서
    parts_data["Guitar"]["melodies"].append(guitar_chord)  # 리스트로!
    parts_data["Guitar"]["beat_ends"].append(current_beat)
    parts_data["Guitar"]["dynamics"].append("mf")
    parts_data["Guitar"]["lyrics"].append("")

# 기본 정보
score_data = {
    'key': 'C',
    'time_signature': '4/4',
    'tempo': 120,
    'clef': 'treble'
}

# 파일 경로
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