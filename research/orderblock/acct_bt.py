"""추세 눌림 계좌 단위 백테스트 (11/22): 2년 1시간봉, 1회 손실 1%, 노출 최대 10배, BTC·ETH·SOL 동시, 수수료 한쪽 0.05%
alt.py는 거래당 R만 봤음 → 여기서 계좌 수익·최대 낙폭·연속 손실·월별·앞/뒤 1년 나눠 확인"""
import numpy as np, pandas as pd
from ob import load, atr
from alt import signals

P = dict(r=50, sm=1.5, tr=5, mx=96); COST = 0.0005

def trades(d, sym):
    L, S = signals(d, "pull", P); o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values; A = atr(d); t = d.index
    out = []; i = 210; N = len(c)
    while i < N - 2:
        s = 1 if L[i] else -1 if S[i] else 0
        if not s: i += 1; continue
        e = o[i + 1]; risk = P["sm"] * A[i]; stop = e - s * risk; best = e; x = None; j = i + 1
        while j < min(N, i + 1 + P["mx"]):
            if (s > 0 and l[j] <= stop) or (s < 0 and h[j] >= stop):
                x = (min(o[j], stop) if s > 0 else max(o[j], stop)) if j > i + 1 else stop; break
            best = max(best, h[j]) if s > 0 else min(best, l[j]); tr = best - s * P["tr"] * A[j]
            stop = max(stop, tr) if s > 0 else min(stop, tr); j += 1
        if x is None: j = min(N - 1, j); x = c[j]
        out.append(dict(sym=sym, tin=t[i + 1], tout=t[j], pct=s * (x / e - 1) - 2 * COST, risk=risk / e)); i = j + 1
    return out

T = pd.DataFrame(sum([trades(load(s, "1h"), s[:3]) for s in ["BTC-USD", "ETH-USD", "SOL-USD"]], [])).sort_values("tin").reset_index(drop=True)
# 계좌: 진입 때 확정 자산 기준 크기, 정리 때 손익 반영
ev = sorted([(r.tin, 0, k) for k, r in T.iterrows()] + [(r.tout, 1, k) for k, r in T.iterrows()], key=lambda x: (x[0], -x[1]))
eq = 10000.0; size = {}; curve = []; expo_open = {}
for tm, typ, k in ev:
    r = T.loc[k]
    if typ == 0:
        size.setdefault(k, min(eq * 0.01 / r.risk, eq * 10))        # 1회 손실 1%, 노출 10배 한도
    else:
        size.setdefault(k, min(eq * 0.01 / r.risk, eq * 10))        # 진입 봉에서 바로 손절된 경우
        pnl = size[k] * r.pct; eq += pnl; T.loc[k, "acct"] = pnl / (eq - pnl); curve.append((tm, eq))
C = pd.Series([e for _, e in curve], index=[t for t, _ in curve])
mdd = (C / C.cummax() - 1).min()
w = (T.acct > 0).values; streak = mx = 0
for x in w: streak = 0 if x else streak + 1; mx = max(mx, streak)
print(f"기간 {T.tin.min():%Y-%m-%d} ~ {T.tout.max():%Y-%m-%d} · 거래 {len(T)}번 · 승률 {w.mean():.0%}")
print(f"계좌 $10,000 → ${C.iloc[-1]:,.0f} ({C.iloc[-1]/1e4-1:+.0%}) · 최대 낙폭 {mdd:.1%} · 최장 연속 손실 {mx}번")
print(f"거래당 평균 계좌 {T.acct.mean()*100:+.2f}% · 최악 한 번 {T.acct.min()*100:.2f}% · 최고 한 번 {T.acct.max()*100:+.2f}%")
print(f"10배 한도에 걸린 비율 {(0.01/T.risk > 10).mean():.0%}")
half = T.tin.min() + (T.tout.max() - T.tin.min()) / 2
for nm, X in [("앞 1년", T[T.tin < half]), ("뒤 1년", T[T.tin >= half])]:
    print(nm, f"거래 {len(X)} · 계좌 {(1 + X.acct).prod() - 1:+.0%} · 승률 {(X.acct > 0).mean():.0%}")
for s in ["BTC", "ETH", "SOL"]:
    X = T[T.sym == s]; print(s, f"거래 {len(X)} · 계좌 기여 {(1 + X.acct).prod() - 1:+.0%}")
M = C.resample("ME").last().ffill(); mr = M.pct_change().fillna(M.iloc[0] / 1e4 - 1)
print(f"월별: 플러스 {int((mr > 0).sum())}달 / 마이너스 {int((mr <= 0).sum())}달 · 최악의 달 {mr.min():+.1%} · 최고의 달 {mr.max():+.1%}")
# 수수료 0.1% (체결 미끄러짐 포함 비관)
print("비관(한쪽 0.1%):", f"거래당 R {((T.pct - 2*0.0005) / T.risk).mean():+.2f} (기본 {(T.pct / T.risk).mean():+.2f})")

def sim(T, risk):
    eq = 1e4; size = {}; C = []
    for tm, typ, k in ev:
        r = T.loc[k]; size.setdefault(k, min(eq * risk / r.risk, eq * 10))
        if typ: eq += size[k] * r.pct; C.append(eq)
    C = pd.Series(C); return C.iloc[-1] / 1e4 - 1, (C / C.cummax() - 1).min()
print("\n1회 손실 크기별 (2년):")
for rk in (0.01, 0.005, 0.0025):
    a, b = sim(T, rk); print(f"  {rk*100:.2f}% → 수익 {a:+.0%} · 최대 낙폭 {b:.1%}")
