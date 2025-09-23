# LSTM/predict_next_chord.py
import os, sys, json, re, math
import numpy as np
import torch

from model.train_lstm import ChordLSTM
from harmony_score import evaluate_progression, interpret_score

# ====== 모델 디렉토리 ======
BASE_DIRS = {
    "jazz": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/jazz/New2",
    "rock": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/rock",
    "pop" : "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/pop"
}

# ====== 재즈 규칙 유틸 ======
_PITCH_PC = {
    "C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,
    "G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11
}
_BAD_SHARP_MAJ = {"G#","D#","A#"}  # 재즈 표기에서 선호되지 않음(Ab/Eb/Bb 권장)

def _parse_chord(ch: str):
    m = re.match(r'^([A-G](?:#|b)?)(.*)$', ch.strip())
    if not m: return None, ""
    root, qual = m.group(1), (m.group(2) or "").strip()
    return root, qual

def _is_seventh_quality(qual: str):
    q = qual.lower()
    return ("7" in q) or ("ø" in q) or ("dim7" in q) or ("m7b5" in q)

def _is_power_or_plain(qual: str):
    q = (qual or "").lower()
    if "5" in q:   # 파워코드
        return True
    # maj/min/sus만 있고 7/9/11/13/ø/°/dim/aug 같은 확장이 없으면 'plain'
    if any(k in q for k in ["7","9","11","13","ø","°","dim","aug"]):
        return False
    q2 = q.replace("maj","").replace("min","m").replace("sus","")
    return True  # 확장 없으면 plain 취급

def _pc(root: str):
    return _PITCH_PC.get(root, None)

def _down_fifth(a_root, b_root):
    pa, pb = _pc(a_root), _pc(b_root)
    if pa is None or pb is None: return False
    return (pa - pb) % 12 == 7  # 완전5도 하행

def _has_iivi(prog):
    count = 0
    for i in range(len(prog)-2):
        a, b, c = prog[i], prog[i+1], prog[i+2]
        ra, qa = _parse_chord(a)
        rb, qb = _parse_chord(b)
        rc, qc = _parse_chord(c)
        if not (ra and rb and rc): continue
        if ("m7" in qa.lower()) and ("7" in qb.lower()) and ("maj7" in qc.lower()):
            if _down_fifth(ra, rb) and _down_fifth(rb, rc):
                count += 1
    return count

def _jazz_rule_score(prog):
    """0~1: 7th 비율↑, ii–V–I↑, 파워/삼화음↓, 비선호 표기↓"""
    if not prog: return 0.0
    n = len(prog)
    bad_sharp = 0; seventh = 0; plain = 0
    for ch in prog:
        r, q = _parse_chord(ch)
        if not r: continue
        if r in _BAD_SHARP_MAJ and (("maj" in (q or "").lower()) or q == ""):
            bad_sharp += 1
        if _is_seventh_quality(q): seventh += 1
        if _is_power_or_plain(q):  plain   += 1

    ratio_7th   = seventh / n
    ratio_plain = plain / n
    ii_vi       = _has_iivi(prog)
    enh_pen     = bad_sharp / n

    score = 0.5*ratio_7th + 0.4*min(1.0, ii_vi/2.0) - 0.3*ratio_plain - 0.1*enh_pen
    return max(0.0, min(1.0, score))

def _seed_is_non_jazz(seed3):
    if not seed3: return True
    seventh = 0; power_like = False
    for ch in seed3:
        r, q = _parse_chord(ch)
        if _is_power_or_plain(q):
            power_like = power_like or ("5" in (q or "").lower())
        if _is_seventh_quality(q):
            seventh += 1
    ratio_7 = seventh / max(1, len(seed3))
    return power_like or (ratio_7 < 1/3)  # 3개 중 1개 미만이 7th면 비재즈로 간주

# ====== 로딩/추론 유틸 ======
def load_model_and_vocab(genre):
    base_dir = BASE_DIRS[genre]
    chord_to_index = np.load(os.path.join(base_dir,'chord_to_index.npy'), allow_pickle=True).item()
    index_to_chord = np.load(os.path.join(base_dir,'index_to_chord.npy'), allow_pickle=True).item()

    model = ChordLSTM(len(chord_to_index))
    state = torch.load(os.path.join(base_dir,'chord_lstm.pt'), map_location=torch.device('cpu'))
    # emb / embedding 키 호환
    if hasattr(model, "embedding"):
        if "emb.weight" in state and "embedding.weight" not in state:
            state["embedding.weight"] = state.pop("emb.weight")
    elif hasattr(model, "emb"):
        if "embedding.weight" in state and "emb.weight" not in state:
            state["emb.weight"] = state.pop("embedding.weight")

    model.load_state_dict(state, strict=False)
    model.eval()
    return model, chord_to_index, index_to_chord

