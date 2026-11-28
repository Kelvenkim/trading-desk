"""상위 4개 코인만 (11/28 형): 시가총액 상위 — 스테이블코인 제외 BTC·ETH·XRP·BNB (SOL 넣은 버전도 참고)
bos_test 의 전략·청산 그대로 + 진단(무작위 진입 비교, +1R 도달, 상위 5% 빼기)"""
import numpy as np, pandas as pd, bos_test as B, diag as D
rng = np.random.default_rng(2)
SETS = {"상위4 (BTC·ETH·XRP·BNB)": ["BTC", "ETH", "XRP", "BNB"], "BTC·ETH·SOL·XRP": ["BTC", "ETH", "SOL", "XRP"]}
rows = []
for name, syms in SETS.items():
    for tf in ("1h", "4h", "1d"):
        SS = {s: B.structure(B.load(s, tf)) for s in syms}
        for strat, ex in [("S1", "B"), ("S2", "A"), ("S2", "B"), ("S3", "A"), ("S3", "B"), ("S4", "A"), ("S4", "B")]:
            T = pd.concat([B.simulate(S, strat, ex).assign(sym=s) for s, S in SS.items()]).sort_values("t")
            cut = T.t.min() + (T.t.max() - T.t.min()) / 2
            top = T.r.nlargest(max(1, int(len(T) * .05))).index
            rows.append(dict(set=name, tf=tf, strat=strat, exit=ex, n=len(T), win=round((T.r > 0).mean(), 2), avgR=round(T.r.mean(), 3),
                             first=round(T[T.t < cut].r.mean(), 3), second=round(T[T.t >= cut].r.mean(), 3),
                             no_top5=round(T.drop(top).r.mean(), 3), long=round(T[T.side == 1].r.mean(), 3), short=round(T[T.side == -1].r.mean(), 3),
                             coins="/".join(f"{s}{g.r.mean():+.2f}" for s, g in T.groupby("sym"))))
        # 진단: +1R 도달 — BOS 진입 vs 무작위 (3R 익절 기준)
        for kind in ("S3", "S4", "RND"):
            R = []
            for s, S in SS.items():
                busy = -1
                for i, sd in D.entries(S, kind):
                    if i < busy: continue
                    t = D.trade(S, i, sd, "R3")
                    if t: R.append(t); busy = t["j"] + 1
            X = pd.DataFrame(R)
            rows.append(dict(set=name, tf=tf, strat="진단-" + kind, exit="R3", n=len(X), avgR=round(X.r.mean(), 3),
                             win=round((X.mfe >= 1).mean(), 2)))   # 진단 줄의 win = +1R 도달 비율
R = pd.DataFrame(rows); R.to_csv("top4_result.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(R.to_string(index=False))
