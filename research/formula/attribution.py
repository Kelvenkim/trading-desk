"""수익의 출처 나누기: 분산(3지수) / 레버리지(목표변동성) / 추세필터 각각의 몫"""
import numpy as np, pandas as pd
import lab as L
from robust import gtaa, met, U3
OOS = slice("2006-01-01", "2026-12-31")
eq3 = L.monthly(pd.DataFrame({a: pd.Series(1 / 3, index=L.DATES) for a in U3}))
rows = {
    "보유 3지수 균등 (월말 리밸런싱)": eq3,
    "보유 3지수 균등 + 목표 15% 최대 2배": L.vol_scale(eq3, 0.15, 2.0),
    "보유 3지수 균등 + 목표 20% 최대 2배": L.vol_scale(eq3, 0.20, 2.0),
    "보유 3지수 균등 + 목표 25% 최대 2배": L.vol_scale(eq3, 0.25, 2.0),
    "추세필터 3지수 150일선 (맞춤 없음)": gtaa(U3, 150, 0),
    "추세필터 3지수 150일선 + 목표 15% 최대 2배": gtaa(U3, 150, 0.15),
    "추세필터 3지수 150일선 + 목표 20% 최대 2배": gtaa(U3, 150, 0.20),
    "추세필터 3지수 150일선 + 목표 25% 최대 2배": gtaa(U3, 150, 0.25),
    "보유 NDX": pd.DataFrame({"NDX": pd.Series(1.0, index=L.DATES)}),
    "보유 NDX + 목표 20% 최대 2배": L.vol_scale(pd.DataFrame({"NDX": pd.Series(1.0, index=L.DATES)}), 0.20, 2.0),
}
for k, W in rows.items():
    r = L.run_weights(W)
    print(f"{k:40s} 전체 {met(r[OOS])} | 06~15 {met(r['2006':'2015'])} | 16~26 {met(r['2016':'2026'])}")
