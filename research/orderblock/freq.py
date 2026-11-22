"""오더블록 하루 3번 이상 (11/22 형: 기준 너무 빡빡하게 말고, 하면서 고치자) — 1시간봉 2년, 코인 3개 / 13개
설정별 하루 평균 거래 수·평균 R·비용 0.1%일 때. 진입·손절·익절 방식은 그대로(구간 터치·꼬리 끝·파동 고점 절반)"""
import itertools, numpy as np, pandas as pd
from ob import load, find_obs, simulate
C3 = ["BTC-USD", "ETH-USD", "SOL-USD"]
C13 = C3 + ["XRP-USD", "BNB-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "DOT-USD", "BCH-USD", "TRX-USD"]
D = {t: load(t, "1h") for t in C13}
rows = []
for K, L in [(1.0, 10), (1.5, 10), (1.5, 20), (2.0, 20)]:
    OBS = {t: [o for o in find_obs(d, {"K": K, "L": L}) if o["k"] == 2] for t, d in D.items()}
    for need, minrr in itertools.product([(), ("gap",), ("sweep",), ("fvg",), ("gap", "sweep"), ("sweep", "fvg"), ("gap", "fvg")], [0.0, 1.0]):
        for nm, U in [("3개", C3), ("13개", C13)]:
            T = pd.concat([simulate(D[t], OBS[t], dict(W=48, hold=72, K=K, need=need, stop_rule=1, tp="half", cost=.0005, minrr=minrr)).assign(sym=t) for t in U])
            days = (D["BTC-USD"].index[-1] - D["BTC-USD"].index[0]).days
            h = T.te.min() + (T.te.max() - T.te.min()) / 2
            rows.append(dict(코인=nm, K=K, L=L, 필터="+".join(need) or "없음", minrr=minrr, n=len(T), 하루=len(T) / days, avgR=T.r.mean(), 승률=(T.r > 0).mean(),
                             앞=T[T.te < h].r.mean(), 뒤=T[T.te >= h].r.mean(), 비용01=(T.r - 0.001 / T.risk).mean(), 손절폭=T.risk.median() * 100))
R = pd.DataFrame(rows); R.to_csv("freq.csv", index=False); pd.set_option("display.width", 250)
X = R[R.하루 >= 3].sort_values("avgR", ascending=False)
print(f"하루 3번 이상 나오는 설정 {len(X)}개 / {len(R)}개 — 평균 R 높은 순"); print(X.head(12).round(3).to_string(index=False))
print("\n참고: 지금 규칙(K2·L20·갭+흡수+FVG·minrr1, 3개)"); print(R[(R.코인 == "3개")].sort_values("하루").head(3).round(3).to_string(index=False))
