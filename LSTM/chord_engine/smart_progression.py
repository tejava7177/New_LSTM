# LSTM/chord_engine/smart_progression.py
from typing import List, Dict, Tuple, Optional, Callable
import math
import random

# --------- utilities ---------
PC = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,
      "G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}
ABS = {0:"C",1:"C#",2:"D",3:"Eb",4:"E",5:"F",6:"F#",7:"G",8:"Ab",9:"A",10:"Bb",11:"B"}

MAJOR_SCALE = {0,2,4,5,7,9,11}
MINOR_SCALE = {0,2,3,5,7,8,10}

def pc_of(root: str) -> Optional[int]:
    return PC.get(root, None)

def rel_pc(root_pc: int, key_pc: int) -> int:
    return (root_pc - key_pc) % 12

def deg_major(rel: int) -> int:
    return {0:1, 2:2, 4:3, 5:4, 7:5, 9:6, 11:7}.get(rel, -1)

def deg_minor(rel: int) -> int:
    return {0:1, 2:2, 3:3, 5:4, 7:5, 8:6, 10:7}.get(rel, -1)

# --------- genre policies ---------
def jazz_quality_for_degree(deg: int) -> str:
    if deg in (1,4): return "maj"   # I, IV
    if deg == 5:     return "7"     # V
    if deg in (2,3,6): return "m"   # ii/iii/vi
    if deg == 7:     return "dim"   # vii°
    return "maj"

def pop_quality_for_degree(deg: int) -> str:
    if deg in (1,4,5): return "maj"
    if deg in (2,3,6): return "m"
    if deg == 7:       return "dim"
    return "maj"

def rock_quality_for_degree(deg: int) -> str:
    return "5power"

# --------- templates (roman degrees, length 8) ---------
JAZZ_TEMPLATES = [
    [2,5,1,6,  2,5,1,5],    # ii–V–I–vi | ii–V–I–V
    [2,5,1,1,  2,5,1,5],    # turn-around
    [6,2,5,1,  6,2,5,1],    # vi–ii–V–I
    [2,5,1,4,  2,5,1,5],    # IV touch
    [3,6,2,5,  1,4,2,5],    # iii–vi–ii–V | I–IV–ii–V
    [2,5,2,5,  1,6,2,5],    # 반복 ii–V + I–vi–ii–V
]

POP_TEMPLATES = [
    [1,5,6,4,  1,5,6,4],
    [6,4,1,5,  6,4,1,5],
    [1,6,4,5,  1,6,4,5],
]

ROCK_TEMPLATES = [
    [1,7,4,1,  1,7,4,5],    # I–bVII–IV
    [1,4,5,1,  1,4,5,1],
    [5,4,1,5,  5,4,1,5],
]

def templates_for_genre(genre:str) -> List[List[int]]:
    if genre=="jazz": return JAZZ_TEMPLATES
    if genre=="pop":  return POP_TEMPLATES
    return ROCK_TEMPLATES

def quality_policy_for_genre(genre:str):
    if genre=="jazz": return jazz_quality_for_degree
    if genre=="pop":  return pop_quality_for_degree
    return rock_quality_for_degree

# --------- key inference (very lightweight) ---------
def score_key_major(seed_roots: List[str], key_root: str) -> float:
    kpc = pc_of(key_root)
    if kpc is None: return -1e9
    score = 0.0
    for r in seed_roots:
        rpc = pc_of(r);
        if rpc is None: continue
        rel = rel_pc(rpc, kpc)
        score += 1.0 if rel in MAJOR_SCALE else -0.5
        if rel==7: score += 0.4  # V
        if rel==2: score += 0.2  # ii
    return score

def infer_key(seed_roots: List[str]) -> Tuple[str,str]:
    best = ("C","major", -1e9)
    for name in ("C","D","E","F","G","A","B"):
        s = score_key_major(seed_roots, name)
        if s > best[2]: best = (name,"major",s)
    return best[0], best[1]

# --------- romanization & realization ---------
def romanize_major(roots: List[str], key_root: str) -> List[int]:
    kpc = pc_of(key_root)
    out = []
    for r in roots:
        rpc = pc_of(r)
        if rpc is None: out.append(-1); continue
        rel = rel_pc(rpc, kpc)
        out.append(deg_major(rel))
    return out

