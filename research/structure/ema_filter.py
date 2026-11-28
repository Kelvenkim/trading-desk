"""BOS 공식 + 1시간봉 200EMA 필터: 수익·낙폭·월별 비교 (상위4 + 검증 6코인)"""
import numpy as np, pandas as pd, bos_test as B, sys
def trades(syms):
    out = []
    for sym in syms:
        d = B.load(sym, "1h").iloc[:-1]; S = B.structure(d)
        T = B.simulate(S, "S4", "B")
        ema = d.close.ewm(span=200, adjust=False).mean()
        # 진입 봉(t) 바로 전 봉 마감 기준 — 신호 봉 종가 vs 200EMA
        pos = d.index.get_indexer(T.t) - 1
        T["agree"] = np.sign(d.close.values[pos] - ema.values[pos]) == T.side
        out.append(T.assign(sym=sym))
    return pd.concat(out).sort_values("t").reset_index(drop=True)
def stats(T, risk):
    e = 1e6; pk = e; mdd = 0; path = []
    for r in T.r: e *= 1 + risk * r; pk = max(pk, e); mdd = min(mdd, e / pk - 1); path.append(e)
    m = T.set_index("t").r.resample("MS").sum()
    streak = cur = 0
    for r in T.r:
        cur = cur + 1 if r < 0 else 0; streak = max(streak, cur)
    return dict(거래=len(T), 합계R=round(T.r.sum(), 1), 거래당R=round(T.r.mean(), 2), 최종=f"{e/1e4:,.0f}만원", 최대낙폭=f"{mdd:.0%}",
                지는달=f"{(m < 0).sum()}/{len(m)}", 제일나쁜달=f"{m.min():+.1f}R", 최장연패=streak), m
for name, syms in [("상위 4개", ["BTC", "ETH", "XRP", "BNB"]), ("검증 6개", ["SOL", "ADA", "DOGE", "LINK", "LTC", "TRX"])]:
    T = trades(syms); F = T[T.agree]
    print(f"\n===== {name} =====")
    rows = []
    for risk in (.005, .01):
        a, ma = stats(T, risk); b, mb = stats(F, risk)
        rows += [dict(버전="필터 없음", 위험=f"{risk:.1%}", **a), dict(버전="200EMA 필터", 위험=f"{risk:.1%}", **b)]
    print(pd.DataFrame(rows).to_string(index=False))
    M = pd.DataFrame({"필터없음": ma, "200EMA": mb}).fillna(0).round(1)
    M.index = M.index.strftime("%y.%m"); print(M.T.to_string())
    if name == "상위 4개": M.to_csv("ema_monthly_top4.csv")
