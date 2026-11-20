"""금리 발표(FOMC) 전 매도 시험 — 2010~2026, 예정된 회의 결정일만
가설(형 11/20): 발표 2~3일 전에 매도(숏) 포지션 → 발표날 정리하면 수익?
비교: 같은 구간 S&P500 롱, 채권(TLT 20년·IEF 7~10년) 롱/숏, 그리고 아무 날이나 같은 길이로 했을 때(무작위 기준)
비용: 왕복 0.10% (수수료+체결 차이). 숏 대여료는 3일이라 무시
"""
import numpy as np, pandas as pd, yfinance as yf
from pathlib import Path
H = Path(__file__).parent
dates = [pd.Timestamp(l.strip()) for l in open(H / "fomc_dates.txt") if l[:2] == "20"]
px = {t: yf.Ticker(t).history(start="2009-10-01", auto_adjust=True)[["Open", "Close"]] for t in ["SPY", "TLT", "IEF", "QQQ"]}
for t in px: px[t].index = px[t].index.tz_localize(None).normalize()
idx = px["SPY"].index
dates = [d for d in dates if d in idx and d <= idx[-1]]
COST = 0.001

def window(t, d, k_in, exit_at="close", k_out=0):
    """d 결정일. k_in 거래일 전 종가에 진입, 결정일(+k_out) 종가 또는 시가에 청산. 롱 수익률"""
    s = px[t]; i = s.index.get_loc(d)
    a = s.Close.iloc[i - k_in]
    b = s.Open.iloc[i + k_out] if exit_at == "open" else s.Close.iloc[i + k_out]
    return b / a - 1

def stats(r, name):
    r = np.array(r); n = len(r); m = r.mean(); t = m / (r.std(ddof=1) / np.sqrt(n))
    return {"이름": name, "횟수": n, "평균": m, "이김": (r > 0).mean(), "t": t, "누적": np.prod(1 + r) - 1, "최악": r.min()}

rows = []
for k in (3, 2, 1):
    for ex in ("close", "open"):
        lab = f"{k}일 전 종가 → 발표날 {'종가' if ex == 'close' else '시가'}"
        spy = [window("SPY", d, k, ex) for d in dates]
        rows.append(stats([-x - COST for x in spy], "S&P 숏: " + lab))
        rows.append(stats([x - COST for x in spy], "S&P 롱: " + lab))
for t, nm in (("TLT", "20년 국채"), ("IEF", "7~10년 국채")):
    r = [window(t, d, 3, "close") for d in dates]
    rows.append(stats([x - COST for x in r], f"{nm} 롱: 3일 전 → 발표날 종가"))
    rows.append(stats([-x - COST for x in r], f"{nm} 숏: 3일 전 → 발표날 종가"))
# 무작위 기준: 모든 날의 3일 보유 S&P 숏
c = px["SPY"].Close; all3 = (c.shift(-3) / c - 1).dropna()
all3 = all3[all3.index >= dates[0]]
rows.append(stats(list(-all3.values - COST), "기준: 아무 날 S&P 숏 3일 (전 기간)"))
rows.append(stats(list(all3.values - COST), "기준: 아무 날 S&P 롱 3일 (전 기간)"))
T = pd.DataFrame(rows)

# 기간·금리 국면별 (3일 전 → 발표날 종가 숏)
spy3 = pd.Series([-window("SPY", d, 3) - COST for d in dates], index=dates)
tlt3 = pd.Series([window("TLT", d, 3) - COST for d in dates], index=dates)
hike = set(pd.to_datetime(["2015-12-16","2016-12-14","2017-03-15","2017-06-14","2017-12-13","2018-03-21","2018-06-13","2018-09-26","2018-12-19",
    "2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14","2023-02-01","2023-03-22","2023-05-03","2023-07-26"]))
seg = []
for nm, m in [("2010~2017", spy3.index.year <= 2017), ("2018~2026", spy3.index.year >= 2018), ("2022~2026(인상기 포함)", spy3.index.year >= 2022),
              ("금리 인상한 회의", spy3.index.isin(hike)), ("인상 안 한 회의", ~spy3.index.isin(hike))]:
    seg.append(stats(spy3[m].values, "S&P 숏 3일 전→발표날: " + nm))
    seg.append(stats(tlt3[m].values, "20년 국채 롱 3일 전→발표날: " + nm))
G = pd.DataFrame(seg)
# 1만 달러를 회의 때마다 그 구간만 넣었다면 (나머지 날은 현금)
eq = {"S&P 숏(3일 전→발표날)": np.cumprod(1 + spy3.values)[-1], "20년 국채 롱(같은 구간)": np.cumprod(1 + tlt3.values)[-1]}
pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 60)
fmt = lambda D: D.assign(평균=lambda x: (x.평균 * 100).round(2), 이김=lambda x: (x.이김 * 100).round(0), t=lambda x: x.t.round(2), 누적=lambda x: (x.누적 * 100).round(1), 최악=lambda x: (x.최악 * 100).round(1))
print("회의 수", len(dates), dates[0].date(), "~", dates[-1].date())
print(fmt(T).to_string(index=False)); print(); print(fmt(G).to_string(index=False)); print(); print({k: round((v - 1) * 100, 1) for k, v in eq.items()})
T.to_csv(H / "result_main.csv", index=False); G.to_csv(H / "result_seg.csv", index=False)