def predict_top_k_next_chords(model, chord_to_index, index_to_chord, input_chords, k=3):
    indices = [chord_to_index.get(c, 0) for c in input_chords]
    x = torch.tensor([indices], dtype=torch.long)
    with torch.no_grad():
        out = model(x)
        probs = torch.softmax(out, dim=1)
        topk = torch.topk(probs, k)
        topk_indices = topk.indices[0].cpu().numpy()
    return [index_to_chord[idx] for idx in topk_indices]

def generate_multiple_progressions(model, chord_to_index, index_to_chord, seed_chords, n_generate=5, k=3):
    progressions = [[*seed_chords] for _ in range(k)]
    last_chords = [list(seed_chords) for _ in range(k)]
    for _ in range(n_generate):
        candidates_per_prog = []
        for i in range(k):
            next_k = predict_top_k_next_chords(model, chord_to_index, index_to_chord, last_chords[i], k)
            candidates_per_prog.append(next_k)
        for i in range(k):
            next_chord = candidates_per_prog[i][i]  # 0→top1, 1→top2, 2→top3
            progressions[i].append(next_chord)
            last_chords[i] = last_chords[i][1:] + [next_chord]
    return progressions

def _softmax_percent(scores, temperature=0.25):
    t = max(1e-6, float(temperature))
    xs = [s / t for s in scores]
    m = max(xs) if xs else 0.0
    exps = [math.exp(x - m) for x in xs]
    Z = sum(exps) or 1.0
    return [e / Z for e in exps]

# ====== 메인 ======
if __name__ == "__main__":
    genres = list(BASE_DIRS.keys())
    while True:
        genre = input(f"예측할 코드 진행 장르를 입력하세요 {genres}: ").strip().lower()
        if genre in genres: break
        print(f"지원하는 장르만 입력하세요! ({'/'.join(genres)})")

    model, chord_to_index, index_to_chord = load_model_and_vocab(genre)

    while True:
        user_input = input("3개의 코드를 띄어쓰기로 입력 (예: C G Am): ").strip().split()
        if len(user_input) == 3: break
        print("반드시 3개의 코드를 입력해주세요!")

    n_steps, k = 5, 3
    result = generate_multiple_progressions(model, chord_to_index, index_to_chord,
                                            user_input, n_generate=n_steps, k=k)

    # 점수 계산 (+ 재즈 규칙)
    seed_non_jazz = (genre == "jazz") and _seed_is_non_jazz(user_input)
    scored = []  # (prog, s_model, s_rule, s_final, label)
    for prog in result:
        s_model = float(evaluate_progression(model, prog, chord_to_index, index_to_chord, genre_hint=genre))  # 0~1
        if genre == "jazz":
            s_rule = _jazz_rule_score(prog)
            s_final = 0.5*s_model + 0.5*s_rule  # 재즈는 규칙 가중 50%
            if seed_non_jazz:
                s_final = min(s_final, 0.20)  # 비재즈 시드면 캡
            # 라벨은 s_final 기준으로
            if seed_non_jazz:
                label = "재즈와 거리가 먼 시드(점수 제한)"
            else:
                label = interpret_score(s_final)
        else:
            s_rule = 0.0
            s_final = s_model
            label = interpret_score(s_final)

        scored.append((prog, s_model, s_rule, s_final, label))

    # s_final로 정렬 + 상대 신뢰도(소프트맥스)
    scored.sort(key=lambda x: x[3], reverse=True)
    pcts = _softmax_percent([x[3] for x in scored], temperature=0.25)

    print(f"\n🎸 [{genre.upper()}] Top-3 예측 코드 진행 (총 {n_steps+3}개):")
    for rank, ((prog, s_model, s_rule, s_final, label), p) in enumerate(zip(scored, pcts), start=1):
        print(f"{rank}번 진행({label}, 확률 {int(round(p*100))}%): " + " → ".join(prog))

    # 선택 & 저장 (정렬된 순서 기준)
    while True:
        choice = input("사용할 진행 번호를 입력하세요 (1/2/3, q=취소): ").strip()
        if choice.lower() == 'q':
            sys.exit("취소되었습니다.")
        if choice in ('1','2','3'):
            break
    chosen_prog = scored[int(choice)-1][0]

    BASE_DATA_DIR = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data"
    genre_json_dir = os.path.join(BASE_DATA_DIR, f"{genre}_midi", "chord_JSON")
    os.makedirs(genre_json_dir, exist_ok=True)
    tmp_path = os.path.join(genre_json_dir, "tmp_selected_progression.json")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"genre": genre, "progression": chosen_prog}, f, ensure_ascii=False, indent=2)

    print(f"✅ 선택된 진행이 저장되었습니다.\n→ {tmp_path}")
    print("다음 단계에서 useSongMaker_*.py 를 실행하세요.")