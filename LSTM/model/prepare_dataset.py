import json
import numpy as np
import os

def load_and_prepare_dataset(json_path, window_size=3):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 진행 리스트 key 찾기
    key = [k for k in data.keys() if k.endswith('_chord_progressions')][0]
    progressions = data[key]

    # 전체 코드 사전 만들기
    all_chords = []
    for prog in progressions:
        all_chords.extend(prog.strip().split())
    chords_vocab = sorted(set(all_chords))
    chord_to_index = {c: i for i, c in enumerate(chords_vocab)}
    index_to_chord = {i: c for c, i in chord_to_index.items()}

    # X, y 생성
    X, y = [], []
    for prog in progressions:
        tokens = prog.strip().split()
        for i in range(len(tokens) - window_size):
            X.append([chord_to_index[c] for c in tokens[i:i+window_size]])
            y.append(chord_to_index[tokens[i+window_size]])
    X = np.array(X)
    y = np.array(y)
    return X, y, chord_to_index, index_to_chord

def save_dataset_for_genre(json_path, save_dir, window_size=3):
    os.makedirs(save_dir, exist_ok=True)
    # npy 파일 삭제 (있으면)
    for fn in ["X.npy", "y.npy", "chord_to_index.npy", "index_to_chord.npy"]:
        file_path = os.path.join(save_dir, fn)
        if os.path.exists(file_path):
            os.remove(file_path)

    X, y, chord_to_index, index_to_chord = load_and_prepare_dataset(json_path, window_size=window_size)
    np.save(os.path.join(save_dir, "X.npy"), X)
    np.save(os.path.join(save_dir, "y.npy"), y)
    np.save(os.path.join(save_dir, "chord_to_index.npy"), chord_to_index, allow_pickle=True)
    np.save(os.path.join(save_dir, "index_to_chord.npy"), index_to_chord, allow_pickle=True)
    print(f"[{os.path.basename(save_dir)}] ✅ 저장 완료 | X: {X.shape}, y: {y.shape}, vocab: {len(chord_to_index)}")

if __name__ == "__main__":
    # 각 장르에 대해 경로 설정
    genre_config = {
        "rock": {
            "json": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_midi/rock_chords_rich_normalized.json",
            "save": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/rock"
        },
        "jazz": {
            "json": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi/jazz_chords_cleaned.json",
            "save": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/jazz"
        },
        "pop": {
            "json": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/pop_chords_normalized.json",
            "save": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/pop"
        }
    }
    for genre, paths in genre_config.items():
        print(f"\n--- {genre.upper()} ---")
        save_dataset_for_genre(paths["json"], paths["save"], window_size=3)