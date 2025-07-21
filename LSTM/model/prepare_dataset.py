import json
import numpy as np
import os

def load_and_prepare_dataset(json_path, window_size=3):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    progressions = data["rock_chord_progressions"]

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

if __name__ == "__main__":
    # 경로 설정
    json_path = "/LSTM/cli/data/rock_midi/rock_chords_rich_normalized.json"
    save_dir = "./LSTM/model"
    os.makedirs(save_dir, exist_ok=True)

    # 데이터셋 생성
    X, y, chord_to_index, index_to_chord = load_and_prepare_dataset(json_path, window_size=3)

    # 저장
    np.save(os.path.join(save_dir, "X.npy"), X)
    np.save(os.path.join(save_dir, "y.npy"), y)
    np.save(os.path.join(save_dir, "chord_to_index.npy"), chord_to_index)
    np.save(os.path.join(save_dir, "index_to_chord.npy"), index_to_chord)

    print(f"✅ 데이터셋 저장 완료!\nX shape: {X.shape}, y shape: {y.shape}")
    print(f"코드 vocabulary 크기: {len(chord_to_index)}")