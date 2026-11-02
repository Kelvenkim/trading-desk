"""장기 테마: 종목 묶기, 테마 지수, 신호 계산 (매일 실행·과거 검증 공용)"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from narrative_def import NARRATIVES, POLICY_WORDS, EXCLUDE, INCLUDE

ROOT = Path(__file__).resolve().parent.parent


def members(universe, themes_path=ROOT / "data/narrative/naver_themes.json"):
    """universe: 종목코드 목록(시총 순). 반환 {key: [code,...]} — 주력 이야기 + 테마 2개 이상 겹치는 이야기"""
    T = json.loads(Path(themes_path).read_text())["themes"]
    uni = set(universe)
    cnt = {}   # code -> {key: 겹친 테마 수}
    for n in NARRATIVES:
        for t in T:
            if any(k in t["name"] for k in n["themes"]):
                for c, _ in t["stocks"]:
                    if c in uni:
                        cnt.setdefault(c, {}).setdefault(n["key"], 0)
                        cnt[c][n["key"]] += 1
    order = {n["key"]: i for i, n in enumerate(NARRATIVES)}
    out = {n["key"]: [] for n in NARRATIVES}
    primary = {}
    for c, d in cnt.items():
        best = max(d, key=lambda k: (d[k], -order[k]))
        primary[c] = best
        for k, v in d.items():
            if k == best or v >= 2:
                out[k].append(c)
    for k, cs in EXCLUDE.items():
        out[k] = [c for c in out[k] if c not in cs]
    for k, cs in INCLUDE.items():
        out[k] += [c for c in cs if c in uni and c not in out[k]]
    rank = {c: i for i, c in enumerate(universe)}
    for k in out:
        out[k].sort(key=lambda c: rank.get(c, 9999))
    return out, primary


def theme_index(C, codes):
    """동일 비중 테마 지수 (하루 수익률 ±30%로 자름, 시작 100)"""
    cols = [c for c in codes if c in C.columns]
    if not cols:
        return None
    r = C[cols].pct_change(fill_method=None).clip(-0.3, 0.3)
    r = r.mean(axis=1, skipna=True).fillna(0)
    return 100 * (1 + r).cumprod()


def policy_hits(title, extra=()):
    t = title
    return any(w in t for w in POLICY_WORDS) or any(w in t for w in extra)
