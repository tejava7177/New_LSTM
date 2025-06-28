import os
from ai_song_maker.score_helper import process_and_output_score

# 📌 코드 구성음 매핑 (기초적 triad 구성, 필요 시 확장 가능)
chord_notes = {
    "C": ["C4", "E4", "G4"],
    "G": ["G3", "B3", "D4"],
    "Am": ["A3", "C4", "E4"],
    "F": ["F3", "A3", "C4"],
    "D": ["D4", "F#4", "A4"],
    "Em": ["E3", "G3", "B3"],
    "Dm": ["D4", "F4", "A4"],
    "E": ["E3", "G#3", "B3"],
    "A": ["A3", "C#4", "E4"],
    "Bm": ["B3", "D4", "F#4"],
    "B": ["B3", "D#4", "F#4"]
    # 필요에 따라 추가
}

# 🎹 코드 진행 → parts_data 변환 함수
def generate_parts_data_from_chords(chords):
    melodies = []
    beat_ends = []
    beat = 0.0

    for chord in chords:
        notes = chord_notes.get(chord, [])
        for note in notes:
            melodies.append(note)
            beat_ends.append(beat + 1.0)  # 한 박자 유지
        beat += 1.0  # 마디 넘기기

    return {
        "Piano": {
            "instrument": "Piano",
            "melodies": melodies,
            "beat_ends": beat_ends,
            "dynamics": ['mf'] * len(melodies),
            "lyrics": [''] * len(melodies),
        }
    }

# 🔄 MIDI 출력 경로 설정
def get_output_paths(filename="rock_sample"):
    base_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi"
    os.makedirs(base_path, exist_ok=True)
    return {
        "musicxml": os.path.join(base_path, f"{filename}.xml"),
        "midi": os.path.join(base_path, f"{filename}.mid"),
        "html": os.path.join(base_path, f"{filename}.html")
    }

# 🎯 메인 실행부
if __name__ == "__main__":
    # 예시 코드 진행 (예측된 결과로 대체 가능)
    predicted_chords = ["C", "G", "Am", "F", "C", "G", "F", "C"]

    # 변환 및 출력
    parts_data = generate_parts_data_from_chords(predicted_chords)
    score_data = {
        "tempo": 120,
        "beats_per_measure": 4
    }
    paths = get_output_paths("rock_sample")

    # 🛠️ SongMaker 기반 MIDI 생성
    process_and_output_score(
        parts_data,
        score_data,
        musicxml_path=paths["musicxml"],
        midi_path=paths["midi"],
        show_html=False,
        sheet_music_html_path=paths["html"]
    )

    print(f"✅ MIDI 생성 완료! 경로: {paths['midi']}")