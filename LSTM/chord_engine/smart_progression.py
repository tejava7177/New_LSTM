# LSTM/chord_engine/smart_progression.py
from typing import List, Dict, Tuple, Optional, Callable

# --------- Pitch-class & scales ---------
PC = {
    "C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,
    "G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11
}
MAJOR_SCALE = {0,2,4,5,7,9,11}
MINOR_SCALE = {0,2,3,5,7,8,10}

def pc_of(root: str) -> Optional[int]:
    return PC.get(root, None)

def rel_pc(root_pc: int, key_pc: int) -> int:
    return (root_pc - key_pc) % 12

def deg_major(rel: int) -> int:
    """Major key degree mapping (1..7), not including bVII here."""
    table = {0:1, 2:2, 4:3, 5:4, 7:5, 9:6, 11:7}
    return table.get(rel, -1)

# --------- genre quality policies ---------
def jazz_quality_for_degree(deg: int) -> str:
    # I, IV -> maj ; V -> 7 ; II/III/VI -> min ; VII -> dim ; (fallback maj)
    if deg in (1, 4): return "maj"
    if deg == 5:      return "7"
    if deg in (2,3,6):return "min"
    if deg == 7:      return "dim"
    return "maj"

def pop_quality_for_degree(deg: int) -> str:
    if deg in (1,4,5): return "maj"
    if deg in (2,3,6): return "min"
    if deg == 7:       return "dim"
    return "maj"

def rock_quality_for_degree(deg: int) -> str:
    # 파워코드 중심
    return "5power"

def quality_policy_for_genre(genre:str):
    if genre == "jazz": return jazz_quality_for_degree
    if genre == "pop":  return pop_quality_for_degree
    return rock_quality_for_degree

# --------- templates (roman degrees, length 8) ---------
# ROCK은 bVII를 -7로 표기(실현 시 Bb 등으로 처리)
JAZZ_TEMPLATES = [
    [2,5,1,6,  2,5,1,5],   # ii–V–I–vi | ii–V–I–V
    [2,5,1,1,  2,5,1,5],   # 기본 턴어라운드
    [6,2,5,1,  6,2,5,1],   # vi–ii–V–I
    [2,5,1,4,  2,5,1,5],   # 서브도미넌트 터치
]
POP_TEMPLATES = [
    [1,5,6,4,  1,5,6,4],
    [6,4,1,5,  6,4,1,5],
    [1,6,4,5,  1,6,4,5],
]
ROCK_TEMPLATES = [
    [1,-7,4,1,  1,-7,4,5],  # I–bVII–IV | I–bVII–IV–V
    [1,4,5,1,  1,4,5,1],
    [5,4,1,5,  5,4,1,5],
]

def templates_for_genre(genre:str) -> List[List[int]]:
    if genre == "jazz": return JAZZ_TEMPLATES
    if genre == "pop":  return POP_TEMPLATES
    return ROCK_TEMPLATES

# --------- key inference (lightweight) ---------
def score_key_major(seed_roots: List[str], key_root: str) -> float:
    kpc = pc_of(key_root)
    if kpc is None: return -1e9
    score = 0.0
    for r in seed_roots:
        rpc = pc_of(r)
        if rpc is None: continue
        rel = rel_pc(rpc, kpc)
        score += 1.0 if rel in MAJOR_SCALE else -0.5
        if rel == 7: score += 0.4  # V
        if rel == 2: score += 0.2  # ii
    return score

def infer_key(seed_roots: List[str]) -> Tuple[str,str]:
    # 12개 메이저 키 중 최고 점수 선택
    best = ("C","major", -1e9)
    for name in ("C","D","E","F","G","A","B"):  # 내추럴 우선
        s = score_key_major(seed_roots, name)
        if s > best[2]:
            best = (name,"major",s)
    # 나머지(#/b)도 확인
    for name in ("C#","Db","D#","Eb","F#","Gb","G#","Ab","A#","Bb"):
        s = score_key_major(seed_roots, name)
        if s > best[2]:
            best = (name,"major",s)
    return best[0], best[1]

