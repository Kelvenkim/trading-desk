"""제한은 그대로, 코인 수를 늘리면? (지금 규칙 그대로 10개 코인 추가, 1시간봉 약 2년)"""
import numpy as np, pandas as pd, yfinance as yf
from pathlib import Path
from ob import find_obs, simulate
H = Path(__file__).parent / "data"
COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "DOT-USD", "BCH-USD", "TRX-USD"]
rows = []
for t in COINS:
    f = H / f"{t}_1h.parquet"
    if f.exists():
        d = pd.read_parquet(f)
    else:
        d = yf.Ticker(t).history(period="730d", interval="1h").dropna(); d.columns = [c.lower() for c in d.columns]
        d = d[["open", "high", "low", "close", "volume"]]; d.to_parquet(f)
    O = [o for o in find_obs(d, {"K": 2.0, "L": 20}) if o["k"] == 2]
    T = simulate(d, O, dict(W=48, hold=72, K=2.0, need=("gap", "sweep", "fvg"), stop_rule=1, tp="half", cost=.0005, minrr=1.0)); T["sym"] = t.replace("-USD", "")
    rows.append(T)
T = pd.concat(rows); h = T.te.min() + (T.te.max() - T.te.min()) / 2
print(T.groupby("sym").agg(n=("r", "size"), win=("r", lambda x: (x > 0).mean()), avgR=("r", "mean")).round(3).sort_values("avgR").to_string())
new = T[~T.sym.isin(["BTC", "ETH", "SOL"])]
for nm, X in [("전체 13개", T), ("새로 넣은 10개만", new)]:
    hh = X.te.min() + (X.te.max() - X.te.min()) / 2
    print(f"{nm}: {len(X)}번 승률 {(X.r>0).mean():.0%} 평균 {X.r.mean():+.3f}R · 앞1년 {X[X.te<hh].r.mean():+.2f} 뒤1년 {X[X.te>=hh].r.mean():+.2f} · 플러스 코인 {(X.groupby('sym').r.mean()>0).sum()}/{X.sym.nunique()} · 비용0.1% {(X.r-0.001/X.risk).mean():+.3f}R")
