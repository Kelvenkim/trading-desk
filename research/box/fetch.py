"""박스권 연구용 데이터: 시가총액 상위 대형주 + KODEX 200의 1시간봉(2년), 5분봉(60일)."""
import warnings
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
N_TOP = 60
HEDGE = "069500.KS"  # KODEX 200 (코스피200 선물 대용)


def universe():
    l = fdr.StockListing("KRX")
    l = l[l["Market"].isin(["KOSPI", "KOSDAQ"]) & l["Code"].str.endswith("0")]
    l = l[~l["Name"].str.contains("스팩|리츠")]
    l = l.sort_values("Marcap", ascending=False).head(N_TOP)
    l["yf"] = l["Code"] + l["Market"].map({"KOSPI": ".KS", "KOSDAQ": ".KQ"})
    return l[["yf", "Name", "Market", "Marcap"]].rename(columns={"yf": "symbol", "Name": "name"})


def download(symbols, period, interval):
    d = yf.download(symbols, period=period, interval=interval, group_by="ticker",
                    progress=False, threads=True, auto_adjust=False)
    rows = []
    for s in symbols:
        try:
            x = d[s].dropna(subset=["Close"])
        except KeyError:
            continue
        x = x[["Open", "High", "Low", "Close", "Volume"]].copy()
        x.columns = ["o", "h", "l", "c", "v"]
        x["sym"] = s
        rows.append(x)
    df = pd.concat(rows)
    df.index = df.index.tz_convert("Asia/Seoul")
    df.index.name = "ts"
    return df.reset_index()


if __name__ == "__main__":
    u = universe()
    u.to_csv(OUT / "universe.csv", index=False)
    syms = list(u["symbol"]) + [HEDGE]
    for period, interval in [("730d", "60m"), ("60d", "5m")]:
        df = download(syms, period, interval)
        df.to_parquet(OUT / f"bars_{interval}.parquet")
        print(interval, len(df), "rows", df["sym"].nunique(), "symbols", df["ts"].min(), "~", df["ts"].max())
