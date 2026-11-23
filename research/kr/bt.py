"""한국 주식에 미국 주식 계좌 규칙 그대로 쓰면? (11/23 형: 미국·한국 같이 운영) — research/oneil/desk_bt.py 'A'를 한국 300종목(data/rank/universe.json)으로
지금 있는 종목 = 생존 편향(실제보다 좋게 나옴). 비용: 한쪽 0.05%+0.05% + 팔 때 거래세 0.2%. 기준 지수 = 코스피"""
import json, sys, types
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf
ROOT = Path(__file__).resolve().parents[2]; H = Path(__file__).parent / "data"
U = json.loads((ROOT / "data/rank/universe.json").read_text())
tk = [c + (".KS" if m == "KOSPI" else ".KQ") for c, n, m in U]
f = H / "px.pkl"
if f.exists():
    P = pd.read_pickle(f)
else:
    P = yf.download(tk + ["^KS11"], start="2014-01-01", auto_adjust=True, group_by="ticker", progress=False, threads=True); P.to_pickle(f)
W = lambda k: pd.DataFrame({t: P[t][k] for t in tk if t in P.columns.get_level_values(0)}).dropna(how="all", axis=1)
O, Hh, L, C, V = W("Open"), W("High"), W("Low"), W("Close"), W("Volume")
for X in (O, Hh, L, V):
    X.drop(columns=[c for c in X if c not in C], inplace=True)
C = C.ffill()        # 시세가 빠진 날 보유 종목 가치가 0으로 빠지는 오류 방지 (처음 돌렸을 때 최대 낙폭 −80%대가 이것 때문이었음)
spx = P["^KS11"]["Close"].reindex(C.index).ffill()
hi252 = Hh.rolling(252, min_periods=200).max().shift(1)
v50 = V.rolling(50).mean().shift(1)
rsraw = 0.4 * C / C.shift(63) + 0.2 * C / C.shift(126) + 0.2 * C / C.shift(189) + 0.2 * C / C.shift(252)
R = types.ModuleType("rules")
R.__dict__.update(O=O, H=Hh, L=L, C=C, V=V, spx=spx, RS=rsraw.rank(axis=1, pct=True) * 99, ma50=C.rolling(50).mean(),
                  base=C / L.rolling(504, min_periods=300).min(), v50=v50, hi252=hi252, tick=list(C.columns))
sys.modules["rules"] = R
src = (ROOT / "research/oneil/desk_bt.py").read_text().split('if __name__ == "__main__":')[0]
src = src.replace("x *= 0.9995; cash += p[\"sh\"] * x * 0.9995", "x *= 0.9995; cash += p[\"sh\"] * x * (0.9995 - 0.002)")
src = src.replace("dv = (C * V).rolling(20).mean().values", "dv = (C * V).rolling(20).mean().values / 1400")   # 원 → 달러 환산(거래대금 $2,000만 기준 그대로 쓰려고)
src = src.replace("ok = (dv[i] >= 2e7) & (cv[i] >= 5)", "ok = (dv[i] >= 2e6) & (cv[i] >= 1000)")         # 한국: 하루 거래대금 약 28억 원↑ · 1,000원↑
g = {}; exec(src, g)
s = spx.iloc[260:]; yrs = (s.index[-1] - s.index[0]).days / 365.25
print(f"기간 {C.index[260]:%Y-%m-%d} ~ {C.index[-1]:%Y-%m-%d} · {C.shape[1]}종목")
print(f"{'코스피 그냥 보유':<26} 연 {(s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1:+.1%} · 최대 낙폭 {(s / s.cummax() - 1).min():.1%}")
E1, T1 = g["run"]("A"); yr = g["summary"]("A 미국 규칙 그대로(한국)", E1, T1)
sy = spx.resample("YE").last().pct_change().dropna()
print((pd.DataFrame({"규칙": yr, "코스피": sy.reindex(yr.index)}) * 100).round(1).to_string())
for k, nm in [("C", "C A + 형 규칙 필터"), ("B", "B 주도주(신고점·거래량·RS80)"), ("B2", "B2 주도주 + 코스피 200일선 위만")]:
    E_, T_ = g["run"](k); g["summary"](nm, E_, T_)
