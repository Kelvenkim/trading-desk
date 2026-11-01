"""백필용: 현재 시총 상위 300 보통주 일봉 2014~ (FDR) + 코스피200"""
import json, time, re, FinanceDataReader as fdr, pandas as pd
from pathlib import Path
D = Path(__file__).parent / "data"; D.mkdir(exist_ok=True)
L = fdr.StockListing("KRX")
L = L[~L["Name"].str.contains(r"(우|우B|우C|\(전환\))$|스팩", regex=True)]
L = L[L["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"])].sort_values("Marcap", ascending=False).head(300)
out = {"names": dict(zip(L.Code, L.Name)), "market": dict(zip(L.Code, L.Market)), "stocks": {}}
for i, c in enumerate(L.Code):
    for k in range(3):
        try:
            df = fdr.DataReader(c, "2013-06-01"); break
        except Exception as e:
            time.sleep(2); df = None
    if df is None or df.empty: continue
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    out["stocks"][c] = [[d.strftime("%Y-%m-%d"), float(r.Open), float(r.High), float(r.Low), float(r.Close), float(r.Volume)] for d, r in df.iterrows()]
    if i % 25 == 0: print(i, c, len(df), flush=True)
k = fdr.DataReader("KS200", "2013-06-01")
out["ks200"] = {d.strftime("%Y-%m-%d"): float(v) for d, v in k["Close"].items()}
json.dump(out, open(D / "prices300.json", "w"))
print("done", len(out["stocks"]))