# --------- romanization & realization ---------
def romanize_major(roots: List[str], key_root: str) -> List[int]:
    kpc = pc_of(key_root)
    out: List[int] = []
    for r in roots:
        rpc = pc_of(r)
        if rpc is None: out.append(-1); continue
        rel = rel_pc(rpc, kpc)
        out.append(deg_major(rel))
    return out

def _abs_name(pc_val: int) -> str:
    # 간단 고정 이름(기본 표기)
    ABS = {0:"C",1:"C#",2:"D",3:"Eb",4:"E",5:"F",6:"F#",7:"G",8:"Ab",9:"A",10:"Bb",11:"B"}
    return ABS[pc_val % 12]

def realize_major(degs: List[int], key_root: str) -> List[str]:
    """degree -> 절대 루트명. bVII는 -7로 인코딩, 나머지는 1..7."""
    kpc = pc_of(key_root)
    pitch_of_degree = {1:0, 2:2, 3:4, 4:5, 5:7, 6:9, 7:11, -7:10}  # -7 == bVII
    out: List[str] = []
    for d in degs:
        if d == -1:
            out.append(key_root); continue
        pc_rel = pitch_of_degree.get(d, 0)
        abs_pc = (kpc + pc_rel) % 12
        out.append(_abs_name(abs_pc))
    return out

# --------- anchor & template rotation ---------
def pick_anchor(seed_degs: List[int]) -> int:
    # I 최우선, 다음 V, 없으면 첫 유효 degree
    candidates: List[Tuple[int,int]] = []
    for i, d in enumerate(seed_degs):
        if d == 1: candidates.append((0, i))
        elif d == 5: candidates.append((1, i))
    if candidates:
        candidates.sort()
        return candidates[0][1]
    for i, d in enumerate(seed_degs):
        if d != -1: return i
    return 0

def insert_anchor_into_template(template: List[int], anchor_deg: int) -> List[int]:
    """템플릿에서 anchor_deg가 처음 나타나는 위치로 회전. 실패 시 원본."""
    tgt = None
    for i, d in enumerate(template):
        if d == anchor_deg or (anchor_deg == 1 and d == 1):
            tgt = i; break
    if tgt is None: return template[:]
    return template[tgt:] + template[:tgt]

# --------- quality & chord realization ---------
def quality_suffix(q: str) -> str:
    if q == "5power": return "5"
    if q == "maj":    return ""
    if q == "min":    return "m"
    if q == "7":      return "7"
    if q == "sus4":   return "sus4"
    if q == "dim":    return "dim"
    if q == "aug":    return "aug"
    return ""

def apply_genre_quality(degs: List[int], genre:str) -> List[str]:
    qf = quality_policy_for_genre(genre)
    return [qf(d) if d != -1 else "maj" for d in degs]

def realize_progression(template_degs: List[int], key_root: str, genre:str) -> List[str]:
    roots = realize_major(template_degs, key_root)
    quals = apply_genre_quality(template_degs, genre)
    return [f"{r}{quality_suffix(q)}" for r, q in zip(roots, quals)]

# --------- rule scoring ---------
def _jazz_rule_score(roman: List[int], chords: List[str]) -> float:
    # ii–V 개수, I/V 존재, 7th 비율
    iiV = sum(1 for i in range(len(roman)-1) if roman[i] == 2 and roman[i+1] == 5)
    has_I = any(d == 1 for d in roman)
    has_V = any(d == 5 for d in roman)
    sev_ratio = sum(ch.endswith("7") for ch in chords) / max(1, len(chords))
    return 0.5 * min(1.0, iiV / 2.0) + 0.3 * (1.0 if (has_I and has_V) else 0.0) + 0.2 * sev_ratio

def _pop_rule_score(roman: List[int], chords: List[str]) -> float:
    pattern_bonus = 1.0 if roman[:4] in ([1,5,6,4], [6,4,1,5], [1,6,4,5]) else 0.5
    min_ratio = sum(ch.endswith("m") for ch in chords) / max(1, len(chords))
    return 0.6 * pattern_bonus + 0.4 * (1.0 - abs(min_ratio - 0.4))

