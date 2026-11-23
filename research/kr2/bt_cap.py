"""한국 주식 계좌 규칙(주도주 돌파)을 '시총 300억~10조' 종목(형 기준)으로 다시 시험 — 네이버 일봉 2015~ (지금 시총 기준 · 생존 편향)
research/kr/bt.py(시총 상위 300종목)와 같은 엔진(research/oneil/desk_bt.py)"""
import json, sys, types
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf
ROOT = Path(__file__).resolve().parents[2]; H = Path(__file__).parent / "data"
U = json.loads((H / "universe.json").read_text())
LO, HI = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (300, 100000)      # 억 원
U = [u for u in U if LO <= u["cap"] <= HI]
cols = {}
for s in U:
    f = H / f"day_{s['code']}.json"
    if f.exists():
        d = pd.DataFrame(json.loads(f.read_text()), columns=["d", "o", "h", "l", "c", "v", "fr"]).set_index("d"); d.index = pd.to_datetime(d.index); cols[s["code"]] = d
W = lambda k: pd.DataFrame({c: d[k].where(d[k] > 0) for c, d in cols.items()}).sort_index()
O, Hh, L, C, V = W("o"), W("h"), W("l"), W("c"), W("v")
r = C.pct_change(fill_method=None); badday = r.abs() > 0.305                      # 액면분할 등 자료 오류 → 그 종목 그날부터 20일 신호 제외
C = C.ffill()
ks = yf.Ticker("^KS11").history(period="max")["Close"]; ks.index = ks.index.tz_localize(None).normalize()
spx = ks.reindex(C.index).ffill()
hi252 = Hh.rolling(252, min_periods=200).max().shift(1)
v50 = V.rolling(50).mean().shift(1)
rsraw = 0.4 * C / C.shift(63) + 0.2 * C / C.shift(126) + 0.2 * C / C.shift(189) + 0.2 * C / C.shift(252)
R = types.ModuleType("rules")
R.__dict__.update(O=O, H=Hh.where(~badday.rolling(20, min_periods=1).max().astype(bool)), L=L, C=C, V=V, spx=spx, RS=rsraw.rank(axis=1, pct=True) * 99, ma50=C.rolling(50).mean(),
                  base=C / L.rolling(504, min_periods=300).min(), v50=v50, hi252=hi252, tick=list(C.columns))
sys.modules["rules"] = R
src = (ROOT / "research/oneil/desk_bt.py").read_text().split('if __name__ == "__main__":')[0]
src = src.replace("x *= 0.9995; cash += p[\"sh\"] * x * 0.9995", "x *= 0.9995; cash += p[\"sh\"] * x * (0.9995 - 0.002)")
src = src.replace("dv = (C * V).rolling(20).mean().values", "dv = (C * V).rolling(20).mean().values / 1400")
src = src.replace("ok = (dv[i] >= 2e7) & (cv[i] >= 5)", "ok = (dv[i] >= 2e6) & (cv[i] >= 1000)")
g = {}; exec(src, g)
s = spx.iloc[260:]; yrs = (s.index[-1] - s.index[0]).days / 365.25
print(f"시총 {LO:,.0f}억~{HI:,.0f}억 {C.shape[1]}종목 · {C.index[260]:%Y-%m-%d} ~ {C.index[-1]:%Y-%m-%d}")
print(f"{'코스피 그냥 보유':<26} 연 {(s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1:+.1%} · 최대 낙폭 {(s / s.cummax() - 1).min():.1%}")
for k, nm in [("B", "주도주 돌파 (필터 없음)"), ("B2", "주도주 돌파 + 코스피 200일선 위만")]:
    E_, T_ = g["run"](k); g["summary"](nm, E_, T_)
