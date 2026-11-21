"""코인 5분봉 단기 매매 후보 시험 (BTC·ETH, 최근 60일 = yfinance 한도)
모든 신호는 '닫힌 봉'까지 정보만 사용, 다음 봉 시가에 진입. 손절은 봉 안 고가·저가로 확인(같은 봉에서 손절·익절 동시면 손절로 가정 — 보수적)
비용: 한쪽 0.05% (수수료 0.04% + 체결 차이 0.01%) → 왕복 0.10%. 참고로 0.02%(지정가 수수료)도 같이.
"""
import numpy as np, pandas as pd, itertools, sys
from pathlib import Path
H = Path(__file__).parent


def load(t):
    d = pd.read_parquet(H / f"{t}_5m.parquet")
    d.columns = [c.lower() for c in d.columns]
    return d


def ema(x, n): return x.ewm(span=n, adjust=False).mean()
def rsi(c, n):
    d = c.diff(); u = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); v = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + u / v)
def atr(d, n=14):
    pc = d.close.shift(); tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def trend1h(d, f=20, s=50):
    h = d.close.resample("1h").last().dropna()
    t = np.sign(ema(h, f) - ema(h, s))
    return t.shift(1).reindex(d.index, method="ffill").fillna(0)          # 직전에 닫힌 1시간봉 기준


def signals(d, kind, p):
    c = d.close; tr = trend1h(d, *p.get("tr", (20, 50))) if p.get("filt", True) else pd.Series(0, d.index)
    if kind == "brk":                       # 1시간 추세 방향으로 n봉 고·저 돌파
        n = p["n"]; hi = d.high.rolling(n).max().shift(1); lo = d.low.rolling(n).min().shift(1)
        L = (c > hi) & (tr > 0); S = (c < lo) & (tr < 0)
    elif kind == "pull":                    # 1시간 추세 방향으로 5분 RSI(2) 눌림
        r = rsi(c, 2); L = (r < p["lo"]) & (tr > 0); S = (r > 100 - p["lo"]) & (tr < 0)
    elif kind == "mr":                      # 추세 없이 볼린저 밴드 바깥 → 평균 회귀
        m = c.rolling(p["n"]).mean(); sd = c.rolling(p["n"]).std(); L = c < m - p["k"] * sd; S = c > m + p["k"] * sd
    elif kind == "rand":
        rng = np.random.default_rng(p["seed"]); x = rng.random(len(c)); L = pd.Series(x < p["pr"], d.index); S = pd.Series(x > 1 - p["pr"], d.index)
    return L.fillna(False).values, S.fillna(False).values


def run(d, kind, p, cost=0.0005):
    L, S = signals(d, kind, p)
    o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values
    A = atr(d).values; r2 = rsi(d.close, 2).values; m = d.close.rolling(p.get("n", 20)).mean().values
    sm, tp, mx = p.get("sm", 1.5), p.get("tp", 2.0), p.get("mx", 24)
    out = []; i = 60; N = len(c)
    while i < N - 2:
        side = 1 if L[i] else -1 if S[i] else 0
        if not side or np.isnan(A[i]): i += 1; continue
        e = o[i + 1]; stop = e - side * sm * A[i]; tgt = e + side * tp * sm * A[i]; j = i + 1; x = None
        while j < min(N, i + 1 + mx):
            if side > 0 and l[j] <= stop: x = min(o[j], stop) if j > i + 1 else stop; break
            if side < 0 and h[j] >= stop: x = max(o[j], stop) if j > i + 1 else stop; break
            if side > 0 and h[j] >= tgt: x = tgt; break
            if side < 0 and l[j] <= tgt: x = tgt; break
            if kind == "pull" and ((side > 0 and r2[j] > 60) or (side < 0 and r2[j] < 40)): x = c[j]; break
            if kind == "mr" and ((side > 0 and c[j] >= m[j]) or (side < 0 and c[j] <= m[j])): x = c[j]; break
            j += 1
        if x is None: j = min(N - 1, j); x = c[j]
        out.append((d.index[i], side * (x / e - 1) - 2 * cost))
        i = j + 1
    return pd.Series([r for _, r in out], index=[t for t, _ in out], dtype=float)


