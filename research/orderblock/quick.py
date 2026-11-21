import sys, numpy as np, pandas as pd
from ob import *
for iv in sys.argv[1:]:
    rows = []
    for tk in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        d = load(tk, iv); Z = htf_zones(load(tk, "1h"), {})
        obs = find_obs(d, {"K": 2.0}); obs2 = [o for o in obs if o["k"] == 2]
        half = d.index[0] + (d.index[-1] - d.index[0]) / 2
        for name, O, need, mtf, cost in [("필터 없음", obs, (), False, .0005), ("3필터", obs, ("gap", "sweep", "fvg"), False, .0005),
                                         ("3필터·2캔들", obs2, ("gap", "sweep", "fvg"), False, .0005), ("3필터·2캔들·1h겹침", obs2, ("gap", "sweep", "fvg"), True, .0005),
                                         ("2필터(갭+흡수)·2캔들", obs2, ("gap", "sweep"), False, .0005), ("3필터·2캔들 지정가0.02%", obs2, ("gap", "sweep", "fvg"), False, .0002)]:
            T = simulate(d, O, dict(W=48, hold=96, K=2.0, need=need, stop_rule=1, tp="half", mtf=mtf, cost=cost), Z)
            S = stats(T)
            a = T[T.t < half].r.mean() if len(T) else np.nan; b = T[T.t >= half].r.mean() if len(T) else np.nan
            rows.append(dict(iv=iv, tk=tk[:3], cfg=name, n=S.get("n"), win=S.get("win"), avgR=S.get("avgR"), a=a, b=b))
    R = pd.DataFrame(rows)
    print(f"\n===== {iv}"); print(R.round(3).to_string(index=False))
    print(R.groupby("cfg").agg(n=("n", "sum"), avgR=("avgR", "mean"), pos=("avgR", lambda x: (x > 0).sum())).round(3))
