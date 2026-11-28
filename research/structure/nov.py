"""BOS 공식 (상위 4코인, 1h, S4+B) — 2026년 11월 진입분만 거래 목록"""
import numpy as np, pandas as pd, bos_test as B
rows = []
for sym in ["BTC", "ETH", "XRP", "BNB"]:
    d = B.load(sym, "1h").iloc[:-1]                      # 아직 안 끝난 마지막 봉 제외
    S = B.structure(d); o, h, l, c, ev, atr = S["o"], S["h"], S["l"], S["c"], S["ev"], S["atr"]
    n, busy = len(c), -1
    for i, s, _ in B.signals(S, "S4"):
        if i + 1 >= n or i < busy: continue
        k = i + 1; e = o[k]; st = S["lastL"][i] if s == 1 else S["lastH"][i]
        if np.isnan(st) or (e - st) * s < 0.3 * atr[i]: continue
        risk = (e - st) * s; x = None; why = "보유 중"
        for j in range(k, min(n, k + B.MAXH)):
            if (s == 1 and l[j] <= st) or (s == -1 and h[j] >= st): x, why = st, "손절"; break
            if j > k and ev[j] == -2 * s: x, why = c[j], "반대 CHoCH"; break
        else:
            if j == k + B.MAXH - 1: x, why = c[j], "200봉"
        busy = j + 1
        t_in = S["t"][k]
        if t_in < pd.Timestamp("2026-11-01", tz="Asia/Seoul"): continue
        xr = c[j] if x is None else x
        r = (xr - e) * s / risk - 2 * B.COST * e / risk
        rows.append(dict(코인=sym, 방향="매수" if s == 1 else "매도", 진입=t_in.tz_convert("Asia/Seoul").strftime("%m/%d %H시"),
                         진입가=round(e, 4 if e < 10 else 2), 손절가=round(st, 4 if e < 10 else 2), 손절폭=f"{risk / e:.1%}",
                         청산=S["t"][j].tz_convert("Asia/Seoul").strftime("%m/%d %H시"), 이유=why, R=round(r, 2), 보유=f"{j - k + 1}시간"))
T = pd.DataFrame(rows).sort_values("진입")
pd.set_option("display.width", 200); print(T.to_string(index=False))
done = T[T.이유 != "보유 중"]
print(f"\n끝난 거래 {len(done)}번 · 합계 {done.R.sum():+.2f}R · 평균 {done.R.mean():+.2f}R · 승 {int((done.R>0).sum())}/{len(done)}")
for risk in (.005, .01):
    e = 1e6
    for r in done.R: e *= 1 + risk * r
    print(f"100만원 · {risk:.1%}: {e:,.0f}원 ({e/1e6-1:+.1%})")
T.to_csv("nov_trades.csv", index=False)
