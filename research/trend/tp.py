"""코인 10배 단타(추세 눌림) 익절 시험 (11/22 형: 손절만 정해져 있고 익절이 없어 손절이 잦은 것 같다)
지금: 손절 ATR×1.5 + 추적 손절 ATR×5 (익절 없음). 비교: 고정 익절 1·1.5·2·3R / 1R에서 절반 익절+본전 / 1R 오면 본전만"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import coach as CO, formula_rules as FR

def trend(d, F, sm=1.5, tr=5.0, mx=96, tp=None, half=False, be=False):
    o, h, l, c = (d[k].values for k in ("open", "high", "low", "close")); A = F["A"]; N = len(c)
    e = lambda n: d.close.ewm(span=n, adjust=False).mean().values
    e20, e50, e200 = e(20), e(50), e(200)
    dl = d.close.diff(); u = dl.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); w = (-dl.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    R = (100 - 100 / (1 + u / w)).values; out = []; k = 210
    while k < N - 1:
        j = k - 1; up = e50[j] > e200[j] and c[j] > e200[j]; dn = e50[j] < e200[j] and c[j] < e200[j]; s = 0
        if up and l[j] <= e20[j] and c[j] > o[j] and R[j-1] < 50: s = 1
        elif dn and h[j] >= e20[j] and c[j] < o[j] and R[j-1] > 50: s = -1
        if not s or F["volhi"][j]: k += 1; continue
        en = o[k]; risk = sm * A[j]; stop = en - s * risk; best = en; legs = []; rem = 1.0; moved = False; q = k
        while q < min(N, k + mx):
            if (s > 0 and l[q] <= stop) or (s < 0 and h[q] >= stop):
                legs.append((rem, min(o[q], stop) if s > 0 else max(o[q], stop))); rem = 0; break
            fav = (h[q] - en) * s if s > 0 else (en - l[q])
            if half and not moved and fav >= risk:
                legs.append((0.5, en + s * risk)); rem = 0.5; moved = True; stop = en
            elif be and not moved and fav >= risk:
                moved = True; stop = en
            if tp and fav >= tp * risk:
                legs.append((rem, en + s * tp * risk)); rem = 0; break
            best = max(best, h[q]) if s > 0 else min(best, l[q]); t_ = best - s * tr * A[q]
            if (s > 0 and t_ > stop) or (s < 0 and t_ < stop): stop = t_
            q += 1
        if rem > 0: q = min(N - 1, q); legs.append((rem, c[q]))
        net = sum(wt * s * (px / en - 1) for wt, px in legs) - 2 * CO.FEE
        out.append(dict(t=d.index[k], r=net / (risk / en))); k = q + 1
    return pd.DataFrame(out)

B = {s: CO.bars(s) for s in CO.SYMS}; F = {s: CO.common(d) for s, d in B.items()}
for nm, kw in [("지금 (익절 없음, 추적 ATR×5)", {}), ("고정 익절 1R", dict(tp=1)), ("고정 익절 1.5R", dict(tp=1.5)), ("고정 익절 2R", dict(tp=2)), ("고정 익절 3R", dict(tp=3)),
               ("1R에서 절반 익절 + 본전", dict(half=True)), ("1R 오면 본전 손절만", dict(be=True)), ("절반 익절 + 나머지 3R 익절", dict(half=True, tp=3))]:
    T = pd.concat([trend(d, F[s], **kw) for s, d in B.items()]); a = CO.acct(T)
    mid = T.t.min() + (T.t.max() - T.t.min()) / 2
    print(f"{nm:<26} {len(T)}번 승률 {(T.r > 0).mean():.0%} · 손절(-0.9R 이하) {(T.r <= -0.9).mean():.0%} · 평균 {T.r.mean():+.2f}R · 합계 {a[0]:+.0f}R · 최대 낙폭 {a[1]:.0f}R · 수익÷낙폭 {a[2]:.1f} · 앞/뒤 1년 {T[T.t < mid].r.mean():+.2f}/{T[T.t >= mid].r.mean():+.2f}")
