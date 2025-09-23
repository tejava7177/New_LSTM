import json, argparse, re, random
from pathlib import Path

ROOTS_SHARP = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
ROOTS_FLAT  = ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"]
PC = {
    "C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,
    "G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11
}

# 허용 품질(최소 세트)
KEEP_QUALS = {
    "maj","min","7","maj7","min7","m7b5","ø","dim","dim7","sus4","aug"
}

# 동의어 → 표준화 매핑
def norm_quality(q: str) -> str:
    q = q.strip().replace("Δ","maj7").replace("M7","maj7").replace("Maj7","maj7")
    q = q.replace("min7","min7").replace("m7","min7").replace("−7","min7")
    q = q.replace("ø7","m7b5").replace("ø","m7b5").replace("m7♭5","m7b5").replace("min7b5","m7b5")
    q = q.replace("dim7","dim7").replace("o7","dim7").replace("°7","dim7")
    q = q.replace("dim","dim").replace("°","dim")
    q = q.replace("maj","maj")  # maj 그대로
    q = q.replace("sus","sus4").replace("sus4","sus4")
    q = q.replace("aug","aug").replace("+","aug")
    # “7b9, 7#11 …” → 일단 “7”로 축약
    if re.search(r'7', q) and q not in ("maj7","min7","m7b5","dim7"):
        return "7"
    # 나머지 잡다한 확장/장식은 버림
    base = q
    if base in KEEP_QUALS: return base
    # triad만 남는 케이스
    if "maj7" in base: return "maj7"
    if "min7" in base or "m7" in base: return "min7"
    return base

CH_RE = re.compile(r'^([A-G](?:#|b)?)(.*)$')

def parse_chord(ch: str):
    ch = ch.strip()
    m = CH_RE.match(ch)
    if not m: return None, ""
    root = m.group(1)
    qual = (m.group(2) or "").strip()
    return root, qual

def to_pc(r): return PC.get(r)

def transpose(root: str, semis: int, prefer_flats: bool = True) -> str:
    if root not in PC: return root
    pc = (PC[root] + semis) % 12
    table = ROOTS_FLAT if prefer_flats else ROOTS_SHARP
    return table[pc]

def canon_chord(ch: str):
    r, q = parse_chord(ch)
    if not r: return None
    qn = norm_quality(q)
    # 허용 집합으로 축소
    if qn not in KEEP_QUALS:
        # triad 축약
        if qn in ("maj",""): return f"{r}maj"
        if qn.startswith("min"): return f"{r}min"
        if "dim7" in qn: return f"{r}dim7"
        if "dim" in qn: return f"{r}dim"
        if "aug" in qn: return f"{r}aug"
        if "sus4" in qn: return f"{r}sus4"
        if qn == "7": return f"{r}7"
        return f"{r}maj"
    return f"{r}{qn}"

def looks_non_jazz_seed(seed3):
    if not seed3: return True
    sevn = 0; power = any(("5" in (parse_chord(c)[1] or "").lower()) for c in seed3)
    for c in seed3:
        _, q = parse_chord(c)
        ql = (q or "").lower()
        if any(k in ql for k in ("maj7","min7","m7b5","dim7","7")):
            sevn += 1
    return power or (sevn < 1)  # 3개 중 1개 미만이 7th면 비재즈 취급

def build_iivi_library(n_per_key=20):
    """간단 ii–V–I 패턴 라이브러리(길이 8 내외)"""
    lib = []
    for key_pc in range(12):
        key_root = ROOTS_FLAT[key_pc]
        ii_root = transpose(key_root, 2)   # scale degree 2
        V_root  = transpose(key_root, 7)   # perfect fifth
        I_root  = key_root
        base = [f"{ii_root}min7", f"{V_root}7", f"{I_root}maj7"]
        for _ in range(n_per_key):
            # 간단 변형: 반복/턴어라운드
            seq = base + [f"{ii_root}min7", f"{V_root}7", f"{I_root}maj7", f"{IV(key_root)}maj7", f"{ii_root}min7"]
            lib.append(seq[:8])
    return lib

def IV(root):
    return transpose(root, 5)  # 상행4도(=완전5도 하행)

