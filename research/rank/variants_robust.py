"""V3(강한 테마 + 단기 눌림) 견고성: 눌림 비중·눌림 기간·상위 몇 개·기간 나눠 보기"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "scripts"))
exec(open(ROOT / "research/rank/variants.py").read().split("res = {}")[0])
out = {}
for d in C.index[400:-21:5]:
    i = pos[d] if 'pos' in dir() else None
pos = {d: i for i, d in enumerate(C.index)}
for d in C.index[400:-21:5]:
    i = pos[d]; cols = C.columns[C.loc[d].notna() & Op.iloc[i + 1].notna()]
    tr = ttrend.loc[d].dropna()
    if len(tr) < 8: continue
    thr = pd.Series({c: tr.rank(pct=True).get(P.get(c), 0.5) if P.get(c) in tr.index else 0.5 for c in cols})
    fr = C.iloc[i + 20][cols] / Op.iloc[i + 1][cols] - 1
    for w in (0.3, 0.5, 1.0):
        for n in (3, 5, 10):
            rev = -(C.loc[d, cols] / C.iloc[i - n][cols] - 1)
            s = L.xrank(thr) + w * L.xrank(rev)
            for top in (10, 20, 30):
                t = s.sort_values(ascending=False, kind="stable").index[:top]
                out.setdefault((w, n, top), []).append((d, float(fr[t].mean() - fr.mean())))
rows = []
for k, v in out.items():
    a = np.array([x[1] for x in v]); dd = [x[0] for x in v]
    early = np.array([x[1] for x in v if x[0] < pd.Timestamp("2021-01-01")]); late = np.array([x[1] for x in v if x[0] >= pd.Timestamp("2021-01-01")])
    rows.append((k, a.mean() * 100, early.mean() * 100, late.mean() * 100))
rows.sort(key=lambda r: -r[1])
print("눌림 비중, 눌림 기간(일), 상위 N → 20일 초과수익(전체 / 2015~2020 / 2021~2026)")
for k, a, e, l in rows: print(f"  {k}  {a:+.2f}%  {e:+.2f}%  {l:+.2f}%")
print("플러스 비율:", sum(r[1] > 0 for r in rows), "/", len(rows), " 두 기간 모두 플러스:", sum(r[2] > 0 and r[3] > 0 for r in rows))
