import numpy as np, pandas as pd
from ob import *
rows = []
for tk in ["BTC-USD", "ETH-USD", "SOL-USD"]:
    d = load(tk, "1h"); obs = find_obs(d, {"K": 2.0}); obs2 = [o for o in obs if o["k"] == 2]
    q = [d.index[0] + (d.index[-1] - d.index[0]) * f for f in (0, .25, .5, .75, 1.01)]
    for name, O, need, cost, sr in [("3필터·2캔들", obs2, ("gap", "sweep", "fvg"), .0005, 1), ("3필터·2캔들·지정가", obs2, ("gap", "sweep", "fvg"), .0002, 1),
                                ("갭+흡수·2캔들", obs2, ("gap", "sweep"), .0005, 1), ("3필터·2캔들·봉마감손절", obs2, ("gap", "sweep", "fvg"), .0005, 2)]:
        T = simulate(d, O, dict(W=48, hold=72, K=2.0, need=need, stop_rule=sr, tp="half", cost=cost))
        S = stats(T); qs = [T[(T.t >= q[i]) & (T.t < q[i + 1])].r.mean() for i in range(4)]
        rows.append(dict(tk=tk[:3], cfg=name, n=S["n"], win=S["win"], avgR=S["avgR"], tot=S["tot"], mdd=S["mdd"], q1=qs[0], q2=qs[1], q3=qs[2], q4=qs[3]))
R = pd.DataFrame(rows); print(R.round(3).to_string(index=False))
print(R.groupby("cfg").agg(n=("n", "sum"), avgR=("avgR", "mean"), pos=("avgR", lambda x: (x > 0).sum())).round(3))
