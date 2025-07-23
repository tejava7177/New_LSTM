import torch
import numpy as np
import os
from train_lstm import ChordLSTM

BASE_DIR = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/pop"

chord_to_index = np.load(os.path.join(BASE_DIR, "chord_to_index.npy"), allow_pickle=True).item()
index_to_chord = np.load(os.path.join(BASE_DIR, "index_to_chord.npy"), allow_pickle=True).item()
vocab_size = len(chord_to_index)

model = ChordLSTM(vocab_size)
model.load_state_dict(torch.load(os.path.join(BASE_DIR, "chord_lstm.pt"), map_location=torch.device('cpu')))
model.eval()

def predict_top_k_next_chords(input_chords, k=3):
    indices = [chord_to_index.get(c, 0) for c in input_chords]
    input_tensor = torch.tensor([indices], dtype=torch.long)  # shape: (1, 3)
    with torch.no_grad():
        output = model(input_tensor)
        probs = torch.softmax(output, dim=1)
        topk = torch.topk(probs, k)
        topk_indices = topk.indices[0].cpu().numpy()
        return [index_to_chord[idx] for idx in topk_indices]

def generate_multiple_progressions(seed_chords, n_generate=5, k=3):
    progressions = [[*seed_chords] for _ in range(k)]
    last_chords = [list(seed_chords) for _ in range(k)]

    for step in range(n_generate):
        candidates_per_prog = []
        for i in range(k):
            next_k_chords = predict_top_k_next_chords(last_chords[i], k)
            candidates_per_prog.append(next_k_chords)
        # 각 진행의 다음 코드를 각각 1개씩 뽑아 진행 (순서대로)
        for i in range(k):
            next_chord = candidates_per_prog[i][i]  # 0번째 진행은 top1, 1번째는 top2, 2번째는 top3
            progressions[i].append(next_chord)
            last_chords[i] = last_chords[i][1:] + [next_chord]
    return progressions

if __name__ == "__main__":
    user_input = input("3개의 코드를 띄어쓰기로 입력 (예: C G Am): ").strip().split()
    if len(user_input) != 3:
        print("반드시 3개의 코드를 입력해주세요!")
    else:
        n_steps = 5
        result = generate_multiple_progressions(user_input, n_generate=n_steps, k=3)
        print(f"🎸 Top-3 예측 코드 진행 (총 {n_steps+3}개):")
        for i, prog in enumerate(result):
            print(f"{i+1}번 진행: {' → '.join(prog)}")