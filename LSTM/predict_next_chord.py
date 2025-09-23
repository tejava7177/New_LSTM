# LSTM/model/predict_next_chord.py
import os
import json
import re
import numpy as np
import torch
from typing import List, Dict, Tuple

from model.train_lstm import ChordLSTM
from harmony_score import evaluate_progression  # 0~1
from model.decoding.beam import generate_progressions_guided
from model.rules.base import GenreRule
from model.rules.jazz import JazzRule

# ───────────────────────────────────────────────────────────────────────────────
# 1) 모델 경로 설정
# ───────────────────────────────────────────────────────────────────────────────
BASE_DIRS: Dict[str, str] = {
    "jazz": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/jazz/New2",
    "rock": "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/rock",
    "pop":  "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/pop",
}

# 장르 규칙 레지스트리(재즈만 강화된 규칙 사용, pop/rock은 기본 규칙)
RULES: Dict[str, GenreRule] = {
    "jazz": JazzRule(alpha=0.8),   # 모델(0.6) + 규칙(0.4) 결합을 가정
    "pop":  GenreRule(),
    "rock": GenreRule(),
}

# ───────────────────────────────────────────────────────────────────────────────
# 2) 어휘(OOV) 보정: 재즈 확대 vocab이 아닌 72-토큰(maj/min/7/dim/aug/sus4)에서도 동작하도록
# ───────────────────────────────────────────────────────────────────────────────
ENH_FLAT = {"A#": "Bb", "D#": "Eb", "G#": "Ab"}  # 재즈 표기 선호(플랫화)
ALIASES = [
    ("maj7", ["maj7", "M7", "Δ7", "^7"]),
    ("min7", ["min7", "m7", "-7"]),
    ("min",  ["min", "m", "-"]),
    ("dim7", ["dim7", "o7", "°7"]),
    ("dim",  ["dim", "o", "°"]),
    ("sus4", ["sus4"]),
    ("7",    ["7"]),
]

_root_re = re.compile(r"^([A-G](?:#|b)?)(.*)$")

def canonicalize_to_vocab(ch: str, vocab_set: set) -> Tuple[str, bool]:
    """
    단일 코드 문자열을 모델 vocab에 맞게 보정.
    반환: (보정된코드 혹은 원본, 보정되었는지 여부)
    """
    m = _root_re.match(ch.strip())
    if not m:
        return ch, False

    root, qual = m.group(1), (m.group(2) or "")
    root = ENH_FLAT.get(root, root)   # #계열 중 재즈 관용적으로 b 사용
    cand = root + qual
    if cand in vocab_set:
        return cand, (cand != ch)

    ql = qual.lower()

    # 1) 별칭 정규화 시도
    for canon, forms in ALIASES:
        for f in forms:
            if f in ql:
                c2 = root + ql.replace(f, canon)
                if c2 in vocab_set:
                    return c2, True

    # 2) 7th를 triad로 격하(72 토큰 모델에서 maj7/min7/m7b5 미지원인 경우)
    if "maj7" in ql and (root + "maj") in vocab_set:
        return root + "maj", True
    if any(x in ql for x in ["min7", "m7", "-7"]) and (root + "min") in vocab_set:
        return root + "min", True
    if any(x in ql for x in ["ø", "m7b5"]) and (root + "dim") in vocab_set:
        return root + "dim", True
    if "dim7" in ql and (root + "dim") in vocab_set:
        return root + "dim", True

    # 3) 마지막 보정: triad/7/sus4 중 존재하는 것으로 매핑
    for fb in ["7", "maj", "min", "dim", "aug", "sus4"]:
        c3 = root + fb
        if c3 in vocab_set:
            return c3, True

    # 그래도 안 되면 원본 반환(추후 경고)
    return ch, False


