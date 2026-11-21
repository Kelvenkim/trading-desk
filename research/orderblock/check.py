import numpy as np, pandas as pd, sys
from ob import *
iv = sys.argv[1] if len(sys.argv) > 1 else "1h"
P = dict(W=48, hold=72 if iv == "1h" else 96, K=2.0, need=("gap", "sweep", "fvg"), stop_rule=1, tp="half")
allT = []
for tk in ["BTC-USD", "ETH-USD", "SOL-USD"]:
    d = load(tk, iv); obs = find_obs(d, P); T = simulate(d, obs, P); T["tk"] = tk[:3]; allT.append(T)
    # 무작위 기준: 같은 개수, 무작위 봉에서 직전 2캔들 범위를 OB처럼
    rs = []
    for seed in range(20):
        rng = np.random.default_rng(seed); h, l = d.high.values, d.low.values
        fake = []
        for i in sorted(rng.choice(np.arange(30, len(d) - 3), size=len(obs), replace=False)):
            s = 1 if rng.random() < .5 else -1
            fake.append(dict(i=i, side=s, entry=h[i-1] if s > 0 else l[i-1], stop=min(l[i-1], l[i]) if s > 0 else max(h[i-1], h[i]), k=2, gap=1, disp=1, sweep=1, fvg=1))
        Tr = simulate(d, fake, {**P, "need": ()}); rs.append(Tr.r.mean())
    print(tk, stats(T), "무작위 평균R", round(np.mean(rs), 3), "범위", round(min(rs), 3), round(max(rs), 3))
A = pd.concat(allT)
print("\n전체", stats(A)); print(A.why.value_counts()); print("평균 손절 거리 %", round(A.risk.mean() * 100, 2))
print(A.groupby("k").r.agg(["count", "mean"])); print(A.groupby("side").r.agg(["count", "mean"]))
print("수수료 0.02% 가정:")
for tk in ["BTC-USD", "ETH-USD", "SOL-USD"]:
    d = load(tk, iv); T = simulate(d, find_obs(d, P), {**P, "cost": 0.0002}); print(tk, round(T.r.mean(), 3), len(T))