def realize_major(degs: List[int], key_root: str) -> List[str]:
    kpc = pc_of(key_root)
    pitch_of_degree = {1:0,2:2,3:4,4:5,5:7,6:9,7:11}
    out = []
    for d in degs:
        if d==-1: out.append(key_root); continue
        abs_pc = (kpc + pitch_of_degree[d]) % 12
        out.append(ABS[abs_pc])
    return out

def quality_suffix(q:str)->str:
    if q=="5power": return "5"
    if q=="maj":    return ""
    if q=="m":      return "m"
    if q=="7":      return "7"
    if q=="sus4":   return "sus4"
    if q=="dim":    return "dim"
    if q=="aug":    return "aug"
    return ""

def apply_genre_quality(degs: List[int], genre:str) -> List[str]:
    qf = quality_policy_for_genre(genre)
    return [qf(d) if d!=-1 else "maj" for d in degs]

def realize_progression(template_degs: List[int], key_root: str, genre:str) -> List[str]:
    roots = realize_major(template_degs, key_root)
    quals = apply_genre_quality(template_degs, genre)
    return [f"{r}{quality_suffix(q)}" for r,q in zip(roots, quals)]

# --------- variations for jazz to increase diversity ---------
def _tritone_pc(pc:int)->int:
    return (pc + 6) % 12

def _root_of(ch:str)->str:
    for i,c in enumerate(ch):
        if i==0 and c in "ABCDEFG":
            if len(ch)>1 and ch[1] in "#b": return ch[:2]
            return ch[0]
    return ch

def _is7(ch:str)->bool:
    return ch.endswith("7")

def _ism(ch:str)->bool:
    return ch.endswith("m") and not ch.endswith("maj")  # 'm' triad

def jazz_variations(seq: List[str], key_root: str) -> List[List[str]]:
    out = []
    # v1) 트라이톤 대리: 마지막 7 한 개를 bII(또는 tritone root)7로 치환
    s1 = seq[:]
    for i in range(len(s1)-1, -1, -1):
        if _is7(s1[i]):
            r = _root_of(s1[i])
            rpc = pc_of(r);
            if rpc is not None:
                tpc = _tritone_pc(rpc)
                s1[i] = ABS[tpc] + "7"
                out.append(s1);
            break
    # v2) 백도어 도미넌트: (… V7 → I) 패턴의 V7을 bVII7로 치환
    s2 = seq[:]
    # 키 루트의 V7 root
    key_pc = pc_of(key_root)
    v_pc = (key_pc + 7) % 12
    for i in range(len(s2)-1):
        if _is7(s2[i]) and pc_of(_root_of(s2[i])) == v_pc:
            s2[i] = ABS[(key_pc + 10) % 12] + "7"  # bVII7
            out.append(s2)
            break
    # v3) 세컨더리 도미넌트: 아무 'Xm' 하나를 그 V/X 로 치환 (길이 유지)
    s3 = seq[:]
    for i in range(len(s3)):
        if _ism(s3[i]):
            r = _root_of(s3[i]); rpc = pc_of(r)
            if rpc is not None:
                v_of_x = ABS[(rpc + 7) % 12] + "7"
                s3[i] = v_of_x
                out.append(s3)
                break
    # v4) 차용 IVm: 마지막 I 근처의 IV(maj)를 IVm으로
    s4 = seq[:]
    for i in range(len(s4)-2, -1, -1):
        if not s4[i].endswith("m"):
            # 근이 IV인가?
            if pc_of(_root_of(s4[i])) == (pc_of(key_root)+5)%12:
                s4[i] = _root_of(s4[i]) + "m"
                out.append(s4)
                break
    # 고유성 확보
    uniq = []
    seen = set()
    for cand in out:
        t = tuple(cand)
        if t not in seen:
            uniq.append(cand); seen.add(t)
    return uniq

