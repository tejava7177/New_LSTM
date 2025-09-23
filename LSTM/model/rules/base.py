# LSTM/model/rules/base.py
from typing import List

class GenreRule:
    """장르 공통 인터페이스 (필요 메서드만 오버라이드해서 사용)"""

    # 후보 정규화(표기 보정 등)
    def normalize_candidate(self, prev_chord: str, candidate: str) -> str:
        return candidate

    # 후보 필터(불허 후보 제거)
    def filter_candidates(self, candidates: List[str]) -> List[str]:
        return candidates

    # 진행의 부분(또는 전체)에 대한 규칙 점수(0~1)
    def partial_score(self, seq: List[str]) -> float:
        return 0.0

    # 시드 3개가 장르에 부적합한지(예: 재즈에서 파워코드만)
    def seed_is_bad(self, seed3: List[str]) -> bool:
        return False

    # 사용자에게 보여줄 라벨 문자열
    def label(self, seq: List[str], seed_bad: bool) -> str:
        return "특이/실험적 진행"

    # 규칙 가중치(디코딩에서 누적 점수에 곱)
    @property
    def alpha(self) -> float:
        return 0.0