def load_json_or_jsonl(p):
    """
    다양한 입력 형태를 받아 list[list[str]]로 돌려준다.
    허용 예:
      - {"progressions":[["Cmaj7","F7",...], ["Dm7","G7",...]]}
      - {"progressions":["C F G Am", "Dm G C F", ...]}
      - {"chords":["C F G Am", "Dm G C F", ...]}
      - [{"chords":["C","F","G","Am"]}, {"chords":"Dm G C F"}, ...]
      - ["C F G Am", "Dm G C F", ...]
      - [["C","F","G","Am"], ["Dm","G","C","F"], ...]
    jsonl의 경우 각 줄이 위 형태 중 하나여도 OK.
    """
    from pathlib import Path
    import json, re

    def _split_line(line: str):
        # 쉼표/세미콜론 등 구분자도 허용
        toks = re.split(r'[\s,;|]+', line.strip())
        return [t for t in toks if t]

    def _coerce_to_seqs(obj):
        # 최종적으로 list[list[str]] 반환
        seqs = []

        # 1) dict 형태
        if isinstance(obj, dict):
            # 우선순위: progressions / chords 키
            for key in ("progressions", "chords", "data", "items"):
                if key in obj:
                    val = obj[key]
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, list):
                                seqs.append([str(x) for x in item])
                            elif isinstance(item, str):
                                seqs.append(_split_line(item))
                    elif isinstance(val, str):
                        seqs.append(_split_line(val))
                    if seqs:
                        return seqs
            # dict 안의 값들 중 list/str을 긁어오는 느슨한 처리
            for v in obj.values():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, list):
                            seqs.append([str(x) for x in item])
                        elif isinstance(item, str):
                            seqs.append(_split_line(item))
                elif isinstance(v, str):
                    seqs.append(_split_line(v))
            if seqs:
                return seqs

        # 2) list 형태
        if isinstance(obj, list):
            # 리스트의 요소가 또 리스트거나 문자열일 수 있음
            for item in obj:
                if isinstance(item, list):
                    seqs.append([str(x) for x in item])
                elif isinstance(item, dict):
                    seqs.extend(_coerce_to_seqs(item) or [])
                elif isinstance(item, str):
                    seqs.append(_split_line(item))
            if seqs:
                return seqs

        # 3) 문자열 단독
        if isinstance(obj, str):
            return [_split_line(obj)]

        return None

    path = Path(p)
    text = path.read_text(encoding="utf-8")

    def _gather_from_lines(lines):
        all_seqs = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                seqs = _coerce_to_seqs(obj)
                if seqs:
                    all_seqs.extend(seqs)
            except json.JSONDecodeError:
                # jsonl이 아닌 “그냥 공백 문자열들”로 구성된 파일을 방어적으로 처리
                all_seqs.append(_split_line(line))
        return all_seqs

    # 확장자에 상관없이 먼저 전체를 JSON으로 시도
    try:
        obj = json.loads(text)
        seqs = _coerce_to_seqs(obj)
        if seqs:
            return seqs
    except json.JSONDecodeError:
        pass

    # JSON 실패 시 jsonl/라인 단위 파싱 시도
    lines = text.splitlines()
    seqs = _gather_from_lines(lines)
    if seqs:
        return seqs

    raise ValueError("지원하지 않는 JSON/JSONL 구조 또는 비어있는 파일처럼 보입니다.")

def write_jsonl(out_path, seqs):
    with open(out_path, "w", encoding="utf-8") as f:
        for s in seqs:
            f.write(json.dumps({"chords": s}, ensure_ascii=False))
            f.write("\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_len", type=int, default=8)
    ap.add_argument("--max_len", type=int, default=64)
    ap.add_argument("--transpose", action="store_true", help="12키 전조 증강")
    ap.add_argument("--inject_iivi", action="store_true", help="ii–V–I 라이브러리 주입")
    args = ap.parse_args()

    raw = load_json_or_jsonl(args.inp)
    norm = []
    for seq in raw:
        can = []
        for ch in seq:
            c = canon_chord(str(ch))
            if c: can.append(c)
        if args.min_len <= len(can) <= args.max_len:
            norm.append(can)

    # 전조 증강
    aug = []
    if args.transpose:
        for seq in norm:
            for s in range(12):
                aug.append([transpose(parse_chord(c)[0], s) + parse_chord(c)[1]
                            for c in seq])
    else:
        aug = norm

    # ii–V–I 주입(소량)
    if args.inject_iivi:
        aug += build_iivi_library(n_per_key=10)

    # 중복 제거
    dedup = []
    seen = set()
    for s in aug:
        k = tuple(s)
        if k not in seen:
            seen.add(k); dedup.append(s)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out, dedup)
    print(f"raw={len(raw)} -> norm={len(norm)} -> aug={len(aug)} -> dedup_out={len(dedup)}")

if __name__ == "__main__":
    main()