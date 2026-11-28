import numpy as np, pandas as pd, bos_test as B
rng = np.random.default_rng(0)
def run(tf, syms, strat, ex, K=3, flip=False):
    B.K = K; out = []
    for s in syms:
        S = B.structure(B.load(s, tf))
        if flip:   # 같은 시점·같은 청산 규칙, 방향만 무작위 → 청산 규칙 자체의 힘 확인
            sig = B.signals(S, strat)
            orig = B.signals
            B.signals = lambda S_, st_, sig=sig: [(i, int(rng.choice([1, -1])), h) for i, _, h in sig]
            # 손절은 방향 따라 lastL/lastH 가 쓰이므로 그대로 의미 있음
            T = B.simulate(S, strat, ex); B.signals = orig
        else:
            T = B.simulate(S, strat, ex)
        if len(T): out.append(T.assign(sym=s))
    return pd.concat(out)
for tf, syms in [("1h", B.H1), ("1d", B.D1)]:
    for strat, ex in [("S3", "A"), ("S3", "B"), ("S4", "B"), ("S2", "B")]:
        T = run(tf, syms, strat, ex)
        L, S_ = T[T.side == 1].r, T[T.side == -1].r
        R = [run(tf, syms, strat, ex, flip=True).r.mean() for _ in range(3)]
        ks = {k: round(run(tf, syms, strat, ex, K=k).r.mean(), 3) for k in (2, 5)}
        yrs = T.groupby(T.t.dt.year).r.mean().round(2).to_dict() if tf == "1d" else T.groupby(T.t.dt.to_period("Q")).r.mean().round(2).to_dict()
        print(f"{tf} {strat}{ex} all {T.r.mean():+.3f} | long {L.mean():+.3f} (n{len(L)}) short {S_.mean():+.3f} (n{len(S_)}) | 무작위방향 {np.mean(R):+.3f} | K2 {ks[2]:+} K5 {ks[5]:+}")
        print("    기간별:", yrs)
