"""오더블록 제한 풀어보기 (11/22 형 요청: 지금 규칙은 2년 101번뿐 — 제한이 너무 큼)
1시간봉 2년 BTC·ETH·SOL, 수수료 한쪽 0.05%. 바꿔보는 것:
  K   = 갭: 양봉 몸통 ≥ 음봉 몸통 × K  (지금 2.0)
  need= 필터 조합 (지금 갭+유동성 흡수+FVG)
  L   = 유동성 흡수 판단에 쓰는 직전 봉 수 (지금 20)
  k3  = 3캔들(양→음→양)도 허용 (지금 2캔들만)
  minrr = 파동 고점까지 거리 ≥ 손절 거리 × minrr 일 때만 (지금 1.0)
나머지(OB 터치 진입·꼬리 끝 손절·파동 고점 절반 익절+본전·반대 OB 정리·48봉 대기·72봉 보유)는 그대로"""
import itertools, numpy as np, pandas as pd
from ob import load, find_obs, simulate
D = {t: load(t, "1h") for t in ["BTC-USD", "ETH-USD", "SOL-USD"]}
NEEDS = [(), ("gap",), ("sweep",), ("fvg",), ("gap", "sweep"), ("gap", "fvg"), ("sweep", "fvg"), ("gap", "sweep", "fvg")]
rows = []
for K, L in itertools.product([1.0, 1.5, 2.0, 3.0], [10, 20, 50]):
    OBS = {t: find_obs(d, {"K": K, "L": L}) for t, d in D.items()}
    for need, k3, minrr in itertools.product(NEEDS, [False, True], [0.0, 1.0]):
        rec = dict(K=K, need="+".join(need) or "없음", L=L, k3=k3, minrr=minrr); allT = []
        for t, d in D.items():
            O = OBS[t] if k3 else [o for o in OBS[t] if o["k"] == 2]
            T = simulate(d, O, dict(W=48, hold=72, K=K, need=need, stop_rule=1, tp="half", cost=.0005, minrr=minrr)); T["sym"] = t[:3]; allT.append(T)
        T = pd.concat(allT)
        if len(T) < 20:
            continue
        h = T.te.min() + (T.te.max() - T.te.min()) / 2
        rec.update(n=len(T), win=(T.r > 0).mean(), avgR=T.r.mean(), **{c: T[T.sym == c].r.mean() for c in ["BTC", "ETH", "SOL"]},
                   a=T[T.te < h].r.mean(), b=T[T.te >= h].r.mean(), cost01=(T.r - 0.001 / T.risk).mean())
        rec["coins+"] = int(sum(rec[c] > 0 for c in ["BTC", "ETH", "SOL"])); rec["halves+"] = int((rec["a"] > 0) + (rec["b"] > 0))
        rows.append(rec)
R = pd.DataFrame(rows); R.to_csv("loosen.csv", index=False)
pd.set_option("display.width", 250)
cur = R[(R.K == 2.0) & (R.need == "gap+sweep+fvg") & (R.L == 20) & (~R.k3) & (R.minrr == 1.0)]
print("지금 규칙:\n", cur.round(3).to_string(index=False))
for p in ["K", "need", "L", "k3", "minrr"]:
    print(f"\n[{p}별 평균] ", R.groupby(p).agg(n=("n", "mean"), avgR=("avgR", "mean"), win=("win", "mean")).round(3).to_dict("index"))
ok = R[(R["coins+"] == 3) & (R["halves+"] == 2)]
print(f"\n코인 3개 + 앞뒤 1년 모두 플러스인 설정 {len(ok)}개 / 전체 {len(R)}개 — 거래 수별 최고")
for lo, hi in [(100, 200), (200, 400), (400, 800), (800, 99999)]:
    X = ok[(ok.n >= lo) & (ok.n < hi)].sort_values("avgR", ascending=False).head(4)
    print(f"-- {lo}~{hi}번\n", X.round(3).to_string(index=False) if len(X) else "  없음")
