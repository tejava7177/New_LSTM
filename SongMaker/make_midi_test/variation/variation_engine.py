# make_midi_test/variation_engine.py
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

JAZZ_DRUM_STYLES = ["medium_swing","up_swing","two_feel","shuffle_blues","brush_ballad"]
COMP_STYLES = ["minimal","shell","drop2","quartal"]
POINT_DENSITIES = ["light","medium","busy"]
POINT_POOL = ["trumpet","alto_sax","tenor_sax","trombone","clarinet","flute","vibraphone"]

@dataclass
class Humanize:
    swing_push: float    # -0.02~+0.02 beat
    vel_jitter: int      # 0~12
    dur_shrink: float    # 0.0~0.15

@dataclass
class VariationPlan:
    seed: int
    drum_style: str
    comp_style: str
    point_inst: List[str]
    point_density: str
    phrase_len: int
    fill_prob: float
    form: List[str]                   # ex) ["A","A","B","A"]
    section_bars: List[Tuple[int,int]]
    humanize: Humanize

def sample_variation(num_bars: int, seed: Optional[int]=None) -> VariationPlan:
    if seed is None:
        seed = random.randrange(1_000_000_000)
    r = random.Random(seed)

    forms = [
        (["A","A","B","A"], [ (0, num_bars//4), (num_bars//4, num_bars//4),
                              (num_bars//2, num_bars//4), (3*num_bars//4, num_bars-(3*num_bars//4)) ]),
        (["A","B","A","C"], [ (0, num_bars//4), (num_bars//4, num_bars//4),
                              (num_bars//2, num_bars//4), (3*num_bars//4, num_bars-(3*num_bars//4)) ]),
        (["Chorus"], [(0, num_bars)]),
    ]
    form, section_bars = r.choice(forms)

    drum_style = r.choice(JAZZ_DRUM_STYLES)
    comp_style = r.choices(COMP_STYLES, weights=[3,2,2,1], k=1)[0]
    point_density = r.choices(POINT_DENSITIES, weights=[3,2,1], k=1)[0]
    pick_n = r.choice([0,1,2,3])
    point_inst = r.sample(POINT_POOL, k=pick_n)

    phrase_len = r.choice([2,4,8])
    fill_prob = round(r.uniform(0.08, 0.25), 2)

    humanize = Humanize(
        swing_push=r.uniform(-0.015, 0.020),
        vel_jitter=r.randint(2, 10),
        dur_shrink=r.uniform(0.02, 0.10)
    )

    return VariationPlan(
        seed=seed, drum_style=drum_style, comp_style=comp_style,
        point_inst=point_inst, point_density=point_density,
        phrase_len=phrase_len, fill_prob=fill_prob,
        form=form, section_bars=section_bars, humanize=humanize
    )