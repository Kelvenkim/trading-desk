"""박스 안 위치(z)에 따라 이후 h봉 수익이 실제로 되돌아오는지(평균회귀) 확인."""
import numpy as np
import pandas as pd

import boxlab as BL

data = BL.load("60m")
H = [1, 3, 6, 12, 30]
for N in [30, 60, 120]:
    rows = []
    for s, (idx, x, xi) in data.items():
        c, h, l = x["c"], x["h"], x["l"]
        T, B = BL.rolling_max(h, N), BL.rolling_min(l, N)
        M, Hh = (T + B) / 2, (T - B) / 2
        z = (c - M) / np.where(Hh > 0, Hh, np.nan)
        er = BL.eff_ratio(c, N)
        ci = xi["c"]
        df = pd.DataFrame({"z": z, "er": er})
        for k in H:
            # 지수 대비 초과수익 (시장 방향 제거)
            fwd = pd.Series(c).shift(-k) / c - 1
            fwdi = pd.Series(ci).shift(-k) / ci - 1
            df[f"r{k}"] = fwd - fwdi
        rows.append(df)
    d = pd.concat(rows).dropna()
    d["zb"] = pd.cut(d["z"], [-9, -1, -0.75, -0.25, 0.25, 0.75, 1, 9], labels=["<-1 이탈", "-1~-.75", "-.75~-.25", "중심", ".25~.75", ".75~1", ">1 이탈"])
    for name, sub in [("횡보(ER<0.25)", d[d.er < 0.25]), ("전체", d)]:
        t = sub.groupby("zb", observed=True)[[f"r{k}" for k in H]].mean() * 1e4
        t["n"] = sub.groupby("zb", observed=True).size()
        print(f"\nN={N} {name} | 지수 대비 이후 h봉 초과수익 (bp, 1bp=0.01%)")
        print(t.round(1).to_string())