# --------- anchor & hint logic ---------
def pick_anchor(seed_degs: List[int]) -> int:
    candidates = []
    for i,d in enumerate(seed_degs):
        if d in (1,5): candidates.append((0 if d==1 else 1, i))
    if candidates:
        candidates.sort()
        return candidates[0][1]
    for i,d in enumerate(seed_degs):
        if d!=-1: return i
    return 0

def insert_anchor_into_template(template: List[int], anchor_deg: int) -> List[int]:
    tgt_pos = None
    for i,d in enumerate(template):
        if d == anchor_deg or (anchor_deg==1 and d==1):
            tgt_pos = i; break
    if tgt_pos is None: return template[:]
    return template[tgt_pos:]+template[:tgt_pos]

# --------- rule-only candidate generator ---------
def _generate_rule_candidates(genre:str, seed_roots: List[str], steps:int=5) -> Tuple[str,List[List[str]]]:
    key_root, mode = infer_key(seed_roots)
    seed_degs = romanize_major(seed_roots, key_root)
    anchor_idx = pick_anchor(seed_degs)
    anchor_deg = seed_degs[anchor_idx] if seed_degs[anchor_idx]!=-1 else 1

    templs = templates_for_genre(genre)
    base_cands: List[List[str]] = []
    for t in templs:
        rotated = insert_anchor_into_template(t, anchor_deg)
        realized = realize_progression(rotated, key_root, genre)
        base_cands.append(realized)

    # 재즈 다양화
    if genre=="jazz":
        more: List[List[str]] = []
        for c in base_cands:
            more.extend(jazz_variations(c, key_root))
        base_cands.extend(more)

    # 중복 제거
    uniq = []
    seen = set()
    for c in base_cands:
        t = tuple(c)
        if t not in seen:
            uniq.append(c); seen.add(t)
    return key_root, uniq

# --------- simple rule scores ---------
def _jazz_rule_score(roman: List[int], chords: List[str]) -> float:
    iiV = sum(1 for i in range(len(roman)-1) if roman[i]==2 and roman[i+1]==5)
    has_I = any(d==1 for d in roman)
    has_V = any(d==5 for d in roman)
    sev_ratio = sum(ch.endswith("7") for ch in chords)/len(chords)
    return 0.5*min(1.0, iiV/2) + 0.3*(1.0 if has_I and has_V else 0.0) + 0.2*sev_ratio

def _pop_rule_score(roman: List[int], chords: List[str]) -> float:
    pattern_bonus = 1.0 if roman[:4] in ([1,5,6,4],[6,4,1,5],[1,6,4,5]) else 0.5
    min_ratio = sum(ch.endswith("m") for ch in chords)/len(chords)
    return 0.6*pattern_bonus + 0.4*(1.0 - abs(min_ratio-0.4))

def _rock_rule_score(roman: List[int], chords: List[str]) -> float:
    power_ratio = sum(ch.endswith("5") for ch in chords)/len(chords)
    bVII = any("b7" in str(d).lower() for d in [])  # placeholder
    return 0.6*power_ratio + 0.4*0.8

# --------- main entry (rule + optional model scorer) ---------
def generate_topk(
    genre: str,
    seed_roots: List[str],
    steps: int = 5,
    k: int = 3,
    scorer: Optional[Callable[[List[str]], float]] = None,
    alpha: float = 0.6,
) -> List[Tuple[List[str], float]]:
    key_root, cands = _generate_rule_candidates(genre, seed_roots, steps=steps)

    # 간단 로만 수치화(룰 점수 계산용)
    def roman_of(chords: List[str]) -> List[int]:
        roots = [_root_of(ch) for ch in chords]
        return romanize_major(roots, key_root)

    ranked: List[Tuple[List[str], float]] = []
    for seq in cands:
        r = roman_of(seq)
        if genre=="jazz": rule_score = _jazz_rule_score(r, seq)
        elif genre=="pop": rule_score = _pop_rule_score(r, seq)
        else: rule_score = _rock_rule_score(r, seq)
        if scorer is not None:
            try:
                model_score = float(scorer(seq))
            except Exception:
                model_score = 0.0
            final = alpha * rule_score + (1.0 - alpha) * model_score
        else:
            final = rule_score
        ranked.append((seq, final))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:k]