"""BOS 공식(상위4·1h·S4+B) 결과가 이동평균선 추세와 관련 있는지 — 2년 전체 + 11월
추세 판정은 모두 '진입 직전에 알 수 있는 값'만 사용 (일봉은 전날 종가 기준)"""
import numpy as np, pandas as pd, bos_test as B
rows = []
import sys
SY = sys.argv[1].split(",") if len(sys.argv) > 1 else ["BTC", "ETH", "XRP", "BNB"]
for sym in SY:
    d = B.load(sym, "1h").iloc[:-1]
    S = B.structure(d)
    T = B.simulate(S, "S4", "B")
    day = d.close.resample("1D").last().dropna()
    try:                                                     # 200일선 계산용 긴 일봉 이어 붙이기
        lg = pd.read_parquet(B.DD / f"d_{sym}-USD.parquet")["Close"]; lg.index = lg.index.tz_localize("UTC")
        day = pd.concat([lg[lg.index < day.index[0]], day])
    except Exception:
        pass
    feat = pd.DataFrame({"c": day, "ma50": day.rolling(50).mean(), "ma200": day.rolling(200).mean()})
    feat["slope50"] = feat.ma50.diff(5)
    feat = feat.shift(1)                                     # 전날까지 정보만
    ema200h = d.close.ewm(span=200, adjust=False).mean()
    for _, t in T.iterrows():
        f = feat.loc[:t.t.normalize()].iloc[-1]
        if np.isnan(f.ma200): continue                       # 200일선 모르면 제외
        prev_h = d.loc[:t.t].iloc[-2]                        # 진입 봉 직전 1시간봉
        s = t.side
        rows.append(dict(sym=sym, t=t.t, side=s, r=t.r,
                         d50=np.sign(f.c - f.ma50) == s, d200=np.sign(f.c - f.ma200) == s,
                         sl50=np.sign(f.slope50) == s, h200=np.sign(prev_h.close - ema200h.loc[prev_h.name]) == s))
X = pd.DataFrame(rows)
cut = X.t.min() + (X.t.max() - X.t.min()) / 2
nov = X.t >= pd.Timestamp("2026-11-01", tz="Asia/Seoul")
def line(name, m):
    a = X[m]; top = a.r.nlargest(max(1, int(len(a) * .05))).index
    n_ = X[m & nov]
    return dict(조건=name, 거래=len(a), 거래당R=round(a.r.mean(), 2), 승률=f"{(a.r > 0).mean():.0%}",
                앞기간=round(a[a.t < cut].r.mean(), 2), 뒤기간=round(a[a.t >= cut].r.mean(), 2), 대박5빼면=round(a.drop(top).r.mean(), 2),
                코인별=" ".join(f"{s}{g.r.mean():+.2f}" for s, g in a.groupby("sym")),
                **{"11월": f"{len(n_)}번 {n_.r.sum():+.1f}R"})
out = [line("전체", X.r == X.r)]
for col, nm in [("d50", "일봉 50일선"), ("d200", "일봉 200일선"), ("sl50", "50일선 기울기"), ("h200", "1시간봉 200EMA")]:
    out += [line(nm + " 같은 방향", X[col]), line(nm + " 반대 방향", ~X[col])]
out += [line("50일선+200일선 둘 다 같은 방향", X.d50 & X.d200)]
R = pd.DataFrame(out); pd.set_option("display.width", 250); print(R.to_string(index=False))
R.to_csv("ma_trend_result.csv", index=False)
