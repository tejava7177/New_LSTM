# LSTM/predict_next_chord.py
import os, sys, json, re
import numpy as np
import torch
from typing import List, Tuple, Optional

# --- 패키지 임포트가 단독 실행에서도 되도록 경로 보정 ---
THIS_FILE = os.path.abspath(__file__)
LSTM_DIR  = os.path.dirname(THIS_FILE)            # .../LSTM
PROJ_ROOT = os.path.dirname(LSTM_DIR)             # .../ (LSTM 상위)
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)                 # 'import LSTM.*' 가능

# 내부 모듈
from LSTM.model.train_lstm import ChordLSTM
from LSTM.harmony_score import evaluate_progression  # 0~1 평균 확률
from LSTM.chord_engine.smart_progression import generate_topk  # 룰 후보 + (옵션)모델 스코어 블렌딩

# --- 장르별 모델 디렉토리 ---
BASE_DIRS = {
    "jazz": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/jazz/New2",
    "rock": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/rock",
    "pop" : "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/pop",
}

# --- 저장 경로 ---
BASE_DATA_DIR = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data"

# -------- 유틸 --------
ROOT_RE = re.compile(r"^([A-G](?:#|b)?)")

def to_roots(tokens: List[str]) -> List[str]:
    """사용자 입력(품질 포함 가능) -> 루트만 추출 (최대 3개)"""
    roots = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        m = ROOT_RE.match(t)
        roots.append(m.group(1) if m else t)
    # 3개 미만이면 가능한 만큼만, 3개 초과면 앞에서 3개만
    return roots[:3]

def parse_seed_line(line: str) -> List[str]:
    # "C G Am" 또는 "C,G,Am" 모두 허용
    if "," in line:
        toks = [x.strip() for x in line.split(",")]
    else:
        toks = line.strip().split()
    return toks

# -------- 모델 로딩 --------
def load_model_and_vocab(genre: str):
    """모델과 vocab 로드. 실패 시 (None, None, None) 반환."""
    try:
        base = BASE_DIRS[genre]
        chord_to_index = np.load(os.path.join(base, "chord_to_index.npy"), allow_pickle=True).item()
        index_to_chord = np.load(os.path.join(base, "index_to_chord.npy"), allow_pickle=True).item()

        model = ChordLSTM(len(chord_to_index))
        state = torch.load(os.path.join(base, "chord_lstm.pt"), map_location=torch.device("cpu"))
        # 체크포인트 키 호환 (embedding/emb)
        if hasattr(model, "embedding"):
            if "emb.weight" in state and "embedding.weight" not in state:
                state["embedding.weight"] = state.pop("emb.weight")
        elif hasattr(model, "emb"):
            if "embedding.weight" in state and "emb.weight" not in state:
                state["emb.weight"] = state.pop("embedding.weight")
        model.load_state_dict(state, strict=False)
        model.eval()
        print(f"🧠 Using LSTM model: {os.path.join(base,'chord_lstm.pt')}")
        return model, chord_to_index, index_to_chord
    except Exception as e:
        print(f"⚠️  모델 로딩 실패(룰 기반만 사용): {e}")
        return None, None, None

# -------- 메인 --------
def main():
    genres = list(BASE_DIRS.keys())
    # 0) 장르 입력
    while True:
        genre = input(f"예측할 코드 진행 장르를 입력하세요 {genres}: ").strip().lower()
        if genre in genres:
            break
        print(f"지원하는 장르만 입력하세요! ({'/'.join(genres)})")

    # 1) 시드 입력 (루트만/혹은 품질 포함해도 OK → 루트로 환원)
    while True:
        raw = input("3개의 코드를 띄어쓰기 또는 콤마로 입력 (예: C G Am / D,G,C): ").strip()
        toks = parse_seed_line(raw)
        if len(toks) >= 3:
            break
        print("반드시 3개의 코드를 입력해주세요!")

    seed_roots = to_roots(toks)
    if len(seed_roots) < 3:
        print("⚠️  유효한 루트를 3개 추출하지 못했습니다. 입력값을 확인해주세요.")
        sys.exit(1)

    # 2) 모델 로딩(있으면 블렌딩, 없으면 룰만)
    model, chord_to_index, index_to_chord = load_model_and_vocab(genre)
    use_model = model is not None

    # 3) 후보 생성
    # 3-1) 첫 번째 결과: 룰만 (가장 '정석/장르스러움'이 높은 것)
    rule_only = generate_topk(
        genre=genre,
        seed_roots=seed_roots,
        k=1,
        scorer=None,   # 모델 스코어 사용 안 함
        alpha=1.0
    )  # -> [(seq, score)]
    top1_seq, top1_score = rule_only[0]

    # 3-2) 두/세 번째 결과: 모델+룰 블렌딩 (가능하면)
    blended: List[Tuple[List[str], float]] = []
    if use_model:
        def scorer_fn(seq: List[str]) -> float:
            # evaluate_progression: 모델이 예측한 다음 코드 확률들의 평균 (0~1)
            return float(evaluate_progression(model, seq, chord_to_index, index_to_chord))
        blended_all = generate_topk(
            genre=genre,
            seed_roots=seed_roots,
            k=5,                 # 넉넉히 뽑아 중복 제거 후 상위 2개만 사용
            scorer=scorer_fn,
            alpha=0.6           # 룰 60% + 모델 40% (가중치는 필요시 조정)
        )
        # 1번(룰-only)과 동일 진행 제거 후 2개만 취함
        def same_prog(a: List[str], b: List[str]) -> bool:
            return len(a)==len(b) and all(x==y for x,y in zip(a,b))
        for seq, sc in blended_all:
            if not same_prog(seq, top1_seq):
                blended.append((seq, sc))
            if len(blended) >= 2:
                break
    else:
        # 모델이 없으면 룰 후보 중 2,3위로 채움
        rule_top3 = generate_topk(genre=genre, seed_roots=seed_roots, k=3, scorer=None, alpha=1.0)
        # 0번은 이미 top1로 사용했으니 1,2번만
        for seq, sc in rule_top3[1:3]:
            blended.append((seq, sc))

    # 4) 결과 출력(총 3개)
    print(f"\n🎸 [{genre.upper()}] Top-3 예측 코드 진행:")
    print(f"1번 진행(정석/룰 기반, 점수 {int(round(top1_score*100))}%): " + " → ".join(top1_seq))
    for i, (seq, sc) in enumerate(blended, start=2):
        tag = "모델+룰 블렌딩" if use_model else "룰 기반(보조)"
        print(f"{i}번 진행({tag}, 점수 {int(round(sc*100))}%): " + " → ".join(seq))

    # 5) 선택 받아서 저장
    valid_choices = ["1","2","3"]
    while True:
        choice = input("사용할 진행 번호를 입력하세요 (1/2/3, q=취소): ").strip()
        if choice.lower() == 'q':
            sys.exit("취소되었습니다.")
        if choice in valid_choices:
            break

    if choice == "1":
        chosen_prog = top1_seq
    elif choice == "2":
        chosen_prog = blended[0][0]
    else:
        chosen_prog = blended[1][0]

    out_dir = os.path.join(BASE_DATA_DIR, f"{genre}_midi", "chord_JSON")
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, "tmp_selected_progression.json")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"genre": genre, "progression": chosen_prog}, f, ensure_ascii=False, indent=2)

    print(f"✅ 선택된 진행이 저장되었습니다.\n→ {tmp_path}")
    print("다음 단계에서 useSongMaker_*.py 를 실행하세요.")

if __name__ == "__main__":
    main()