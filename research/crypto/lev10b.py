"""10배에서 '손절 7%' = 계좌(증거금) −7% = 가격 0.7% 반대로 가면 손절 (11/22 형 설명)
BTC 1시간봉 2년 · 방향 일봉 50일선 · 노출 계좌의 10배 · 비용 매매 0.05%×노출 · 재진입: 다음 1시간봉 / 다음 일봉 마감"""
from lev10 import *
def sim2(stop_acct=0.07, trail=False, reenter="hour", E0=10.0):
    sp = stop_acct / E0
    eq, pos, e, ext, n, stops, last_day = 1.0, 0, 0, 0, 0, 0, None; curve = []
    for i in range(1, len(c)):
        w = want[i]; day = h.index[i].normalize()
        if pos:
            ref = ext if trail else e
            stop = ref * (1 - pos * sp); adv = lo[i] if pos > 0 else hi[i]
            if (pos > 0 and adv <= stop) or (pos < 0 and adv >= stop):
                px = min(o[i], stop) if pos > 0 else max(o[i], stop)
                eq *= max(0, 1 + pos * E0 * (px / c[i - 1] - 1)) * (1 - E0 * 0.0005); pos = 0; stops += 1; last_day = day
            else:
                eq *= max(0, 1 + pos * E0 * (c[i] / c[i - 1] - 1))
                ext = max(ext, hi[i]) if pos > 0 else min(ext, lo[i])
                if np.isfinite(w) and w != pos: eq *= 1 - E0 * 0.0005; pos = 0
        if eq <= 0.01: curve.append(eq); break
        if not pos and np.isfinite(w) and w != 0 and (reenter == "hour" or last_day is None or day > last_day):
            pos, e, ext = int(w), o[i], o[i]; eq *= 1 - E0 * 0.0005; n += 1
        curve.append(eq)
    s = pd.Series(curve); return s.iloc[-1], (s / s.cummax() - 1).min(), n, stops, len(curve)
print("손절(계좌 기준) · 방식 · 재진입      → 최종(시작 1) · 최대 낙폭 · 진입 · 손절 · 버틴 시간")
for sa in (0.07, 0.15, 0.3):
    for tr in (False, True):
        for re in ("hour", "day"):
            f, m, n, s, L = sim2(sa, tr, re)
            print(f"  −{sa:.0%} ({sa / 10:.2%} 가격) · {'추적' if tr else '고정'} · {'1시간 뒤' if re == 'hour' else '다음 날'}   {f:7.3f} · {m:5.0%} · {n:>4} · {s:>4} · {L / 24:5.0f}일")
