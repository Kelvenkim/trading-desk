"""미국장 → 다음 날 한국장 (11/23 형 아이디어: 미국이 크게 빠지면 다음 날 한국도 영향 — 이걸로 매매하면?)
코스피(^KS11)·코스닥(^KQ11) 일봉 2010~. 미국 하루 등락(S&P500) 구간별로 다음 한국 거래일:
  갭 = 한국 시가 / 전날 한국 종가 (미국 영향이 '시가'에 바로 반영되는 부분 — 이건 장 열리기 전이라 못 먹음)
  장중 = 한국 종가 / 한국 시가 (시가에 사서 종가에 파는 것 — 실제로 할 수 있는 부분)
  다음 날까지 = 다음 날 종가 / 시가"""
import numpy as np, pandas as pd, yfinance as yf

def get(t):
    d = yf.Ticker(t).history(period="max", interval="1d").dropna(); d.index = d.index.tz_localize(None).normalize()
    return d[d.index >= "2010-01-01"]

sp = get("^GSPC"); spr = sp.Close.pct_change()
for kt, nm in (("^KS11", "코스피"), ("^KQ11", "코스닥")):
    k = get(kt)
    gap = k.Open / k.Close.shift() - 1; intra = k.Close / k.Open - 1; two = k.Close.shift(-1) / k.Open - 1
    rows = []
    for d in k.index:
        prev = spr[spr.index < d]
        if not len(prev): continue
        rows.append((d, prev.iloc[-1], gap[d], intra[d], two[d]))
    T = pd.DataFrame(rows, columns=["d", "us", "gap", "intra", "two"]).dropna()
    print(f"\n== {nm} {T.d.min():%Y}~{T.d.max():%Y} · {len(T)}일 · 미국 등락과 상관: 갭 {T.us.corr(T.gap):.2f} / 장중 {T.us.corr(T.intra):.2f}")
    bins = [-1, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03, 1]; labs = ["−3%↓", "−3~−2%", "−2~−1%", "±1%", "+1~+2%", "+2~+3%", "+3%↑"]
    T["b"] = pd.cut(T.us, bins, labels=labs)
    g = T.groupby("b", observed=True).agg(n=("gap", "size"), gap=("gap", "mean"), intra=("intra", "mean"), up=("intra", lambda x: (x > 0).mean()), two=("two", "mean"))
    print((g.assign(gap=g.gap * 100, intra=g.intra * 100, two=g.two * 100, up=g.up * 100)).round(2).to_string())
    for lab, m in (("미국 −2%↓ 다음 날 시가 매수→종가", T.us <= -0.02), ("미국 +2%↑ 다음 날 시가 매수→종가", T.us >= 0.02)):
        x = T[m].intra - 0.0025                       # 왕복 비용 0.25% (거래세 포함 대략)
        h = T.d.min() + (T.d.max() - T.d.min()) / 2
        print(f"  {lab}: {m.sum()}번 · 비용 뺀 평균 {x.mean() * 100:+.2f}% · 이긴 비율 {(x > 0).mean():.0%} · 앞/뒤 절반 {x[T[m].d < h].mean() * 100:+.2f}/{x[T[m].d >= h].mean() * 100:+.2f}%")
