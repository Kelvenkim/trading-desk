"""미국 순위 방식 비교 (2016~2026): 순위 다음 날 시가 매수 → 5·20일 뒤 종가, 상위 20 − 전체 평균. 현재 S&P500+나스닥100+테마 종목(생존 편향)"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "scripts"))
import rank_lib as L
from us_narr_def import NARR
J = json.loads((ROOT / "research/us/data/prices.json").read_text())
U = {s["t"] for s in json.loads((ROOT / "data/us/universe.json").read_text())["stocks"]}
uni = sorted(U & set(J))
bench = J["^GSPC"]; cal = [r[0] for r in bench]
C, H, V = L.wide({t: J[t] for t in uni}, cal); Op = L.opens({t: J[t] for t in uni}, cal)
ks = pd.Series({r[0]: r[4] for r in bench}); ks.index = pd.to_datetime(ks.index); ks = ks.reindex(C.index).ffill()
I = L.ours_inputs(C, H, V); F = L.price_factors(C, H, V)
prim = {}
for n in NARR:
    for t in n["tickers"]:
        prim.setdefault(t, n["key"])
CA = {}
for n in NARR:
    cs = [t for t in n["tickers"] if t in J]
    Ct, _, _ = L.wide({t: J[t] for t in cs}, cal)
    r = Ct.pct_change(fill_method=None).clip(-0.3, 0.3).mean(axis=1).fillna(0)
    CA[n["key"]] = (1 + r).cumprod()
D = pd.DataFrame(CA); lr = np.log(D).sub(np.log(ks), axis=0); ttr = ((lr - lr.shift(63)) + (lr - lr.shift(126))) / 2
mom = C.shift(21) / C.shift(252) - 1
pos = {d: i for i, d in enumerate(C.index)}
ma200 = ks.rolling(200).mean()
res = {}
for d in C.index[300:-21:5]:
    i = pos[d]; cols = C.columns[C.loc[d].notna() & Op.iloc[i + 1].notna()]
    O = L.our_score(**{k: v.loc[d, cols] for k, v in I.items()})
    tr = ttr.loc[d].dropna(); tp = tr.rank(pct=True)
    thr = pd.Series({c: tp.get(prim.get(c), 0.5) for c in cols})
    rev = -(C.loc[d, cols] / C.iloc[i - 5][cols] - 1)
    V_ = {"우리 점수": O["total"], "강한 테마": thr, "테마 눌림": L.xrank(thr) + 0.5 * L.xrank(rev),
          "12-1 모멘텀": mom.loc[d, cols], "3개월 강세": C.loc[d, cols] / C.iloc[i - 63][cols], "낮은 변동성": F["lowvol"].loc[d, cols],
          "단기 눌림": rev, "모멘텀 + 눌림": L.xrank(mom.loc[d, cols]) + 0.5 * L.xrank(rev), "52주 고점 근접": F["hi52"].loc[d, cols]}
    up = ks.iloc[i] > ma200.iloc[i]
    for h in (5, 20):
        fr = C.iloc[i + h][cols] / Op.iloc[i + 1][cols] - 1
        for k, s in V_.items():
            top = s.sort_values(ascending=False, kind="stable").index[:20]
            res.setdefault((k, h), []).append((d.year, float(fr[top].mean() - fr.mean()), up))
out = {}
print("상위 20 − 전체 평균 (다음 날 시가 매수, 비용 전) | 상승장 / 하락장")
for (k, h), v in sorted(res.items(), key=lambda x: (x[0][1], -np.mean([y[1] for y in x[1]]))):
    a = np.array([x[1] for x in v]); yrs = pd.DataFrame(v, columns=["y", "e", "up"]).groupby("y").e.mean()
    upm = np.mean([x[1] for x in v if x[2]]); dnm = np.mean([x[1] for x in v if not x[2]]) if any(not x[2] for x in v) else np.nan
    t = a.mean() / a.std() * np.sqrt(len(a) / (h / 5))
    print(f"{h:>2}일 {k:<12} 평균 {a.mean()*100:+.2f}% 이김 {(a>0).mean()*100:.0f}% t {t:+.1f} 플러스 연도 {(yrs>0).sum()}/{len(yrs)} | {upm*100:+.2f}% / {dnm*100:+.2f}%")
    out.setdefault(k, {})[str(h)] = {"ex": float(a.mean()), "beat": float((a > 0).mean()), "t": float(t), "years_pos": int((yrs > 0).sum()), "years": int(len(yrs)),
                                     "up": float(upm), "down": float(dnm)}
(ROOT / "data/us/variants_backfill.json").write_text(json.dumps({"method": "순위 다음 날 시가 매수 → 5·20일 뒤 종가, 상위 20 − 전체 평균, 비용 전, 2016~2026", "variants": out}, ensure_ascii=False))
