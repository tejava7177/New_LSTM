# LSTM/model/rules/jazz.py
from typing import List

from LSTM.model.utils.chords import (
    parse_chord, down_fifth, is_seventh_quality, is_power_or_plain,
    norm_enharm_jazz, is_bad_sharp_maj
)

class JazzRule(
    # 장르별 규칙
):
    def __init__(self, alpha=0.8):
        self._alpha = alpha

    @property
    def alpha(self) -> float:
        return self._alpha

    def _has_iivi(self, prog: List[str]) -> int:
        cnt = 0
        for i in range(len(prog)-2):
            a, b, c = prog[i], prog[i+1], prog[i+2]
            ra, qa = parse_chord(a)
            rb, qb = parse_chord(b)
            rc, qc = parse_chord(c)
            if not (ra and rb and rc):
                continue
            qla, qlb, qlc = (qa or "").lower(), (qb or "").lower(), (qc or "").lower()
            if ("m7" in qla) and ("7" in qlb) and ("maj7" in qlc):
                if down_fifth(ra, rb) and down_fifth(rb, rc):
                    cnt += 1
        return cnt

    def _jazz_rule_score(self, prog: List[str]) -> float:
        if not prog: return 0.0
        n = len(prog)
        seventh = 0
        plain   = 0
        enh_bad = 0
        for ch in prog:
            r, q = parse_chord(ch)
            if is_seventh_quality(q): seventh += 1
            if is_power_or_plain(q):  plain   += 1
            if is_bad_sharp_maj(ch):  enh_bad += 1

        ratio_7th   = seventh / float(n)
        ratio_plain = plain   / float(n)
        ii_vi = self._has_iivi(prog)
        enh_pen = enh_bad / float(n)

        score = 0.5*ratio_7th + 0.4*min(1.0, ii_vi/2.0) - 0.3*ratio_plain - 0.1*enh_pen
        return max(0.0, min(1.0, score))

    def _upgrade_to_7th(self, prev: str, cur: str) -> str:
        r, q = parse_chord(cur)
        if not r: return cur
        ql = (q or "").lower()
        if any(t in ql for t in ["7","9","11","13","ø","°","dim","aug","sus"]):
            return cur
        pr, _ = parse_chord(prev or "")
        if pr and down_fifth(pr, r):
            return f"{r}7"
        if "m" in ql and "maj" not in ql:
            return f"{r}m7"
        return f"{r}maj7"

    def normalize_candidate(self, prev_chord: str, candidate: str) -> str:
        c = norm_enharm_jazz(candidate)
        return c

    def filter_candidates(self, candidates: List[str]) -> List[str]:
        keep = []
        for ch in candidates:
            r, q = parse_chord(ch)
            if not r:
                continue
            if is_power_or_plain(q) and "5" in (q or "").lower():  # 파워코드 컷
                continue
            keep.append(ch)
        return keep or candidates  # 모두 걸러지면 원본 반환

    def partial_score(self, seq: List[str]) -> float:
        return self._jazz_rule_score(seq)

    def seed_is_bad(self, seed3: List[str]) -> bool:
        if not seed3: return True
        seventh = 0; power_like = False
        for ch in seed3:
            r, q = parse_chord(ch)
            if is_power_or_plain(q):
                power_like = power_like or ("5" in (q or "").lower())
            if is_seventh_quality(q):
                seventh += 1
        ratio_7 = float(seventh) / max(1.0, float(len(seed3)))
        return power_like or (ratio_7 < (1.0/3.0))

    def label(self, seq: List[str], seed_bad: bool) -> str:
        if seed_bad:
            return "재즈와 거리가 먼 시드(점수 제한)"
        # 간단 라벨링(7th 비율 & ii–V–I)
        ratio_7 = sum(
            1 for ch in seq if is_seventh_quality(parse_chord(ch)[1])
        ) / float(len(seq))
        ii_vi = self._has_iivi(seq)
        if ii_vi > 0 and ratio_7 >= 0.5:
            return "정석 진행"
        elif ratio_7 >= 0.5:
            return "재즈에 가까움"
        return "특이/실험적 진행"

    # 외부에서 호출할 보정(선택)
    def maybe_upgrade(self, prev: str, cand: str) -> str:
        return self._upgrade_to_7th(prev, cand)