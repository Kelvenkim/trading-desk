"""
공식에 붙는 '추가 조건' — 코치 봇(scripts/coach.py)이 시험을 통과한 조건을 스스로 넣고 빼는 곳 (11/22 형: "보고할 필요 없이 너가 해보면서 계속 수정해")
data/us/formula_cfg.json:
  {"amd": {"filters": {"mvol_lo": true, ...}, "params": {"rr": 2.0}, "changed": "2026-11-22"}, "ob": {...}, "tr10": {...}, "log": [...]}
모의 계좌 스크립트(amd_paper.py · ob_paper.py · trend_paper.py)는 진입 직전에 gate()로 검사하고, params()로 숫자를 덮어씀.
코치와 계좌가 같은 함수(FILTERS)를 쓰니 시험과 실제가 같은 규칙.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CF = ROOT / "data/us/formula_cfg.json"

# 이름: (설명, 쓸 수 있는 공식, 코치, 검사 함수(특징 f, 기준값 thr) → True면 진입 허용)
FILTERS = {
    "mvol_lo": ("조작 봉 거래량이 약할 때(박스 평균 1.5배 미만)만", ("amd",), "wyckoff", lambda f, thr: f["mvol"] < 1.5),
    "mvol_hi": ("조작 봉 거래량이 박스 평균 1.5배↑일 때만", ("amd",), "wyckoff", lambda f, thr: f["mvol"] >= 1.5),
    "boxw_narrow": ("박스가 좁은 것(폭 ATR×4 이하)만", ("amd",), "minervini", lambda f, thr: f["boxw"] <= 4),
    "fvg": ("OB 다음 봉에 FVG(빈 구간) 있는 것만", ("ob",), "ict", lambda f, thr: bool(f["fvg"])),
    "gap": ("갭(강한 마지막 캔들) 있는 것만", ("ob",), "ict", lambda f, thr: bool(f["gap"])),
    "vhi": ("OB 마지막 캔들 거래량 1.5배↑만", ("ob",), "wyckoff", lambda f, thr: bool(f["vhi"])),
    "kill": ("런던·뉴욕 장 시작 시간대(킬존)만", ("amd", "ob", "tr10"), "ict", lambda f, thr: (7 <= f["t"].hour <= 10) or (12 <= f["t"].hour <= 16)),
    "htf": ("상위 추세(≈50일선) 쪽 방향만", ("amd", "ob", "tr10"), "livermore", lambda f, thr: bool(f["htf"])),
    "risk_narrow": ("손절 폭이 좁은 쪽 2/3만", ("amd", "ob", "tr10"), "minervini", lambda f, thr: f["risk"] <= thr),
    "vol_lo": ("변동성이 평소보다 낮을 때만", ("amd", "ob", "tr10"), "ptj", lambda f, thr: not f["volhi"]),
    "no_wkend": ("주말 빼기", ("amd", "ob", "tr10"), "ptj", lambda f, thr: f["t"].weekday() < 5),
}
# 숫자 바꿔 보기: 이름: (설명, 공식, 코치, 파라미터, 후보 값들)
VARIANTS = {
    "rr": ("목표 손익비", "amd", "seykota", [1.5, 2.0, 2.5, 3.0]),
    "minrr": ("파동 고점까지 최소 손익비", "ob", "seykota", [0.0, 0.5, 1.0]),
    "tr": ("추적 손절 ATR 배수", "tr10", "seykota", [3.0, 4.0, 5.0, 6.0, 8.0]),
}
DEFAULT_PARAMS = {"amd": {"rr": 2.0}, "ob": {"minrr": 0.0}, "tr10": {"tr": 5.0}}


def load():
    try:
        C = json.loads(CF.read_text())
    except Exception:
        C = {}
    for k, p in DEFAULT_PARAMS.items():
        C.setdefault(k, {}).setdefault("filters", {}); C[k].setdefault("params", dict(p)); C[k].setdefault("changed", None)
    C.setdefault("log", [])
    return C


def save(C):
    CF.write_text(json.dumps(C, ensure_ascii=False, indent=1))


def params(formula):
    return dict(load()[formula]["params"])


def context(d):
    """상위 추세(1시간 EMA 1200 ≈ 50일선 방향), 변동성 수준(ATR%가 90일 중앙값보다 큰지)
    + 11/22 '우리만의 그래프'용 특징: RSI14, 200EMA에서 떨어진 정도, 거래량 배수(20봉 평균 대비), ATR%"""
    c = d.close; pc = c.shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    A = tr.ewm(alpha=1 / 14, adjust=False).mean()
    atrp = A / c
    dl = c.diff(); u = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); w = (-dl.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    vr = (d.volume / d.volume.rolling(20).mean()) if "volume" in d else pd.Series(np.nan, index=d.index)
    return dict(htf=np.sign(c - c.ewm(span=1200, adjust=False).mean()).values,
                volhi=(atrp > atrp.rolling(24 * 90, min_periods=24 * 20).median()).values,
                rsi=(100 - 100 / (1 + u / w)).values, trend=(c / c.ewm(span=200, adjust=False).mean() - 1).values,
                vr=vr.values, atrp=atrp.values)


def feat(X, j, side, t, risk, **extra):
    """진입 순간의 특징 기록 (11/22 형 목표: ① 확실한 자리에 더 큰 비중 ② 그것만 보면 판단되는 '우리만의 그래프')
    모든 계좌의 진입마다 남겨서, 결과(R)와 같이 모음 → 어떤 특징이 결과를 가르는지 찾는 데이터"""
    g = lambda k: (None if X.get(k) is None or not np.isfinite(X[k][j]) else float(X[k][j]))
    tt = pd.Timestamp(t)
    out = dict(side=int(side), hour=int(tt.hour), wd=int(tt.weekday()), risk=round(float(risk) * 100, 3),
               htf=bool(X["htf"][j] == side), volhi=bool(X["volhi"][j]),
               rsi=None if g("rsi") is None else round(g("rsi"), 1), trend=None if g("trend") is None else round(g("trend") * side * 100, 2),
               vr=None if g("vr") is None else round(g("vr"), 2), atrp=None if g("atrp") is None else round(g("atrp") * 100, 3))
    out.update({k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else (bool(v) if isinstance(v, (bool, np.bool_)) else v)) for k, v in extra.items()})
    return out


def check(formula, f, C=None):
    """지금 붙은 조건 중 통과 못 한 것 설명 목록 (빈 목록 = 진입 OK)"""
    C = C or load()
    bad = []
    for name, thr in C.get(formula, {}).get("filters", {}).items():
        if name in FILTERS:
            try:
                if not FILTERS[name][3](f, thr):
                    bad.append(FILTERS[name][0])
            except Exception:
                pass
    return bad


def active_text(formula, C=None):
    C = C or load(); F = C.get(formula, {})
    fl = [FILTERS[n][0] for n in F.get("filters", {}) if n in FILTERS]
    ch = [f"{VARIANTS[k][0]} {v:g}" for k, v in F.get("params", {}).items() if k in VARIANTS and v != DEFAULT_PARAMS[formula].get(k)]
    return " · ".join(fl + ch)