def _rock_rule_score(roman: List[int], chords: List[str]) -> float:
    power_ratio = sum(ch.endswith("5") for ch in chords) / max(1, len(chords))
    has_bVII = any(d == -7 for d in roman)
    return 0.5 * power_ratio + 0.5 * (1.0 if has_bVII else 0.6)

def _rule_score(genre: str, roman: List[int], chords: List[str]) -> float:
    if genre == "jazz": return _jazz_rule_score(roman, chords)
    if genre == "pop":  return _pop_rule_score(roman, chords)
    return _rock_rule_score(roman, chords)

# --------- candidate generation ---------
def _generate_rule_candidates(
    genre: str,
    seed_roots: List[str],
    steps: int = 5  # 현재 템플릿 길이 8 고정(steps는 향후 확장용)
) -> List[Tuple[List[str], List[int], str]]:
    """
    반환: [(chords, roman, key_root), ...]
    """
    key_root, _mode = infer_key(seed_roots)
    seed_degs = romanize_major(seed_roots, key_root)
    anchor_idx = pick_anchor(seed_degs)
    anchor_deg = seed_degs[anchor_idx] if seed_degs[anchor_idx] != -1 else 1

    cands: List[Tuple[List[str], List[int], str]] = []
    for t in templates_for_genre(genre):
        rotated = insert_anchor_into_template(t, anchor_deg)
        chords = realize_progression(rotated, key_root, genre)
        cands.append((chords, rotated, key_root))
    return cands

# --------- public APIs ---------
def generate_topk(
    genre: str,
    seed_roots: List[str],
    steps: int = 5,
    k: int = 3,
    scorer: Optional[Callable[[List[str]], float]] = None,
    alpha: float = 0.6,  # final = alpha*rule + (1-alpha)*model
) -> List[Tuple[List[str], float]]:
    """
    룰 기반 후보 생성 후, (선택) 모델 점수와 블렌딩해 상위 k개 반환.
    반환: [(seq, final_score0_1), ...] 내림차순
    """
    candidates = _generate_rule_candidates(genre, seed_roots, steps=steps)
    ranked: List[Tuple[List[str], float]] = []

    for chords, roman, _key in candidates:
        rule_s = _rule_score(genre, roman, chords)  # 0~1
        if scorer is not None:
            try:
                model_s = float(scorer(chords))  # 0~1
            except Exception:
                model_s = 0.0
            final = alpha * rule_s + (1.0 - alpha) * model_s
        else:
            final = rule_s
        ranked.append((chords, final))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:k]

def generate_top3(
    seed: List[Dict[str, str]],
    genre: str,
    topk: int = 3
) -> Dict:
    """
    예전 호환용: seed는 [{"root":"D","quality":"7"}, ...] 형태(quality는 힌트일 뿐).
    딕셔너리 포맷으로 키/로만/스코어까지 반환.
    """
    seed_roots = [s.get("root","C") for s in seed]
    key_root, _mode = infer_key(seed_roots)
    seed_degs = romanize_major(seed_roots, key_root)
    anchor_idx = pick_anchor(seed_degs)
    anchor_deg = seed_degs[anchor_idx] if seed_degs[anchor_idx] != -1 else 1

    proposals = []
    for t in templates_for_genre(genre):
        rotated = insert_anchor_into_template(t, anchor_deg)
        chords = realize_progression(rotated, key_root, genre)
        score = _rule_score(genre, rotated, chords)
        proposals.append({
            "chords": chords,
            "roman":  rotated,
            "score":  round(float(score), 3)
        })

    proposals.sort(key=lambda x: x["score"], reverse=True)
    return {
        "key": key_root,
        "anchor_index": anchor_idx,
        "proposals": proposals[:topk],
        "notes": [
            f"inferred_key={key_root} major",
            "qualities auto-assigned per-genre"
        ]
    }