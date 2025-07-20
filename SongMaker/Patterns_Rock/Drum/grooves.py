# -*- coding: utf-8 -*-
# Patterns_Rock/Drum/grooves.py
"""
드럼 스타일별 기본 스트럭처(4/4 기준).
beat = quarterLength 1.0 단위
pos   = 마디 안 오프셋 (0.0 ~ <4.0)
"""

GROOVES = {
    # 8-비트 락: 킥 1·3, 스네어 2·4, 하이햇 8분
    "rock8": {
        "kick":   [0.0, 2.0],
        "snare":  [1.0, 3.0],
        "hihat":  [i * 0.5 for i in range(8)],     # 0.0 → 3.5
    },
    # 16-비트 락: 하이햇 16분
    "rock16": {
        "kick":   [0.0, 2.0, 2.5],
        "snare":  [1.0, 3.0],
        "hihat":  [i * 0.25 for i in range(16)],   # 0.0 → 3.75
    },
    # 하프-타임
    "halfTime": {
        "kick":   [0.0],
        "snare":  [2.0],
        "hihat":  [i * 0.5 for i in range(8)],
    },
}