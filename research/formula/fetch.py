"""장기 일봉 데이터: 코스피200·코스닥 지수(네이버), S&P500·나스닥100·원달러(야후), 실제 ETF(보정용)."""
import warnings
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
D = Path(__file__).parent / "data"
D.mkdir(exist_ok=True)


def fdr_close(code, start="1990"):
    d = fdr.DataReader(code, start)
    return d["Close"].rename(code)


def fdr_long(code, start=2002):
    """FDR은 한 번에 3000행까지라 구간을 나눠 받음."""
    parts = []
    for y0 in range(start, 2027, 8):
        try:
            d = fdr.DataReader(code, f"{y0}-01-01", f"{min(y0 + 7, 2026)}-12-31")
            parts.append(d["Close"])
        except Exception:
            pass
    s = pd.concat(parts)
    return s[~s.index.duplicated()].sort_index().rename(code)


def yf_close(t):
    d = yf.Ticker(t).history(period="max", auto_adjust=True)
    s = d["Close"]
    s.index = s.index.tz_localize(None).normalize()
    return s.rename(t)


kr = pd.concat([fdr_close("KS200"), fdr_close("KQ11")], axis=1)
etf = pd.concat([fdr_long(c, 2009) for c in ["069500", "122630", "114800", "233740", "229200"]], axis=1)
us = pd.concat([yf_close("^GSPC"), yf_close("^NDX"), yf_close("KRW=X")], axis=1)
kr.to_csv(D / "kr_index.csv")
etf.to_csv(D / "kr_etf.csv")
us.to_csv(D / "us_index.csv")
for name, df in [("kr_index", kr), ("kr_etf", etf), ("us_index", us)]:
    print(name, df.shape, df.dropna(how="all").index[0].date(), "~", df.index[-1].date())
    print(df.dropna().head(1).to_string())
