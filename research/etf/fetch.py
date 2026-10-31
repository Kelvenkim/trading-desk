"""ETF 단타 연구용 데이터: 사이트와 같은 형식([unix, o, h, l, c, v])으로 5분봉(60일), 1시간봉(약 2년) 저장."""
import json
import math
import warnings
from pathlib import Path

import yfinance as yf

warnings.filterwarnings("ignore")
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
ETFS = {
    "069500.KS": "KODEX 200",
    "122630.KS": "KODEX 레버리지",
    "114800.KS": "KODEX 인버스",
    "252670.KS": "KODEX 200선물인버스2X",
    "229200.KS": "KODEX 코스닥150",
    "233740.KS": "KODEX 코스닥150레버리지",
}
for sym, name in ETFS.items():
    for iv, per in [("5m", "60d"), ("60m", "730d")]:
        df = yf.Ticker(sym).history(period=per, interval=iv, auto_adjust=False, actions=False)
        rows = []
        for ts, r in df.iterrows():
            v = [r["Open"], r["High"], r["Low"], r["Close"]]
            if any(x is None or (isinstance(x, float) and math.isnan(x)) or x <= 0 for x in v):
                continue
            rows.append([int(ts.timestamp()), *[round(float(x), 2) for x in v], int(r["Volume"] or 0)])
        (OUT / f"{sym}_{iv}.json").write_text(json.dumps({"symbol": sym, "name": name, "bars": rows}), encoding="utf-8")
        print(sym, name, iv, len(rows))
