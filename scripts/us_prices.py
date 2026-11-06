"""미국 시세 받기 (yfinance 일괄) — {티커: [[날짜, 시, 고, 저, 종, 거래량], ...]}"""
import math, time, warnings
import pandas as pd
warnings.filterwarnings("ignore")


def download(tickers, period="2y", chunk=120):
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        for k in range(3):
            try:
                df = yf.download(part, period=period, interval="1d", group_by="ticker", auto_adjust=True, threads=True, progress=False)
                break
            except Exception:
                time.sleep(5 + 10 * k); df = None
        if df is None or df.empty:
            continue
        for t in part:
            try:
                d = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                d = d.dropna(subset=["Open", "High", "Low", "Close"])
                d = d[(d[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
                out[t] = [[ix.strftime("%Y-%m-%d"), round(float(r.Open), 4), round(float(r.High), 4), round(float(r.Low), 4),
                           round(float(r.Close), 4), int(r.Volume) if not math.isnan(r.Volume) else 0] for ix, r in d.iterrows()]
            except Exception:
                pass
        time.sleep(1)
    return out
