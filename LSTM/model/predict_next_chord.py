import torch
import numpy as np
import os
from train_lstm import ChordLSTM

# 지원 장르별 모델 디렉토리
BASE_DIRS = {
    "jazz": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/jazz",
    "rock": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/rock",
    "pop" : "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/pop"
}

def load_model_and_vocab(genre):
    base_dir = BASE_DIRS[genre]
    chord_to_index = np.load(os.path.join(base_dir, 'chord_to_index.npy'), allow_pickle=True).item()
    index_to_chord = np.load(os.path.join(base_dir, 'index_to_chord.npy'), allow_pickle=True).item()
    # 모델도 여기에!
    model = ChordLSTM(len(chord_to_index))
    model.load_state_dict(torch.load(os.path.join(base_dir, 'chord_lstm.pt'), map_location=torch.device('cpu')))
    model.eval()
    return model, chord_to_index, index_to_chord

def predict_top_k_next_chords(model, chord_to_index, index_to_chord, input_chords, k=3):
    indices = [chord_to_index.get(c, 0) for c in input_chords]
    input_tensor = torch.tensor([indices], dtype=torch.long)
    with torch.no_grad():
        output = model(input_tensor)
        probs = torch.softmax(output, dim=1)
        topk = torch.topk(probs, k)
        topk_indices = topk.indices[0].cpu().numpy()
        return [index_to_chord[idx] for idx in topk_indices]

def generate_multiple_progressions(model, chord_to_index, index_to_chord, seed_chords, n_generate=5, k=3):
    progressions = [[*seed_chords] for _ in range(k)]
    last_chords = [list(seed_chords) for _ in range(k)]

    for step in range(n_generate):
        candidates_per_prog = []
        for i in range(k):
            next_k_chords = predict_top_k_next_chords(model, chord_to_index, index_to_chord, last_chords[i], k)
            candidates_per_prog.append(next_k_chords)
        for i in range(k):
            next_chord = candidates_per_prog[i][i]  # 0번째 진행은 top1, 1번째는 top2, 2번째는 top3
            progressions[i].append(next_chord)
            last_chords[i] = last_chords[i][1:] + [next_chord]
    return progressions

if __name__ == "__main__":
    genres = list(BASE_DIRS.keys())
    genre = None
    while genre not in genres:
        genre = input(f"예측할 코드 진행 장르를 입력하세요 {genres} 중 하나: ").strip().lower()
        if genre not in genres:
            print(f"지원하는 장르만 입력하세요! (예: {'/'.join(genres)})")

    model, chord_to_index, index_to_chord = load_model_and_vocab(genre)

    while True:
        user_input = input("3개의 코드를 띄어쓰기로 입력 (예: C G Am): ").strip().split()
        if len(user_input) != 3:
            print("반드시 3개의 코드를 입력해주세요!")
            continue
        n_steps = 5
        result = generate_multiple_progressions(
            model, chord_to_index, index_to_chord,
            user_input, n_generate=n_steps, k=3
        )
        print(f"\n🎸 [{genre.upper()}] Top-3 예측 코드 진행 (총 {n_steps+3}개):")
        for i, prog in enumerate(result):
            print(f"{i+1}번 진행: {' → '.join(prog)}")
        break