"""진입 보강 후보: 큰 시간봉(4시간·일봉) 추세와 같은 방향일 때만 — 진입 직후 움직임이 나아지는지"""
import numpy as np, pandas as pd, bos_test as B, diag as D
def trend_series(d1h, rule):
    d = d1h.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    S = B.structure(d)
    tr = pd.Series(np.sign(S["ev"]).astype(float), index=d.index).replace(0, np.nan).ffill()
    # 큰 봉은 마감 뒤에야 알 수 있음 → 한 칸 밀어서 1시간봉에 붙임 (미래 정보 차단)
    tr.index = tr.index + pd.Timedelta(rule)
    return tr.reindex(d1h.index, method="ffill").fillna(0).values
rows = []
for kind in ("S3", "S2", "RND"):
    R = []
    for sym in B.H1:
        d = B.load(sym, "1h"); S = D.SS[sym]
        t4, td = trend_series(d, "4h"), trend_series(d, "1D")
        busy = -1
        for i, s in D.entries(S, kind):
            if i < busy: continue
            t = D.trade(S, i, s, "R3")
            if t:
                t.update(sym=sym, a4=t4[i] == s, ad=td[i] == s); R.append(t); busy = t["j"] + 1
    T = pd.DataFrame(R)
    for name, m in [("전체", T.r == T.r), ("4h 같은 방향", T.a4), ("4h 반대", ~T.a4), ("일봉 같은 방향", T.ad), ("4h+일봉 둘 다 같은", T.a4 & T.ad)]:
        X = T[m]; top = X.r.nlargest(max(1, int(len(X) * .05))).index
        rows.append(dict(entry=kind, filt=name, n=len(X), reach_1R=round((X.mfe >= 1).mean(), 3), reach_2R=round((X.mfe >= 2).mean(), 3),
                         stopped=round(X.stopped.mean(), 3), avgR=round(X.r.mean(), 3), no_top5=round(X.drop(top).r.mean(), 3),
                         coins_pos=sum(g.r.mean() > 0 for _, g in X.groupby("sym"))))
print(pd.DataFrame(rows).to_string(index=False))
