"""손절로 줄인 낙폭만큼 레버리지를 더하면? 이웃 설정까지 같이 봐서 한 설정만 운 좋은 건지 확인."""
import numpy as np, pandas as pd
import lab as L
from stops import portfolio_stop, per_asset, met, U3, OOS
base = L.monthly(pd.DataFrame({a: pd.Series(1 / 3, index=L.DATES) for a in U3}))
def show(name, W):
    r = L.run_weights(W); c, d, s = met(r[OOS]); c1, d1, _ = met(r["2006":"2015"]); c2, d2, _ = met(r["2016":"2026"])
    yr = (1 + r[OOS]).groupby(r[OOS].index.year).prod() - 1
    print(f"{name:44s} 연 {c:5.1f}% MDD {d:6.1f}% 샤프 {s:.2f} | 06~15 {c1:5.1f}%/{d1:6.1f}% | 16~26 {c2:5.1f}%/{d2:6.1f}% | 최악의 해 {yr.min()*100:5.1f}% ({yr.idxmin()})")
print("── 기준")
show("3지수 균등 보유", base)
for t in [0.20, 0.25]:
    show(f"3지수 균등 + 목표변동성 {int(t*100)}% (최대 2배)", L.vol_scale(base, t, 2.0))
print("── 포트폴리오 트레일링 손절 (손절폭 × 재진입)")
for s in [0.05, 0.08, 0.10]:
    for how, hn in [(("wait", 20), "20일 쉬고"), (("high", 20), "20일 최고가 회복")]:
        show(f"손절 {int(s*100)}% · {hn}", portfolio_stop("trail", s, how))
print("── 같은 손절 + 레버리지 (목표변동성 20%, 최대 2배)")
for s in [0.05, 0.08, 0.10]:
    for how, hn in [(("wait", 20), "20일 쉬고"), (("high", 20), "20일 최고가 회복")]:
        W = portfolio_stop("trail", s, how)
        show(f"손절 {int(s*100)}% · {hn} + 레버리지", L.vol_scale(W, 0.20, 2.0))
print("── 지수별 트레일링 손절 10% + 레버리지")
for how, hn in [(("wait", 20), "20일 쉬고"), (("high", 20), "20일 최고가 회복")]:
    W = per_asset("trail", 0.10, how)
    show(f"지수별 10% · {hn}", W); show(f"지수별 10% · {hn} + 레버리지", L.vol_scale(W, 0.20, 2.0))
