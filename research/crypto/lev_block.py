"""코인 10배 '추적 손절 뒤 같은 방향 재진입 금지' 규칙이 도움이 됐나 (11/22 형 질문: 안 쉬었으면?)
BTC 일봉, 50일선 위 롱·아래 숏, 노출 = min(5, 1.2/20일 변동성), 추적 손절 7%(최고·최저점 대비, 일봉 고저가), 비용 한쪽 0.05% + 펀딩 하루 0.01%
비교: ① 지금 규칙(신호 바뀔 때까지 쉼) ② 안 쉼(다음 날 종가에 같은 방향 바로 재진입) ③ 손절 뒤 5일 쉬고 재진입"""
import sys, numpy as np, pandas as pd, yfinance as yf
d = yf.Ticker("BTC-USD").history(start="2017-06-01").dropna(); c, h, l = d.Close.values, d.High.values, d.Low.values; idx = d.index
m50 = pd.Series(c).rolling(50).mean().values
vol = pd.Series(c).pct_change().rolling(20).std().values * np.sqrt(365)
def sim(mode, start="2018-01-01"):
    eq = 1.0; pos = 0; E = 0; ext = None; block = 0; wait = 0; curve = []; n = 0; stops = 0
    i0 = np.searchsorted(idx, pd.Timestamp(start, tz=idx.tz))
    for i in range(i0, len(c)):
        if pos:                                                   # 오늘 고저가로 추적 손절 확인
            stop = ext * (1 - pos * 0.07)
            hit = (pos > 0 and l[i] <= stop) or (pos < 0 and h[i] >= stop)
            px = stop if hit else c[i]
            eq *= 1 + pos * E * (px / c[i - 1] - 1) - E * 0.0001
            if hit:
                eq *= 1 - E * 0.0005; stops += 1
                block, wait = pos, 5; pos = 0; curve.append(eq); continue
            ext = max(ext, h[i]) if pos > 0 else min(ext, l[i])
        want = 1 if c[i] > m50[i] else -1
        if block and want != block: block = 0
        if wait: wait -= 1
        if pos and want != pos:
            eq *= 1 - E * 0.0005; pos = 0
        if not pos:
            blocked = (mode == "rule" and block == want) or (mode == "5d" and block == want and wait > 0)
            if not blocked:
                pos = want; E = min(5, 1.2 / vol[i]); ext = c[i]; eq *= 1 - E * 0.0005; n += 1
                if mode != "rule": block = 0
        curve.append(eq)
    s = pd.Series(curve, index=idx[i0:i0 + len(curve)]); yrs = (s.index[-1] - s.index[0]).days / 365.25
    yr = s.resample("YE").last().pct_change(); yr.iloc[0] = s.resample("YE").last().iloc[0] - 1
    return s.iloc[-1], s.iloc[-1] ** (1 / yrs) - 1, (s / s.cummax() - 1).min(), n, stops, yr
for start in ("2018-01-01", "2022-01-01"):
    print(f"\n{start}부터")
    for mode, nm in [("rule", "① 지금 규칙 (신호 바뀔 때까지 쉼)"), ("none", "② 안 쉬고 바로 재진입"), ("5d", "③ 손절 뒤 5일 쉬고 재진입")]:
        fin, cagr, mdd, n, st, yr = sim(mode, start)
        print(f"  {nm:<28} 1달러 → {fin:7.2f}배 · 연 {cagr:+.0%} · 최대 낙폭 {mdd:.0%} · 진입 {n}번 · 추적 손절 {st}번 · 마이너스 해 {int((yr < 0).sum())}/{len(yr)}")