def st(r):
    if len(r) < 5: return dict(n=len(r), avg=np.nan, win=np.nan, tot=np.nan, mdd=np.nan)
    eq = (1 + r).cumprod(); return dict(n=len(r), avg=r.mean() * 100, win=(r > 0).mean() * 100, tot=(eq.iloc[-1] - 1) * 100, mdd=(eq / eq.cummax() - 1).min() * 100)


GRID = {
    "brk": [dict(n=n, sm=sm, tp=tp, mx=mx) for n, sm, tp, mx in itertools.product([12, 24, 48], [1.5, 2.5], [2, 3], [24, 72])],
    "pull": [dict(lo=lo, sm=sm, tp=tp, mx=mx) for lo, sm, tp, mx in itertools.product([5, 10, 20], [1.5, 2.5], [1.5, 3], [12, 36])],
    "mr": [dict(n=n, k=k, sm=sm, tp=tp, mx=mx, filt=False) for n, k, sm, tp, mx in itertools.product([20, 48], [2, 2.5, 3], [1.5, 3], [3], [12, 36])],
}

if __name__ == "__main__":
    D = {t: load(t) for t in ["BTC-USD", "ETH-USD"]}
    cut = D["BTC-USD"].index[0] + (D["BTC-USD"].index[-1] - D["BTC-USD"].index[0]) / 2
    rows = []
    for kind, ps in GRID.items():
        for p in ps:
            for cost in (0.0005, 0.0002):
                rec = dict(kind=kind, p=str({k: v for k, v in p.items() if k != "filt"}), cost=cost)
                for t, d in D.items():
                    r = run(d, kind, p, cost)
                    a, b = r[r.index < cut], r[r.index >= cut]
                    rec[f"{t[:3]}_n"] = len(r); rec[f"{t[:3]}_avg"] = r.mean() * 100 if len(r) else np.nan
                    rec[f"{t[:3]}_tot"] = st(r)["tot"]; rec[f"{t[:3]}_mdd"] = st(r)["mdd"]
                    rec[f"{t[:3]}_a"] = a.mean() * 100 if len(a) else np.nan; rec[f"{t[:3]}_b"] = b.mean() * 100 if len(b) else np.nan
                rows.append(rec)
    R = pd.DataFrame(rows)
    R["ok"] = (R[["BTC_a", "BTC_b", "ETH_a", "ETH_b"]] > 0).sum(axis=1)
    R.to_csv(H / "grid.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    for cost in (0.0005, 0.0002):
        X = R[R.cost == cost]
        print(f"\n=== 비용 한쪽 {cost*100:.2f}% · 종류별 '4칸(BTC·ETH × 앞·뒤 30일) 모두 플러스' 개수 / 전체")
        print(X.groupby("kind").apply(lambda g: f"{(g.ok == 4).sum()}/{len(g)} · 평균 거래당 BTC {g.BTC_avg.mean():.3f}% ETH {g.ETH_avg.mean():.3f}%"))
        print(X.sort_values(["ok", "BTC_avg"], ascending=False).head(8)[["kind", "p", "ok", "BTC_n", "BTC_avg", "BTC_tot", "BTC_mdd", "ETH_n", "ETH_avg", "ETH_tot", "BTC_a", "BTC_b", "ETH_a", "ETH_b"]].round(3).to_string(index=False))
    # 무작위 기준
    rr = [run(D["BTC-USD"], "rand", dict(seed=s, pr=0.01, sm=1.5, tp=2, mx=24)).mean() * 100 for s in range(30)]
    print("\n무작위 진입(BTC, 같은 손절·익절) 거래당 평균:", round(np.mean(rr), 3), "% · 범위", round(min(rr), 3), "~", round(max(rr), 3))
    print("기간:", D["BTC-USD"].index[0].date(), "~", D["BTC-USD"].index[-1].date(), "· 반으로 나눈 기준", cut.date(),
          "· BTC 보유", round((D["BTC-USD"].close.iloc[-1] / D["BTC-USD"].close.iloc[0] - 1) * 100, 1), "%")
