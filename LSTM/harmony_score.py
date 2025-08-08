# harmony_score.py
import torch

def evaluate_progression(model, progression, chord_to_index, index_to_chord):
    """
    진행 리스트(시드 + 예측 코드) 전체에 대한 softmax 확률 평균을 반환.
    progression: 코드 리스트(예: ['D', 'A', 'G', 'D', ...])
    """
    window_size = 3  # 예시
    probs = []
    last_chords = progression[:window_size]
    for i in range(window_size, len(progression)):
        indices = [chord_to_index.get(c, 0) for c in last_chords]
        input_tensor = torch.tensor([indices], dtype=torch.long)
        with torch.no_grad():
            output = model(input_tensor)
            softmax_probs = torch.softmax(output, dim=1)
        next_idx = chord_to_index.get(progression[i], 0)
        prob = softmax_probs[0][next_idx].item()
        probs.append(prob)
        last_chords = last_chords[1:] + [progression[i]]
    if probs:
        avg_score = sum(probs) / len(probs)
    else:
        avg_score = 0
    return avg_score  #  0~1 사이 확률값


def interpret_score(score):
    if score >= 0.7:
        return "정석 진행"
    elif score >= 0.6:
        return "대중적인 진행"
    elif score >= 0.45:
        return "비교적 많이 쓰임"
    else:
        return "특이/실험적 진행"