from ai_song_maker.score_helper import process_and_output_score

# 코드 진행
predicted_chords = ["C", "G", "Am", "F", "C", "G", "F", "C"]

# 코드별 4분음표 아르페지오 패턴
chord_patterns = {
    "C": ["C4", "E4", "G4", "E4"],
    "G": ["G3", "B3", "D4", "B3"],
    "Am": ["A3", "C4", "E4", "C4"],
    "F": ["F3", "A3", "C4", "A3"]
}

parts_data = {
    "Piano": {
        "instrument": "Piano",
        "melodies": [],
        "beat_ends": [],
        "dynamics": [],
        "lyrics": []
    }
}

current_beat = 0.0
for chord in predicted_chords:
    notes = chord_patterns.get(chord, ["C4", "E4", "G4", "E4"])
    for note_name in notes:
        duration = 1.0  # 4분음표
        parts_data["Piano"]["melodies"].append(note_name)   # **여기서는 문자열만**
        current_beat += duration
        parts_data["Piano"]["beat_ends"].append(current_beat)
        parts_data["Piano"]["dynamics"].append("mf")
        parts_data["Piano"]["lyrics"].append("")

score_data = {
    'key': 'C',
    'time_signature': '4/4',
    'tempo': 120,
    'clef': 'treble'
}

output_musicxml_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.xml"
output_midi_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_sample.mid"

# MIDI/XML 생성
process_and_output_score(
    parts_data,
    score_data,
    musicxml_path=output_musicxml_path,
    midi_path=output_midi_path,
    show_html=False
)