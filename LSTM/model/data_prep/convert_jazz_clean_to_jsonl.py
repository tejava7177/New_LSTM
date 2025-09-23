# LSTM/model/data_prep/convert_jazz_clean_to_jsonl.py
import argparse, json, os

CANDIDATE_KEYS = [
    "progressions", "chords", "jazz_chord_progressions"
]

def extract_progressions(data):
    # 1) dict 이고 알려진 키가 있으면 그걸 사용
    if isinstance(data, dict):
        for k in CANDIDATE_KEYS:
            if k in data and isinstance(data[k], list):
                return data[k]
        # 2) dict 안에서 "리스트 값을 가진 첫 번째 키"를 자동 선택
        for k, v in data.items():
            if isinstance(v, list):
                return v
        raise ValueError("입력 JSON(dict)에서 진행 리스트를 찾지 못함. 키 후보: " + ", ".join(CANDIDATE_KEYS))
    # 3) 이미 리스트라면 그대로
    if isinstance(data, list):
        return data
    raise ValueError("입력 JSON 포맷을 해석할 수 없음 (list 또는 dict 필요)")

def as_tokens(item):
    # 문자열이면 공백/콤마 분리, 리스트면 문자열화
    if isinstance(item, str):
        toks = [t for t in item.replace(",", " ").split() if t]
    elif isinstance(item, list):
        toks = [str(t) for t in item]
    else:
        toks = []
    return toks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="inp",  required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        raw = json.load(f)

    progs = extract_progressions(raw)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    n = 0
    with open(args.out, "w", encoding="utf-8") as w:
        for p in progs:
            toks = as_tokens(p)
            if toks:
                w.write(json.dumps({"chords": toks}, ensure_ascii=False) + "\n")
                n += 1
    print(f"Wrote {n} lines → {args.out}")

if __name__ == "__main__":
    main()