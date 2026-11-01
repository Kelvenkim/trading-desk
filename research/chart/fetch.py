"""차트 매매 검증용: 시가총액 상위 150종목(코스피·코스닥 보통주) 일봉 2014~ (거래량 포함) + 코스피200 지수."""
import json
import time
import warnings
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd

warnings.filterwarnings("ignore")
D = Path(__file__).parent / "data"
D.mkdir(exist_ok=True)

l = fdr.StockListing("KRX")
l = l[l["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"]) & l["Code"].str.endswith("0") & ~l["Name"].str.contains("스팩|리츠")]
l = l.sort_values("Marcap", ascending=False).head(150)


def get(code):
    parts = []
    for a, b in [("2013-06-01", "2020-12-31"), ("2021-01-01", "2026-12-31")]:
        d = fdr.DataReader(code, a, b)
        parts.append(d)
    d = pd.concat(parts)
    d = d[~d.index.duplicated()].sort_index()
    d = d[(d[["Open", "High", "Low", "Close"]] > 0).all(axis=1) & (d["Volume"] > 0)]
    return [[ts.strftime("%Y-%m-%d"), float(r.Open), float(r.High), float(r.Low), float(r.Close), int(r.Volume)] for ts, r in d.iterrows()]


out, names = {}, {}
t0 = time.time()
for k, (_, r) in enumerate(l.iterrows()):
    try:
        bars = get(r["Code"])
        if len(bars) > 300:
            out[r["Code"]] = bars
            names[r["Code"]] = r["Name"]
    except Exception as e:
        print("skip", r["Code"], e)
    if k % 25 == 0:
        print(k, f"{time.time() - t0:.0f}s", flush=True)
idx = fdr.DataReader("KS200", "2013-01-01")["Close"]
json.dump({"stocks": out, "names": names, "ks200": {d.strftime("%Y-%m-%d"): float(v) for d, v in idx.items()}}, open(D / "daily150.json", "w"), ensure_ascii=False)
print("saved", len(out), "stocks", sum(len(v) for v in out.values()), "bars")
