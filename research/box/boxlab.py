"""
박스권 롱·숏 비중조절 공식 연구

공식 (봉 t의 종가로 계산, 다음 봉 시가에 비중 조정)
-------------------------------------------------
  상단 T  = 직전 N봉 최고가,  하단 B = 직전 N봉 최저가
  중심 M  = (T + B) / 2,       반폭 H = (T - B) / 2
  위치 z  = (종가 - M) / H      (-1 = 하단, 0 = 중심, +1 = 상단)
  효율 ER = |종가 - N봉 전 종가| / N봉 동안 봉별 변동폭 합   (0에 가까울수록 횡보)

  박스권 판정: ER < er_max  그리고  wmin <= 박스폭(T-B)/M <= wmax
  박스 이탈:   종가 > T + b·ATR  또는  종가 < B - b·ATR  →  전량 정리, cooldown 봉 동안 쉬기

  단계 비중 g(|z|): |z| < z1 → 0,  z1~z2 → 1/3,  z2~z3 → 2/3,  z3 이상 → 1
    (박스 끝으로 갈수록 비중을 늘리고, 중심으로 돌아오면 줄이는 구조)

  A. 같은 종목 그리드:   w = -sign(z)·g(|z|)          (하단 롱, 상단 숏 / 개별주식선물)
  B. 롱 + 지수 숏 헤지:  w_L = g(max(-z,0)),  지수 숏 = β·w_L   (β = 최근 120봉 회귀계수)
  C. 롱 전용(비교용):    B에서 헤지를 뺀 것

수익 계산: 비중 변경 전 비중은 갭(전 종가→시가)을, 새 비중은 시가→종가 구간을 가짐.
비용:      비중 변화량 × 편도 비용률 (종목 선물 0.05%, 지수 선물 0.02% 기본)
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).parent / "data"
HEDGE = "069500.KS"


# ---------------------------------------------------------------- 지표
def rolling_max(a, n):
    s = pd.Series(a)
    return s.shift(1).rolling(n, min_periods=n).max().to_numpy()


def rolling_min(a, n):
    s = pd.Series(a)
    return s.shift(1).rolling(n, min_periods=n).min().to_numpy()


def atr(h, l, c, n=14):
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def eff_ratio(c, n):
    s = pd.Series(c)
    net = (s - s.shift(n)).abs()
    path = s.diff().abs().rolling(n).sum()
    return (net / path).to_numpy()


def rolling_beta(rs, ri, n=120):
    a, b = pd.Series(rs), pd.Series(ri)
    cov = a.rolling(n).cov(b)
    var = b.rolling(n).var()
    return (cov / var).clip(0, 3).fillna(1.0).to_numpy()


# ---------------------------------------------------------------- 신호
from numba import njit


@njit(cache=True)
def _state_loop(z, broke, box, g, cool_n):
    n = len(z)
    wA, wL = np.zeros(n), np.zeros(n)
    cool = 0
    for t in range(n):
        if np.isnan(z[t]):
            continue
        if broke[t]:
            cool = cool_n
            continue
        if cool > 0:
            cool -= 1
            continue
        if not box[t]:
            continue
        wA[t] = -np.sign(z[t]) * g[t]
        wL[t] = g[t] if z[t] < 0 else 0.0
    return wA, wL


def step_weight(az, z1, z2, z3):
    return np.where(az >= z3, 1.0, np.where(az >= z2, 2 / 3, np.where(az >= z1, 1 / 3, 0.0)))


def targets(x, p):
    """x: dict of arrays o,h,l,c,day. 반환: (A 비중, B/C 롱 비중) — 봉 종가 기준 목표."""
    o, h, l, c = x["o"], x["h"], x["l"], x["c"]
    N = p["N"]
    T, B = rolling_max(h, N), rolling_min(l, N)
    M, H = (T + B) / 2, (T - B) / 2
    z = (c - M) / np.where(H > 0, H, np.nan)
    er = eff_ratio(c, N)
    width = (T - B) / M
    a = atr(h, l, c)
    box = (er < p["er"]) & (width >= p["wmin"]) & (width <= p["wmax"])
    broke = (c > T + p["b"] * a) | (c < B - p["b"] * a)

    g = step_weight(np.abs(np.nan_to_num(z)), p["z1"], p["z2"], p["z3"])
    wA, wL = _state_loop(z, broke, box, g, int(p["cool"]))
    if p.get("eod"):
        # 장 마감 봉에서는 비중 0 (다음 날로 넘기지 않음)
        last = np.r_[x["day"][1:] != x["day"][:-1], True]
        wA[last] = 0
        wL[last] = 0
    return wA, wL


# ---------------------------------------------------------------- 수익 계산
def pnl(x, w, cost):
    """w[t]: 봉 t 종가에서 정한 목표 비중 → 봉 t+1 시가에 체결."""
    o, c = x["o"], x["c"]
    gap = np.r_[0, o[1:] / c[:-1] - 1]          # 전 종가 → 시가
    intra = c / o - 1                            # 시가 → 종가
    held = np.r_[0, w[:-1]]                      # 봉 t 동안의 새 비중
    prev = np.r_[0, 0, w[:-2]]                   # 시가 전까지의 이전 비중
    r = (1 + prev * gap) * (1 + held * intra) - 1 - np.abs(held - prev) * cost
    return r, np.abs(held - prev)


def run_symbol(x, xi, p, cost_s=0.0005, cost_i=0.0002):
    wA, wL = targets(x, p)
    rA, tA = pnl(x, wA, cost_s)
    rC, tC = pnl(x, wL, cost_s)
    # B: 롱 + 지수 숏 (지수 비중 = -β·w_L)
    rs = x["c"] / np.r_[x["c"][0], x["c"][:-1]] - 1
    ri = xi["c"] / np.r_[xi["c"][0], xi["c"][:-1]] - 1
    beta = rolling_beta(rs, ri)
    rH, tH = pnl(xi, -beta * wL, cost_i)
    rB = rC + rH
    bh = np.r_[0, x["c"][1:] / x["c"][:-1] - 1]
    return {"A": rA, "B": rB, "C": rC, "BH": bh, "turnA": tA, "turnB": tC + tH, "expA": np.abs(np.r_[0, wA[:-1]]), "expB": np.r_[0, wL[:-1]]}


# ---------------------------------------------------------------- 성과
BARS_PER_YEAR = 6 * 248


def stats(r):
    r = np.asarray(r)
    if len(r) == 0:
        return {}
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(eq)
    sd = r.std()
    yrs = len(r) / BARS_PER_YEAR
    return {
        "ret": (eq[-1] - 1) * 100,
        "cagr": (eq[-1] ** (1 / yrs) - 1) * 100 if yrs > 0.2 and eq[-1] > 0 else np.nan,
        "sharpe": r.mean() / sd * np.sqrt(BARS_PER_YEAR) if sd > 0 else 0.0,
        "mdd": (eq / peak - 1).min() * 100,
    }


def load(interval="60m"):
    d = pd.read_parquet(D / f"bars_{interval}.parquet")
    d["day"] = d["ts"].dt.strftime("%Y-%m-%d")
    hedge = d[d.sym == HEDGE].set_index("ts")
    out = {}
    for s, g in d[d.sym != HEDGE].groupby("sym"):
        g = g.set_index("ts").join(hedge[["o", "c"]], rsuffix="_i", how="inner").dropna()
        if len(g) < 500:
            continue
        x = {k: g[k].to_numpy(float) for k in "ohlc"}
        x["day"] = g["day"].to_numpy()
        xi = {"o": g["o_i"].to_numpy(float), "c": g["c_i"].to_numpy(float)}
        out[s] = (g.index, x, xi)
    return out


def grid():
    keys = ["N", "er", "wmin", "z", "b", "eod"]
    vals = [[30, 60, 120], [0.15, 0.25, 0.35], [0.03, 0.05], [(0.25, 0.5, 0.75), (0.4, 0.6, 0.8)], [0.0, 0.5], [False, True]]
    for combo in itertools.product(*vals):
        p = dict(zip(keys, combo))
        z1, z2, z3 = p.pop("z")
        p.update(z1=z1, z2=z2, z3=z3, wmax=0.25, cool=p["N"] // 2)
        yield p


if __name__ == "__main__":
    data = load("60m")
    print("symbols", len(data))
