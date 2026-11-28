"""추세선 반대 거래를 '빼지 말고 다르게 관리' — 같은 방향은 그대로(반대 CHoCH 청산)
A0 그대로 / A1 반대 방향은 1.5R 익절 / A2 반대 방향은 2R 익절 / A3 반대 방향은 +1R 가면 손절을 본전으로 / A4 모든 거래 +1R에 본전
상위4 + 검증6, 거래당 1%"""
import numpy as np, pandas as pd, bos_test as B
def run(syms, mode):
    out = []
    for sym in syms:
        d = B.load(sym, "1h").iloc[:-1]; S = B.structure(d)
        o, h, l, c, ev, atr = S["o"], S["h"], S["l"], S["c"], S["ev"], S["atr"]
        ema = d.close.ewm(span=200, adjust=False).mean().values
        n, busy = len(c), -1
        for i, s, _ in B.signals(S, "S4"):
            if i + 1 >= n or i < busy: continue
            k = i + 1; e = o[k]; st = S["lastL"][i] if s == 1 else S["lastH"][i]
            if np.isnan(st) or (e - st) * s < 0.3 * atr[i]: continue
            risk = (e - st) * s; agree = np.sign(c[i] - ema[i]) == s
            tp = {"A1": 1.5, "A2": 2.0}.get(mode) if not agree else None
            be = (mode == "A3" and not agree) or mode == "A4"
            x = None
            for j in range(k, min(n, k + B.MAXH)):
                if (s == 1 and l[j] <= st) or (s == -1 and h[j] >= st): x = st; break
                if tp and ((h[j] - e) * s / risk >= tp if s == 1 else (e - l[j]) / risk >= tp): x = e + s * tp * risk; break
                if j > k and ev[j] == -2 * s: x = c[j]; break
                if be and ((h[j] - e) if s == 1 else (e - l[j])) >= risk: st = e if (st - e) * s < 0 else st
            if x is None: x = c[j]
            out.append(dict(t=S["t"][k], r=(x - e) * s / risk - 2 * B.COST * e / risk, agree=agree, sym=sym)); busy = j + 1
    return pd.DataFrame(out).sort_values("t")
def money(T, f=.01):
    e = 1e6; pk = e; mdd = 0
    for r in T.r: e *= 1 + f * r; pk = max(pk, e); mdd = min(mdd, e / pk - 1)
    m = T.set_index("t").r.resample("MS").sum()
    return f"{e/1e4:,.0f}만원", f"{mdd:.0%}", f"{(m<0).sum()}/{len(m)}", round(m.iloc[-1], 1)
rows = []
for name, syms in [("상위4", ["BTC", "ETH", "XRP", "BNB"]), ("검증6", ["SOL", "ADA", "DOGE", "LINK", "LTC", "TRX"])]:
    for mode, lab in [("A0", "그대로"), ("FILTER", "반대 방향 빼기"), ("A1", "반대 방향만 1.5R 익절"), ("A2", "반대 방향만 2R 익절"),
                      ("A3", "반대 방향만 +1R에 본전"), ("A4", "전부 +1R에 본전")]:
        T = run(syms, "A0" if mode == "FILTER" else mode)
        if mode == "FILTER": T = T[T.agree]
        fin, mdd, lm, nov = money(T)
        ag = T[~T.agree].r
        rows.append(dict(코인=name, 방법=lab, 거래=len(T), 거래당R=round(T.r.mean(), 2), 반대방향거래당R=round(ag.mean(), 2) if len(ag) else None,
                         **{"100만원→": fin, "최대낙폭": mdd, "지는달": lm, "11월R": nov}))
print(pd.DataFrame(rows).to_string(index=False))
