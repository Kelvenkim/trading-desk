"""테마 눌림(V3)이 시장 상태별로 어땠나: 코스피200 200일선 위/아래, 최근 20일 급락 여부"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "scripts"))
exec(open(ROOT / "research/rank/variants.py").read().split("res = {}")[0])
pos = {d: i for i, d in enumerate(C.index)}
ma200 = ks.rolling(200).mean(); r20 = ks / ks.shift(20) - 1
vol20 = ks.pct_change().rolling(20).std() * np.sqrt(252)
rows = []
for d in C.index[400:-21:5]:
    i = pos[d]; cols = C.columns[C.loc[d].notna() & Op.iloc[i + 1].notna()]
    tr = ttrend.loc[d].dropna()
    if len(tr) < 8: continue
    thr = pd.Series({c: tr.rank(pct=True).get(P.get(c), 0.5) if P.get(c) in tr.index else 0.5 for c in cols})
    rev = -(C.loc[d, cols] / C.iloc[i - 5][cols] - 1)
    s3 = L.xrank(thr) + 0.5 * L.xrank(rev)
    s5 = L.xrank(F["lowvol"].loc[d, cols])
    fr = C.iloc[i + 20][cols] / Op.iloc[i + 1][cols] - 1
    t3 = s3.sort_values(ascending=False, kind="stable").index[:20]; t5 = s5.sort_values(ascending=False, kind="stable").index[:20]
    # 한 테마 최대 5종목으로 분산한 버전
    seen, t3d = {}, []
    for c in s3.sort_values(ascending=False, kind="stable").index:
        k = P.get(c, "-"); 
        if seen.get(k, 0) < 5: t3d.append(c); seen[k] = seen.get(k, 0) + 1
        if len(t3d) == 20: break
    rows.append({"d": d, "up": ks.iloc[i] > ma200.iloc[i], "crash": r20.iloc[i] < -0.05, "hivol": vol20.iloc[i] > 0.25,
                 "v3": fr[t3].mean() - fr.mean(), "v3d": fr[t3d].mean() - fr.mean(), "lowvol": fr[t5].mean() - fr.mean(), "mkt": fr.mean()})
R = pd.DataFrame(rows)
def show(name, g):
    print(f"  {name:<28} {len(g):>3}회  테마눌림 {g.v3.mean()*100:+.2f}% (이김 {(g.v3>0).mean()*100:.0f}%) | 한 테마 5개 제한 {g.v3d.mean()*100:+.2f}% (이김 {(g.v3d>0).mean()*100:.0f}%) | 낮은 변동성 {g.lowvol.mean()*100:+.2f}% | 시장 {g.mkt.mean()*100:+.1f}%")
show("전체", R)
show("코스피200 200일선 위", R[R.up]); show("코스피200 200일선 아래", R[~R.up])
show("최근 20일 -5% 넘게 급락", R[R.crash]); show("변동성 높음(연 25%↑)", R[R.hivol]); show("변동성 보통", R[~R.hivol])
show("200일선 아래 + 변동성 높음", R[~R.up & R.hivol])
for k in ("v3", "v3d"):
    a = R[k]
    print(f"{k}: 20일 초과수익 표준편차 {a.std()*100:.1f}%, 하위 5% {a.quantile(.05)*100:+.1f}%, 최악 {a.min()*100:+.1f}%, -10%보다 나쁜 때 {(a<-0.10).mean()*100:.1f}%")
