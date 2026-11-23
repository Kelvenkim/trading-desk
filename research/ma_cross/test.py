"""형이 가져온 코드 시험 (11/23): '이동평균 교차' — 짧은 이평(ma1) ≥ 긴 이평(ma2)이면 사서 들고, 아래로 내려가면 전부 팜 (롱만)
원 코드 이름은 MACD지만 실제로는 단순 이동평균 두 개 교차 (기본 10·21, 고전 12·26)
원 코드의 문제 2가지를 고쳐서 공정하게 시험: ① 신호가 난 날 종가에 바로 체결(미래 정보) → 다음 날 시가 체결 ② 수수료·체결 차이 없음 → 왕복 0.1%(주식)·0.2%(코인)
대상: 미국 지수(SPY·QQQ) · S&P500 종목 518개(각각 따로, 결과 평균) · 코인(BTC·ETH·SOL 일봉, 1시간봉 2년) · 코스피
비교: 그냥 보유 / 기간 앞·뒤 반 / 이평 길이 여러 개(한 조합만 좋으면 우연)"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf

ROOT = Path(__file__).resolve().parents[2]; H = Path(__file__).parent / "data"; H.mkdir(exist_ok=True)
PAIRS = [(5, 20), (10, 21), (12, 26), (20, 50), (50, 200)]


def dl(tks, period="max", interval="1d", name="x"):
    f = H / f"{name}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    P = yf.download(tks, period=period, interval=interval, auto_adjust=True, progress=False, group_by="ticker", threads=True)
    P.to_pickle(f); return P


def sim(o, c, a, b, cost):
    """다음 봉 시가 체결. 반환: 봉별 수익률 시리즈, 매매 횟수"""
    m1, m2 = c.rolling(a).mean(), c.rolling(b).mean()
    sig = (m1 >= m2).astype(float).where(m2.notna(), 0.0)
    pos = sig.shift(1).fillna(0)                       # 신호 다음 봉부터 보유
    # 보유 중 수익: 시가 진입 봉은 시가→종가, 이후 종가→종가, 청산 봉은 전 종가→시가
    r_cc = c.pct_change().fillna(0)
    enter = (pos == 1) & (pos.shift(1, fill_value=0) == 0)
    exit_ = (pos == 0) & (pos.shift(1, fill_value=0) == 1)
    r = pd.Series(0.0, index=c.index)
    r[pos == 1] = r_cc[pos == 1]
    r[enter] = (c / o - 1)[enter]
    r[exit_] = (o / c.shift(1) - 1)[exit_]
    r[enter] -= cost / 2; r[exit_] -= cost / 2
    return r, int(enter.sum())


def stats(r, per):
    eq = (1 + r).cumprod()
    yrs = len(r) / per
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 and eq.iloc[-1] > 0 else np.nan
    mdd = (eq / eq.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(per) if r.std() > 0 else np.nan
    return cagr, mdd, sh


def one(o, c, per, cost, lab):
    o, c = o.dropna(), c.dropna(); o = o.reindex(c.index)
    bh = c.pct_change().fillna(0)
    out = [(lab, "그냥 보유", *stats(bh, per), 0)]
    for a, b in PAIRS:
        r, n = sim(o, c, a, b, cost)
        out.append((lab, f"{a}·{b}", *stats(r, per), n / (len(c) / per)))
    half = len(c) // 2
    hh = []
    for a, b in PAIRS:
        r, _ = sim(o, c, a, b, cost)
        hh.append((f"{a}·{b}", stats(r.iloc[:half], per)[0] - stats(bh.iloc[:half], per)[0], stats(r.iloc[half:], per)[0] - stats(bh.iloc[half:], per)[0]))
    return out, hh


def show(rows, hh=None):
    for lab, k, cg, md, sh, n in rows:
        print(f"  {lab:<10} {k:<8} 연 {cg:+7.1%} · 최대 낙폭 {md:7.1%} · 샤프 {sh:5.2f}" + (f" · 1년 매수 {n:.1f}번" if n else ""))
    if hh:
        print("    앞 반 / 뒤 반 — 그냥 보유 대비 연 수익 차이: " + " · ".join(f"{k} {x:+.1%}/{y:+.1%}" for k, x, y in hh))


def main():
    print("=== 미국 지수 (일봉, 1993~ / 1999~, 왕복 0.1%)")
    P = dl(["SPY", "QQQ"], name="idx")
    for t in ["SPY", "QQQ"]:
        rows, hh = one(P[t]["Open"], P[t]["Close"], 252, 0.001, t); show(rows, hh)
    print("\n=== 코스피 (일봉, 왕복 0.25%)")
    K = dl(["^KS11"], name="ks")
    k = K["^KS11"] if isinstance(K.columns, pd.MultiIndex) else K
    rows, hh = one(k["Open"].where(k["Open"] > 0), k["Close"], 250, 0.0025, "코스피"); show(rows, hh)
    print("\n=== 코인 일봉 (2017~ 정도, 왕복 0.2%, 1년 365일)")
    C = dl(["BTC-USD", "ETH-USD", "SOL-USD"], name="coin_d")
    for t in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        rows, hh = one(C[t]["Open"], C[t]["Close"], 365, 0.002, t[:3]); show(rows, hh)
    print("\n=== 코인 1시간봉 (최근 2년, 왕복 0.2%)")
    C1 = dl(["BTC-USD", "ETH-USD", "SOL-USD"], period="729d", interval="1h", name="coin_h")
    for t in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        rows, hh = one(C1[t]["Open"], C1[t]["Close"], 24 * 365, 0.002, t[:3] + " 1h"); show(rows, hh)
    print("\n=== S&P500 종목 518개 각각 (2016~ 10년, 왕복 0.1%) — 종목별 결과의 중앙값, 그냥 보유를 이긴 종목 비율")
    U = [s["t"] for s in json.loads((ROOT / "data/us/universe.json").read_text())["stocks"]]
    S = dl(U, period="10y", name="sp")
    res = {k: [] for k in ["그냥 보유"] + [f"{a}·{b}" for a, b in PAIRS]}
    win = {k: 0 for k in res}; n_ok = 0
    for t in U:
        try:
            o, c = S[t]["Open"].dropna(), S[t]["Close"].dropna()
        except Exception:
            continue
        if len(c) < 1000:
            continue
        n_ok += 1
        rows, _ = one(o, c, 252, 0.001, t)
        bh = rows[0][2]
        for lab, k, cg, md, sh, n in rows:
            res[k].append((cg, md, sh, n))
            if k != "그냥 보유" and cg > bh:
                win[k] += 1
    for k, v in res.items():
        a = np.array(v, dtype=float)
        print(f"  {k:<8} 연 수익 중앙 {np.nanmedian(a[:, 0]):+.1%} · 최대 낙폭 중앙 {np.nanmedian(a[:, 1]):.1%} · 샤프 중앙 {np.nanmedian(a[:, 2]):.2f}"
              + (f" · 그냥 보유를 이긴 종목 {win[k] / n_ok:.0%}" if k != "그냥 보유" else f" ({n_ok}종목)"))


if __name__ == "__main__":
    main()
