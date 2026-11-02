"""
매매 계획 (assets/levels.js 의 파이썬판) — 지지·저항, 매수 구간, 손절, 목표(3R), 손익비
bars: 최근 약 130거래일 일봉 [[날짜, 시, 고, 저, 종, 거래량], ...]
"""
import numpy as np

WIN_RATE = 0.32     # research/chart: 추세 눌림목 + 목표 3R 과거 승률 (150종목 2014~2026)


def tick(x):
    return 1 if x < 2000 else 5 if x < 5000 else 10 if x < 20000 else 50 if x < 50000 else 100 if x < 200000 else 500 if x < 500000 else 1000


def r_up(x): t = tick(x); return float(np.ceil(x / t) * t)
def r_dn(x): t = tick(x); return float(np.floor(x / t) * t)
def r_nr(x): t = tick(x); return float(round(x / t) * t)


def atr(h, l, c, n=14):
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    return float(np.mean(tr[-n:])) if len(tr) >= n else float(np.mean(tr)) if len(tr) else 0.0


def swings(h, l, L=5):
    hs, ls = [], []
    for j in range(L, len(h) - L):
        if all(h[j] > h[k] for k in range(j - L, j + L + 1) if k != j):
            hs.append((j, h[j]))
        if all(l[j] < l[k] for k in range(j - L, j + L + 1) if k != j):
            ls.append((j, l[j]))
    return hs, ls


def cluster(pts, tol):
    pts = sorted(pts, key=lambda x: x[1])
    out = []
    for i, p in pts:
        if out and p - out[-1]["hi"] <= tol:
            out[-1]["items"].append(p); out[-1]["hi"] = p
        else:
            out.append({"items": [p], "hi": p})
    return [{"p": float(np.mean(g["items"])), "n": len(g["items"])} for g in out]


def analyze(bars, market_up=True):
    if not bars or len(bars) < 60:
        return None
    a = np.array([b[1:5] for b in bars], dtype=float)
    o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    n, px = len(c), float(c[-1])
    A = atr(h, l, c) or px * 0.02
    m20, m60 = float(np.mean(c[-20:])), float(np.mean(c[-60:]))
    hs, ls = swings(h, l, 5)
    lv = cluster(hs + ls, max(A * 0.6, px * 0.012))
    sup = sorted([x for x in lv if x["p"] < px * 0.995], key=lambda x: -x["p"])[:2]
    res = sorted([x for x in lv if x["p"] > px * 1.005], key=lambda x: x["p"])[:2]
    trend_ok = px > m60 and m20 > m60
    if trend_ok:
        s1 = sup[0]["p"] if sup else m20
        zlo, zhi = s1, max(s1 + 0.5 * A, min(m20, px))
        entry, stop = min(px, zhi), s1 - 0.5 * A
        risk = entry - stop
        p = {"kind": "pullback", "zone": [r_dn(zlo), r_up(zhi)], "entry": r_up(entry), "stop": r_dn(stop),
             "target": r_up(entry + 3 * risk), "in_zone": px <= zhi * 1.005}
    else:
        r1 = res[0]["p"] if res else float(np.max(h[-60:]))
        entry = r1 + 0.2 * A
        stop = max(sup[0]["p"] - 0.5 * A if sup else entry - 2 * A, entry - 2.5 * A)
        risk = entry - stop
        p = {"kind": "breakout", "entry": r_up(entry), "stop": r_dn(stop), "target": r_up(entry + 3 * risk), "in_zone": False}
    p["ok"] = risk > 0 and risk / entry <= 0.15
    p["loss"] = p["stop"] / p["entry"] - 1                 # 실패하면 (음수)
    p["gain"] = p["target"] / p["entry"] - 1               # 성공하면
    p["rr"] = p["gain"] / -p["loss"] if p["loss"] < 0 else None
    p["ev"] = WIN_RATE * p["gain"] + (1 - WIN_RATE) * p["loss"]   # 과거 승률로 본 1회 기대값
    p["trend_ok"], p["market_up"], p["px"] = trend_ok, market_up, px
    p["sup"] = [r_nr(x["p"]) for x in sup]; p["res"] = [r_nr(x["p"]) for x in res]
    p["res1"] = r_nr(res[0]["p"]) if res and res[0]["p"] < p["target"] else None
    p["verdict"] = ("손절 폭이 너무 커서 자리 아님" if not p["ok"] else
                    "관망 — 저항선 돌파 시 고려" if p["kind"] == "breakout" else
                    "추세 좋음, 시장 하락장 주의" if not market_up else
                    "매수 구간 안" if p["in_zone"] else "매수 구간까지 기다리기")
    return p
