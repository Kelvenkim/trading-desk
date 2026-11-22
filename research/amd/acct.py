import sys, numpy as np, pandas as pd
from amd import run
sys.path.insert(0, "../orderblock"); from ob import load
P = dict(N=int(sys.argv[1]), m=float(sys.argv[2]), entry="b", tgt=sys.argv[3])
for cost in (0.0005, 0.001):
    T = pd.concat([run(load(t, "1h"), P, cost).assign(sym=t[:3]) for t in ["BTC-USD", "ETH-USD", "SOL-USD"]]).sort_values("t")
    line = f"수수료 {cost*100:.2f}%: n {len(T)} 승률 {(T.r>0).mean():.0%} 평균 {T.r.mean():+.3f}R"
    for rk in (0.01, 0.005, 0.0025):
        eq = (1 + T.r * rk).cumprod(); line += f" | 1회 {rk*100:.2f}%: {eq.iloc[-1]-1:+.0%} 낙폭 {(eq/eq.cummax()-1).min():.0%}"
    print(line)
    h = T.t.min() + (T.t.max() - T.t.min()) / 2; print("   앞 1년", round(T[T.t < h].r.mean(), 3), "뒤 1년", round(T[T.t >= h].r.mean(), 3))
