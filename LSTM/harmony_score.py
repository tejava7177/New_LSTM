# harmony_score.py
import math
import torch

def evaluate_progression(model, progression, chord_to_index, index_to_chord, genre_hint=None, window_size=3):
    """
    진행 전체에 대한 '로그 확률 평균'(기하평균)을 0~1 사이 값으로 반환.
    - window_size 길이의 슬라이딩 윈도우로 다음 코드의 확률을 추정
    - 길이가 달라도 값이 과도하게 떨어지지 않도록 log-mean 사용
    """
    if not progression or len(progression) <= window_size:
        return 0.0

    logs = []
    last = progression[:window_size]
    for i in range(window_size, len(progression)):
        idxs = [chord_to_index.get(c, 0) for c in last]
        x = torch.tensor([idxs], dtype=torch.long)
        with torch.no_grad():
            out = model(x)  # (1, vocab)
            prob = torch.softmax(out, dim=1)[0, chord_to_index.get(progression[i], 0)].item()
        prob = max(prob, 1e-9)  # underflow 방지
        logs.append(math.log(prob))
        last = last[1:] + [progression[i]]

    if not logs:
        return 0.0

    # 기하평균 = exp(평균 로그확률)
    gmean = math.exp(sum(logs) / len(logs))
    # 0~1 스케일 유지
    return gmean


def interpret_score(score):
    """
    표시용 등급 라벨. (로그평균 기반 점수에 맞춘 권장 기준)
    프로젝트 성격에 맞게 임계값은 조정 가능.
    """
    if score >= 0.68:
        return "정석 진행"
    elif score >= 0.55:
        return "대중적인 진행"
    elif score >= 0.42:
        return "비교적 많이 쓰임"
    else:
        return "특이/실험적 진행"