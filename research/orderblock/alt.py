"""
코인 단타 대체 방법 찾기 (11/22 형 요청: 10배 단타 평균 회귀는 접고 다른 방법)
1시간봉 2년(BTC·ETH·SOL) + 15분봉 60일. 수수료 한쪽 0.05% / 0.02%(지정가 참고). 결과는 R(손절 거리 단위).
후보: ① 돈치안 돌파 + 200EMA 추세 ② 추세 눌림(EMA20 되돌림 + RSI) ③ 변동성 수축 뒤 돌파 ④ 일봉 시가 범위 돌파
청산: 초기 손절 ATR×sm, 추적 손절(최고가−ATR×tr), 최대 보유
"""
import itertools, sys
import numpy as np, pandas as pd
from ob import load, atr


def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def rsi(c, n=14):
    d = c.diff(); u = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); v = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + u / v)


def signals(d, kind, p):
    c = d.close; e200 = ema(c, 200); up = c > e200; dn = c < e200
    if kind == "donch":
        n = p["n"]; hi = d.high.rolling(n).max().shift(1); lo = d.low.rolling(n).min().shift(1)
        L = (c > hi) & up; S = (c < lo) & dn
    elif kind == "pull":
        e20, e50 = ema(c, 20), ema(c, 50); r = rsi(c, 14)
        tu = (e50 > e200) & up; td = (e50 < e200) & dn
        L = tu & (d.low <= e20) & (c > d.open) & (r.shift(1) < p["r"]); S = td & (d.high >= e20) & (c < d.open) & (r.shift(1) > 100 - p["r"])
    elif kind == "squeeze":
        m = c.rolling(20).mean(); sd = c.rolling(20).std(); w = (4 * sd / m)
        sq = w <= w.rolling(p["n"]).quantile(0.2)
        hi = d.high.rolling(20).max().shift(1); lo = d.low.rolling(20).min().shift(1)
        L = sq.shift(1) & (c > hi) & up; S = sq.shift(1) & (c < lo) & dn
    elif kind == "orb":                     # UTC 하루 첫 k봉 범위 돌파
        day = d.index.floor("1D"); k = p["k"]
        g = d.groupby(day); idx = g.cumcount()
        rh = g.high.transform(lambda x: x.iloc[:k].max()); rl = g.low.transform(lambda x: x.iloc[:k].min())
        L = (idx >= k) & (c > rh) & up; S = (idx >= k) & (c < rl) & dn
        first = (L | S).groupby(day).cumsum() == 1
        L, S = L & first, S & first
    return L.fillna(False).values, S.fillna(False).values


def run(d, kind, p, cost=0.0005):
    L, S = signals(d, kind, p)
    o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values
    A = atr(d); sm, tr, mx = p.get("sm", 2.0), p.get("tr", 3.0), p.get("mx", 96)
    out = []; i = 210; N = len(c)
    while i < N - 2:
        s = 1 if L[i] else -1 if S[i] else 0
        if not s or not np.isfinite(A[i]):
            i += 1; continue
        e = o[i + 1]; risk = sm * A[i]; stop = e - s * risk; best = e; x = None; j = i + 1
        while j < min(N, i + 1 + mx):
            if (s > 0 and l[j] <= stop) or (s < 0 and h[j] >= stop):
                x = (min(o[j], stop) if s > 0 else max(o[j], stop)) if j > i + 1 else stop; break
            best = max(best, h[j]) if s > 0 else min(best, l[j])
            trail = best - s * tr * A[j]
            stop = max(stop, trail) if s > 0 else min(stop, trail)
            j += 1
        if x is None:
            j = min(N - 1, j); x = c[j]
        net = s * (x / e - 1) - 2 * cost
        out.append((d.index[i], net / (risk / e), net, risk / e))
        i = j + 1
    return pd.DataFrame(out, columns=["t", "r", "pct", "risk"])


GRID = {
    "donch": [dict(n=n, sm=sm, tr=tr) for n, sm, tr in itertools.product([20, 48, 96], [1.5, 2.5], [2, 3, 5])],
    "pull": [dict(r=r, sm=sm, tr=tr) for r, sm, tr in itertools.product([40, 50], [1.5, 2.5], [2, 3, 5])],
    "squeeze": [dict(n=n, sm=sm, tr=tr) for n, sm, tr in itertools.product([100, 200], [1.5, 2.5], [2, 3, 5])],
    "orb": [dict(k=k, sm=sm, tr=tr) for k, sm, tr in itertools.product([2, 4, 8], [1.5, 2.5], [2, 3, 5])],
}

if __name__ == "__main__":
    iv = sys.argv[1] if len(sys.argv) > 1 else "1h"
    D = {t: load(t, iv) for t in ["BTC-USD", "ETH-USD", "SOL-USD"]}
    rows = []
    for kind, ps in GRID.items():
        for p in ps:
            for cost in (0.0005, 0.0002):
                rec = dict(kind=kind, p=str(p), cost=cost); qs = []
                for t, d in D.items():
                    T = run(d, kind, {**p, "mx": 96 if iv == "1h" else 192}, cost)
                    q = [d.index[0] + (d.index[-1] - d.index[0]) * f for f in (0, .25, .5, .75, 1.01)]
                    rec[t[:3] + "_n"] = len(T); rec[t[:3]] = T.r.mean() if len(T) else np.nan
                    qs += [T[(T.t >= q[k]) & (T.t < q[k + 1])].r.mean() for k in range(4)]
                rec["avgR"] = np.nanmean([rec["BTC"], rec["ETH"], rec["SOL"]])
                rec["pos_q"] = int(np.sum(np.array(qs) > 0)); rec["n"] = rec["BTC_n"] + rec["ETH_n"] + rec["SOL_n"]
                rows.append(rec)
    R = pd.DataFrame(rows); R.to_csv(f"alt_{iv}.csv", index=False)
    pd.set_option("display.width", 250)
    for cost in (0.0005, 0.0002):
        X = R[R.cost == cost].sort_values(["avgR"], ascending=False)
        print(f"\n=== {iv} · 수수료 한쪽 {cost * 100:.2f}% · 상위 10 (pos_q = 코인 3 × 기간 4 = 12칸 중 플러스 칸 수)")
        print(X.head(10)[["kind", "p", "n", "BTC", "ETH", "SOL", "avgR", "pos_q"]].round(3).to_string(index=False))
        print(X.groupby("kind").avgR.agg(["mean", "max"]).round(3))
