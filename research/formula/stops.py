"""
손절(스톱로스)로 큰 하락을 줄일 수 있는가 — 3지수(코스피200·S&P500·나스닥100) 분산 보유에 적용
  손절: 고정(매수가 대비) / 트레일링(보유 중 최고 종가 대비), 지수별 또는 포트폴리오 전체 기준
  재진입: 최근 R일 최고 종가 돌파 / n일선 위로 회복 / K일 쉬고 무조건
  종가 기준 판단 → 다음 날 종가에 매매 → 그다음 날 수익부터 (lab.run_weights 와 같은 지연)
  지수는 종가만 있어서 장중 손절은 모사하지 못함 (실제 손절 주문은 하락이 완만하면 더 유리, 갭 하락이면 더 불리)
"""
import itertools

import numpy as np
import pandas as pd

import lab as L

U3 = ["KS200", "SPX", "NDX"]
OOS = slice("2006-01-01", "2026-12-31")


def met(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    return (eq.iloc[-1] ** (252 / len(r)) - 1) * 100, (eq / eq.cummax() - 1).min() * 100, r.mean() / r.std() * np.sqrt(252)


def reentry_ok(px, i, how, hh, ma, days_out):
    if how[0] == "high":
        return px[i] >= hh[how[1]][i]
    if how[0] == "sma":
        return px[i] > ma[how[1]][i]
    return days_out >= how[1]


def asset_stop(a, kind, s, how):
    """한 지수에 손절·재진입을 적용한 보유 신호 (1=보유, 0=현금)."""
    px = L.PX[a].values
    hh = {r: L.PX[a].rolling(r, min_periods=r).max().values for r in (20, 50)}
    ma = {n: L.sma(L.PX[a], n).values for n in (50, 100)}
    sig = np.zeros(L.N)
    inpos, ref, out = False, 0.0, 0
    for i in range(L.N):
        if np.isnan(px[i]):
            continue
        if not inpos:
            out += 1
            if out == 1 and i > 0 and sig[i - 1] == 0 and not any(sig[:i]):   # 처음 시작은 바로 매수
                inpos, ref = True, px[i]
            elif reentry_ok(px, i, how, hh, ma, out):
                inpos, ref = True, px[i]
        else:
            ref = max(ref, px[i]) if kind == "trail" else ref
            if px[i] <= ref * (1 - s):
                inpos, out = False, 0
        sig[i] = 1.0 if inpos else 0.0
    return pd.Series(sig, index=L.DATES)


def per_asset(kind, s, how):
    on = pd.DataFrame({a: asset_stop(a, kind, s, how) for a in U3})
    return L.monthly(on / 3) if False else on / 3   # 손절은 매일 반응 (월말까지 기다리지 않음)


def portfolio_stop(kind, s, how):
    """3지수 균등 포트폴리오 지수에 손절 적용 → 전부 현금 / 전부 보유."""
    idx = (1 + L.RET[U3].fillna(0).mean(axis=1)).cumprod()
    px = idx.values
    hh = {r: idx.rolling(r, min_periods=r).max().values for r in (20, 50)}
    ma = {n: idx.rolling(n, min_periods=n).mean().values for n in (50, 100)}
    sig = np.zeros(L.N)
    inpos, ref, out = True, px[0], 0
    for i in range(L.N):
        if inpos:
            ref = max(ref, px[i]) if kind == "trail" else ref
            if px[i] <= ref * (1 - s):
                inpos, out = False, 0
        else:
            out += 1
            if reentry_ok(px, i, how, hh, ma, out):
                inpos, ref = True, px[i]
        sig[i] = 1.0 if inpos else 0.0
    sg = pd.Series(sig, index=L.DATES)
    return pd.DataFrame({a: sg / 3 for a in U3})


if __name__ == "__main__":
    base = L.monthly(pd.DataFrame({a: pd.Series(1 / 3, index=L.DATES) for a in U3}))
    rb = L.run_weights(base)
    c0, d0, s0 = met(rb[OOS])
    print(f"기준: 3지수 균등 보유 → 연 {c0:.1f}% · MDD {d0:.1f}% · 샤프 {s0:.2f}\n")
    HOWS = [("high", 20), ("high", 50), ("sma", 50), ("sma", 100), ("wait", 20), ("wait", 60)]
    hname = {("high", 20): "20일 최고가 회복", ("high", 50): "50일 최고가 회복", ("sma", 50): "50일선 회복", ("sma", 100): "100일선 회복", ("wait", 20): "20일 쉬고", ("wait", 60): "60일 쉬고"}
    rows = []
    for scope, fn in [("지수별", per_asset), ("포트폴리오", portfolio_stop)]:
        for kind in ["fixed", "trail"]:
            for s in [0.05, 0.08, 0.10, 0.15, 0.20, 0.25]:
                for how in HOWS:
                    W = fn(kind, s, how)
                    r = L.run_weights(W)
                    c, d, sh = met(r[OOS]); c1, d1, _ = met(r["2006":"2015"]); c2, d2, _ = met(r["2016":"2026"])
                    held = W.sum(axis=1)[OOS]
                    stops = ((held.diff() < -0.01).groupby(held.index.year).sum()).mean()
                    rows.append({"대상": scope, "손절": "고정" if kind == "fixed" else "트레일링", "폭%": int(s * 100), "재진입": hname[how],
                                 "연수익": round(c, 1), "MDD": round(d, 1), "샤프": round(sh, 2), "06~15 연": round(c1, 1), "06~15 MDD": round(d1, 1),
                                 "16~26 연": round(c2, 1), "16~26 MDD": round(d2, 1), "투자비중": round(held.mean() * 100), "연 손절횟수": round(stops, 1)})
    T = pd.DataFrame(rows)
    T.to_csv(L.OUT / "stops_all.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    print(f"전체 {len(T)}개 설정 (2006~2026)")
    print(f"  MDD가 기준({d0:.1f}%)보다 작아진 설정: {(T.MDD > d0).mean() * 100:.0f}%")
    print(f"  연수익이 기준({c0:.1f}%) 이상인 설정: {(T.연수익 >= c0).mean() * 100:.0f}%")
    print(f"  샤프가 기준({s0:.2f}) 이상인 설정: {(T.샤프 >= s0).mean() * 100:.0f}%")
    print(f"  두 기간 모두 MDD가 줄고 연수익 손실이 2%p 이내: {((T['06~15 MDD'] > -30.9) & (T['16~26 MDD'] > -28.3) & (T.연수익 >= c0 - 2)).sum()}개\n")
    print("손절 종류·폭별 평균 (재진입 규칙 6가지 평균)")
    print(T.groupby(["대상", "손절", "폭%"])[["연수익", "MDD", "샤프", "투자비중", "연 손절횟수"]].mean().round(1).to_string())
    print("\n재진입 규칙별 평균")
    print(T.groupby(["재진입"])[["연수익", "MDD", "샤프"]].mean().round(2).to_string())
    print("\n샤프 상위 10개 (참고용 — 결과를 보고 고른 것이라 그대로 믿으면 안 됨)")
    print(T.sort_values("샤프", ascending=False).head(10).to_string(index=False))
