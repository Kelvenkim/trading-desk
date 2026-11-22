"""진짜 10배(계좌의 10배 노출) 시험 (11/22 형: 10배로 두고 피드백으로 손실 줄이기)
BTC 1시간봉 2년(봉 안 순서 문제 줄이려고 1시간봉) · 방향: 일봉 50일선(전날 마감 기준) · 진입 그 뒤 첫 1시간봉 시가
10배 격리: 진입가에서 −9.5% 불리하면 강제 청산(증거금 전부) · 비용: 매매 0.05%×노출, 펀딩 하루 0.01%×노출
변수: 추적 손절 폭, 계좌 낙폭 따라 노출 줄이기(피드백), 재진입은 바로(쉬지 않음)"""
import numpy as np, pandas as pd, yfinance as yf
h = yf.Ticker("BTC-USD").history(period="730d", interval="1h").dropna()
dd_ = yf.Ticker("BTC-USD").history(start="2024-06-01").dropna()
m50 = dd_.Close.rolling(50).mean()
sig = np.sign(dd_.Close - m50).shift(1)                    # 전날 마감 기준
sig.index = sig.index.tz_convert("UTC").normalize() if sig.index.tz else sig.index.tz_localize("UTC")
h.index = h.index.tz_convert("UTC")
want = h.index.normalize().map(lambda d: sig.get(d, np.nan)).values
o, hi, lo, c = h.Open.values, h.High.values, h.Low.values, h.Close.values

def sim(E0, trail, dd_steps=None, liq=0.095):
    eq, peak, pos, E, e, ext, n, liqn, stops = 1.0, 1.0, 0, E0, 0, 0, 0, 0, 0; curve = []
    for i in range(1, len(c)):
        w = want[i]
        if pos:
            stop = ext * (1 - pos * trail); lq = e * (1 - pos * liq)
            adv = lo[i] if pos > 0 else hi[i]
            hit_l = (pos > 0 and adv <= lq) or (pos < 0 and adv >= lq)
            hit_s = (pos > 0 and adv <= stop) or (pos < 0 and adv >= stop)
            if hit_s and (not hit_l or (pos > 0 and stop > lq) or (pos < 0 and stop < lq)):
                px = min(o[i], stop) if pos > 0 else max(o[i], stop)
                if (pos > 0 and px <= lq) or (pos < 0 and px >= lq): px = lq; liqn += 1
                eq *= max(0, 1 + pos * E * (px / c[i - 1] - 1)) * (1 - E * 0.0005); pos = 0; stops += 1
            elif hit_l:
                eq *= max(0, 1 - E * liq * 1.0 + pos * E * 0 ) if False else max(0, 1 + pos * E * (lq / c[i - 1] - 1)); pos = 0; liqn += 1
            else:
                eq *= max(0, 1 + pos * E * (c[i] / c[i - 1] - 1)) * (1 - E * 0.0001 / 24)
                ext = max(ext, hi[i]) if pos > 0 else min(ext, lo[i])
                if np.isfinite(w) and w != pos:
                    eq *= 1 - E * 0.0005; pos = 0
        if eq <= 0.01:
            curve.append(eq); break
        peak = max(peak, eq)
        if not pos and np.isfinite(w) and w != 0:
            E = E0
            if dd_steps:
                for lim, k in dd_steps:
                    if eq / peak - 1 <= lim: E = E0 * k
            pos, e, ext = int(w), o[i], o[i]; eq *= 1 - E * 0.0005; n += 1
        curve.append(eq)
    s = pd.Series(curve)
    return s.iloc[-1], (s / s.cummax() - 1).min(), n, stops, liqn

print(f"BTC 1시간봉 {h.index[0]:%Y-%m-%d} ~ {h.index[-1]:%Y-%m-%d} · 같은 기간 BTC {c[-1] / c[0] - 1:+.0%}\n")
print("노출 · 추적 손절            → 최종(시작 1) · 최대 낙폭 · 진입 · 손절 · 강제 청산")
for E0 in (2.3, 5, 10):
    for tr in (0.02, 0.03, 0.05, 0.07):
        f, m, n, s, l = sim(E0, tr)
        print(f"  {E0:>4}배 · {tr:.0%}                {f:7.2f} · {m:6.0%} · {n:>3} · {s:>3} · {l}")
print("\n10배 + 피드백(계좌가 최고점에서 −15%면 노출 절반, −30%면 ¼)")
for tr in (0.02, 0.03, 0.05):
    f, m, n, s, l = sim(10, tr, [(-0.15, 0.5), (-0.30, 0.25)])
    print(f"  10배 · {tr:.0%}                {f:7.2f} · {m:6.0%} · {n:>3} · {s:>3} · {l}")
