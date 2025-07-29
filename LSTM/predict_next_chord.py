# LSTM/model/predict_next_chord.py
import os, sys, json, tempfile, numpy as np, torch
from model.train_lstm import ChordLSTM              # 경로에 맞게 수정
from harmony_score import evaluate_progression, interpret_score

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
    # ── 0) 장르 선택 ───────────────────────────────────────────
    genres = list(BASE_DIRS.keys())
    while True:
        genre = input(f"예측할 코드 진행 장르를 입력하세요 {genres}: ").strip().lower()
        if genre in genres: break
        print(f"지원하는 장르만 입력하세요! ({'/'.join(genres)})")

    model, chord_to_index, index_to_chord = load_model_and_vocab(genre)

    # ── 1) 시드 3코드 입력 ─────────────────────────────────────
    while True:
        user_input = input("3개의 코드를 띄어쓰기로 입력 (예: C G Am): ").strip().split()
        if len(user_input) == 3: break
        print("반드시 3개의 코드를 입력해주세요!")

    # ── 2) Top-3 예측 & 화면 출력 ───────────────────────────────
    n_steps, k = 5, 3
    result = generate_multiple_progressions(model, chord_to_index, index_to_chord,
                                            user_input, n_generate=n_steps, k=k)

    print(f"\n🎸 [{genre.upper()}] Top-3 예측 코드 진행 (총 {n_steps+3}개):")
    for i, prog in enumerate(result, start=1):
        s = evaluate_progression(model, prog, chord_to_index, index_to_chord)
        print(f"{i}번 진행({interpret_score(s)}, 확률 {int(s*100)}%): {' → '.join(prog)}")

    # ── 3) 번호 선택 ────────────────────────────────────────────
    while True:
        choice = input("사용할 진행 번호를 입력하세요 (1/2/3, q=취소): ").strip()
        if choice.lower() == 'q': sys.exit("취소되었습니다.")
        if choice in ('1','2','3'): break
    chosen_prog = result[int(choice)-1]

    # ── 4) 임시 JSON 저장 ──────────────────────────────────────

    BASE_DATA_DIR = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data"
    genre_json_dir = os.path.join(BASE_DATA_DIR, f"{genre}_midi", "chord_JSON")
    os.makedirs(genre_json_dir, exist_ok=True)

    tmp_path = os.path.join(genre_json_dir, "tmp_selected_progression.json")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"genre": genre, "progression": chosen_prog}, f, ensure_ascii=False, indent=2)

    print(f"✅ '{choice}번' 진행이 저장되었습니다.\n→ {tmp_path}")
    print("다음 단계에서 useSongMaker_*.py 를 실행하세요.")