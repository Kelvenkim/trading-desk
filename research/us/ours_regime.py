"""'우리 점수' — 약세장에서만 통하나? (11/28 형 가설)
실제 채점과 같은 방식: 순위 다음 날 시가 매수 → 1·5·20일 뒤 종가, 상위 20 − 전체 평균, 비용 전.
장 상태: S&P500 종가가 200일선 위(상승장) / 아래(약세장). 5개 항목 중 과거 자료가 있는 3개(추세·수급·안정성)를 따로도 봄.
실적·뉴스는 과거 자료가 없어 기본값(전 종목 같은 점수) → 합계 순위엔 영향 없음.
한계: 지금 S&P500·나스닥100 종목으로 과거를 봄(생존 편향) · 자료 2014-11 ~ 2026-11-05."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "scripts"))
import rank_lib as L
J = json.loads((ROOT / "research/us/data/prices.json").read_text())
U = {s["t"] for s in json.loads((ROOT / "data/us/universe.json").read_text())["stocks"]}
uni = sorted(U & set(J))
bench = J["^GSPC"]; cal = [r[0] for r in bench]
C, H, V = L.wide({t: J[t] for t in uni}, cal); Op = L.opens({t: J[t] for t in uni}, cal)
ks = pd.Series({r[0]: r[4] for r in bench}); ks.index = pd.to_datetime(ks.index); ks = ks.reindex(C.index).ffill()
ma200 = ks.rolling(200).mean()
I = L.ours_inputs(C, H, V)
pos = {d: i for i, d in enumerate(C.index)}
rows = []
for d in C.index[260:-21]:                       # 매일 (겹침은 t 계산에서 보정)
    i = pos[d]; cols = C.columns[C.loc[d].notna() & Op.iloc[i + 1].notna()]
    O = L.our_score(**{k: v.loc[d, cols] for k, v in I.items()})
    S = {"합계": O["total"], "추세만": O["trend"] + O["safe"] * 1e-6, "수급만": O["flow"] + O["safe"] * 1e-6, "안정성만": O["safe"],
         "안정성 뺀 합계": O["total"] - O["safe"]}
    up = bool(ks.iloc[i] > ma200.iloc[i])
    for h in (1, 5, 20):
        fr = C.iloc[i + h][cols] / Op.iloc[i + 1][cols] - 1
        base = fr.mean()
        for k, s in S.items():
            top = s.sort_values(ascending=False, kind="stable").index[:20]
            rows.append((d, h, k, up, float(fr[top].mean() - base)))
R = pd.DataFrame(rows, columns=["d", "h", "k", "up", "ex"])
R.to_parquet(Path(__file__).parent / "data/ours_regime.parquet")


def summ(x, h):
    a = x.ex.values; n_ind = max(1, len(a) / h)  # 겹치지 않는 관측 수
    t = a.mean() / (a.std() + 1e-12) * np.sqrt(n_ind)
    return dict(n=len(a), 독립=int(n_ind), 평균=f"{a.mean()*100:+.2f}%", 이김=f"{(a>0).mean():.0%}", t=round(t, 1))


out = []
for (k, h), g in R.groupby(["k", "h"], sort=False):
    for lab, m in [("전체", g.up | ~g.up), ("상승장", g.up), ("약세장", ~g.up)]:
        out.append(dict(항목=k, 기간=f"{h}일", 장=lab, **summ(g[m], h)))
T = pd.DataFrame(out)
pd.set_option("display.width", 200)
print(T.to_string(index=False))
# 약세장 구간별 (언제 약세장이었나 · 합계 5일)
g = R[(R.k == "합계") & (R.h == 5) & (~R.up)].copy()
g["spell"] = (g.d.diff().dt.days > 10).cumsum()
print("\n약세장 구간별 (합계 · 5일)")
for _, s in g.groupby("spell"):
    if len(s) >= 10:
        print(f"  {s.d.min():%Y-%m}~{s.d.max():%Y-%m} {len(s)}일  평균 {s.ex.mean()*100:+.2f}%  이김 {(s.ex>0).mean():.0%}")
print("\n약세장 비율:", f"{(~R[(R.k=='합계')&(R.h==1)].up).mean():.0%}")
T.to_csv(Path(__file__).parent / "ours_regime_result.csv", index=False)