def normalize_seed(seed3: List[str], vocab_keys: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    시드 3코드를 vocab에 맞게 보정. (Cmaj7->Cmaj 등)
    반환: (보정된 시드, [(원본,보정후), ...] 보정 변경 목록)
    """
    vocab_set = set(vocab_keys)
    fixed, changes = [], []
    for ch in seed3:
        out, changed = canonicalize_to_vocab(ch, vocab_set)
        fixed.append(out)
        if changed and out != ch:
            changes.append((ch, out))
    return fixed, changes

# ───────────────────────────────────────────────────────────────────────────────
# 3) 모델/어휘 로딩 + 체크포인트 키 호환(emb ↔ embedding)
# ───────────────────────────────────────────────────────────────────────────────
def load_model_and_vocab(genre: str):
    base_dir = BASE_DIRS[genre]
    chord_to_index: Dict[str, int] = np.load(
        os.path.join(base_dir, "chord_to_index.npy"), allow_pickle=True
    ).item()
    index_to_chord: Dict[int, str] = np.load(
        os.path.join(base_dir, "index_to_chord.npy"), allow_pickle=True
    ).item()

    model = ChordLSTM(len(chord_to_index))
    state = torch.load(os.path.join(base_dir, "chord_lstm.pt"), map_location=torch.device("cpu"))

    # 체크포인트 키 호환
    if hasattr(model, "embedding"):
        if "emb.weight" in state and "embedding.weight" not in state:
            state["embedding.weight"] = state.pop("emb.weight")
    elif hasattr(model, "emb"):
        if "embedding.weight" in state and "emb.weight" not in state:
            state["emb.weight"] = state.pop("embedding.weight")

    model.load_state_dict(state, strict=False)
    model.eval()
    return model, chord_to_index, index_to_chord

# ───────────────────────────────────────────────────────────────────────────────
# 4) CLI 메인
# ───────────────────────────────────────────────────────────────────────────────
def main():
    genres = list(BASE_DIRS.keys())
    while True:
        genre = input(f"예측할 코드 진행 장르를 입력하세요 {genres}: ").strip().lower()
        if genre in genres:
            break
        print(f"지원하는 장르만 입력하세요! ({'/'.join(genres)})")

    model, chord_to_index, index_to_chord = load_model_and_vocab(genre)
    rule = RULES.get(genre, GenreRule())

    # 시드 입력
    while True:
        raw = input("3개의 코드를 띄어쓰기로 입력 (예: C G Am): ").strip().split()
        if len(raw) == 3:
            break
        print("반드시 3개의 코드를 입력해주세요!")

    # 시드 보정(어휘 미스매치 방지)
    seed_norm, changed = normalize_seed(raw, list(chord_to_index.keys()))
    if changed:
        print("ℹ️  입력 코드를 모델 어휘에 맞춰 보정했습니다:")
        for before, after in changed:
            print(f"   - {before}  →  {after}")
    # 여전히 어휘 밖이 있는지 체크
    oov = [c for c in seed_norm if c not in chord_to_index]
    if oov:
        print(f"⚠️  어휘 밖 코드가 있어 진행할 수 없습니다: {oov}")
        print("   예: Dm7→Dmin, Cmaj7→Cmaj 처럼 입력/보정을 시도해 주세요.")
        return

    # 가이드 빔서치(재즈는 규칙 승격/enforce_upgrade=True)
    seqs: List[List[str]] = generate_progressions_guided(
        model,
        chord_to_index,
        index_to_chord,
        seed_chords=seed_norm,
        steps=5,
        beams=4,
        per_step_top=8,
        rule=rule,
        enforce_upgrade=(genre == "jazz"),
    )

    # 점수/라벨: 모델 점수(0~1) + 규칙 점수(0~1) 결합
    seed_bad = rule.seed_is_bad(seed_norm)
    scored = []
    for seq in seqs:
        s_model = float(evaluate_progression(model, seq, chord_to_index, index_to_chord))  # 0~1
        s_rule = float(rule.partial_score(seq))  # 0~1
        s_final = 0.6 * s_model + 0.4 * s_rule
        if seed_bad and genre == "jazz":
            s_final = min(s_final, 0.20)  # 재즈에 부적합한 시드면 상한
        label = rule.label(seq, seed_bad)
        scored.append((seq, s_model, s_rule, s_final, label))

    scored.sort(key=lambda x: x[3], reverse=True)

    print(f"\n🎸 [{genre.upper()}] Top-{len(scored)} 예측 코드 진행:")
    for i, (seq, s_model, s_rule, s_final, label) in enumerate(scored, start=1):
        print(f"{i}번 진행({label}, 확률 {int(round(s_final * 100))}%): " + " → ".join(seq))

    # 선택/저장
    while True:
        choice = input(f"사용할 진행 번호를 입력하세요 (1~{len(scored)}, q=취소): ").strip()
        if choice.lower() == "q":
            import sys as _sys
            _sys.exit("취소되었습니다.")
        if choice.isdigit() and 1 <= int(choice) <= len(scored):
            break

    chosen = scored[int(choice) - 1][0]
    base_data_dir = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data"
    out_dir = os.path.join(base_data_dir, f"{genre}_midi", "chord_JSON")
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, "tmp_selected_progression.json")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"genre": genre, "progression": chosen}, f, ensure_ascii=False, indent=2)
    print(f"✅ 선택된 진행이 저장되었습니다.\n→ {tmp_path}")
    print("다음 단계에서 useSongMaker_*.py 를 실행하세요.")


if __name__ == "__main__":
    main()