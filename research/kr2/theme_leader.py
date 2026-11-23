"""테마 대장주 데이트레이딩 시험 (11/23 형): 그날 가장 강한 테마 → 그 안에서 가장 많이 오르고 있는 '대장주'를 삼 →
같은 테마에서 대장주가 바뀌면 바로 팔고 새 대장주로 갈아탐 → 장 마감 전 다 정리
5분봉 최근 약 60일 (야후). 한국: 네이버 테마 265개(지금 구성) 중 시총 300억~10조 종목 / 미국: 사이트 테마 16개
판단: 매 5분봉 마감 때 '전날 종가 대비 상승률'로 테마 평균·대장 계산 → 다음 5분봉 시가에 체결
한국은 상한가(+29%↑)면 살 수 없다고 보고 그다음 종목. 비용: 한국 왕복 0.25%(거래세 포함), 미국 0.1%
변형: 갈아타기 기준(대장이 바뀌어도 새 대장이 지금 보유보다 X%p 이상 앞서야 갈아탐), 시작 시각, 테마 정하는 법
python research/kr2/theme_leader.py kr|us"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf

H = Path(__file__).parent / "data"; ROOT = Path(__file__).resolve().parents[2]


def members(mk):
    if mk == "kr":
        U = {s["code"]: s for s in json.loads((H / "universe.json").read_text())}
        T = json.loads((H / "themes.json").read_text())
        out = {}
        for t in T:
            cs = [c + (".KS" if U[c]["mk"] == "KOSPI" else ".KQ") for c in t["codes"] if c in U]
            if len(cs) >= 3:
                out[t["name"]] = cs
        return out
    sys.path.insert(0, str(ROOT / "scripts"))
    from us_narr_def import NARR
    return {n["name"]: n["tickers"] for n in NARR}


def bars(mk, tks):
    f = H / f"m5_{mk}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    out = []
    tl = sorted(tks)
    for k in range(0, len(tl), 200):
        out.append(yf.download(tl[k:k + 200], period="60d", interval="5m", group_by="ticker", progress=False, threads=True, auto_adjust=False))
    P = pd.concat(out, axis=1); P.to_pickle(f)
    return P


def sim(M, O, C, PC, cost, edge=0.0, start=1, end_bar=None, lim=None, theme_mode="avg"):
    days = sorted(set(C.index.date))
    res = []
    for day in days:
        ix = [i for i, t in enumerate(C.index) if t.date() == day]
        if len(ix) < 20:
            continue
        pc = PC.loc[pd.Timestamp(day)] if pd.Timestamp(day) in PC.index else None
        if pc is None:
            continue
        ret = C.iloc[ix] / pc - 1                                   # 전날 종가 대비
        hold = None; ent = None; pnl = 0.0; sw = 0
        last = len(ix) - 3 if end_bar is None else min(end_bar, len(ix) - 3)
        for k in range(start, last):
            row = ret.iloc[k]
            th = {n: (row[[c for c in cs if c in row.index]].mean() if theme_mode == "avg" else row[[c for c in cs if c in row.index]].nlargest(3).mean()) for n, cs in M.items()}
            th = {n: v for n, v in th.items() if np.isfinite(v)}
            if not th:
                continue
            top = max(th, key=th.get)
            cand = row[[c for c in M[top] if c in row.index]].dropna()
            if lim is not None:
                cand = cand[cand < lim]
            if not len(cand):
                continue
            lead = cand.idxmax()
            if hold != lead:
                cur = row.get(hold, -9) if hold else -9
                if hold is None or cand[lead] - cur >= edge:
                    nxt = O.iloc[ix[k + 1]]
                    if not np.isfinite(nxt.get(lead, np.nan)):
                        continue
                    if hold:
                        px = O.iloc[ix[k + 1]][hold]
                        if np.isfinite(px):
                            pnl += px / ent - 1 - cost; sw += 1
                    hold, ent = lead, nxt[lead]
        if hold:
            px = C.iloc[ix[last]][hold]
            if np.isfinite(px):
                pnl += px / ent - 1 - cost
        res.append((day, pnl, sw))
    return pd.DataFrame(res, columns=["day", "pnl", "sw"])


def run(mk):
    M = members(mk)
    tks = sorted({c for cs in M.values() for c in cs})
    P = bars(mk, tks)
    ok = [t for t in tks if t in P.columns.get_level_values(0)]
    O = pd.DataFrame({t: P[t]["Open"] for t in ok}); C = pd.DataFrame({t: P[t]["Close"] for t in ok})
    C = C.dropna(how="all"); O = O.reindex(C.index)
    if mk == "kr":
        C.index = C.index.tz_convert("Asia/Seoul"); O.index = C.index
    else:
        C.index = C.index.tz_convert("America/New_York"); O.index = C.index
    daily_close = C.groupby(C.index.date).last(); daily_close.index = pd.to_datetime(daily_close.index)
    if mk == "kr":                                                # 한국 5분봉 마지막 값은 24% 날이 공식 종가와 1%↑ 달라서(동시호가 빠짐) 네이버 일봉 종가를 씀
        dc = {}
        for t in C.columns:
            f_ = H / f"day_{t[:6]}.json"
            if f_.exists():
                d_ = pd.DataFrame(json.loads(f_.read_text()), columns=["d", "o", "h", "l", "c", "v", "fr"]).set_index("d"); d_.index = pd.to_datetime(d_.index); dc[t] = d_.c.where(d_.c > 0)
        daily_close = pd.DataFrame(dc).reindex(daily_close.index)
    PC = daily_close.shift(1)                                     # 전날 종가
    M = {n: [c for c in cs if c in C.columns] for n, cs in M.items()}; M = {n: cs for n, cs in M.items() if len(cs) >= 3}
    cost = 0.0025 if mk == "kr" else 0.001; lim = 0.29 if mk == "kr" else None
    print(f"\n===== {'한국' if mk == 'kr' else '미국'} 테마 대장주 · 테마 {len(M)}개 · 종목 {C.shape[1]} · {len(set(C.index.date))}일 · 왕복 비용 {cost:.2%}")
    for lab, kw in [("기본: 대장 바뀌면 바로 갈아탐", {}), ("새 대장이 1%p 이상 앞설 때만", dict(edge=0.01)), ("새 대장이 3%p 이상 앞설 때만", dict(edge=0.03)),
                    ("30분 지나고 시작(첫 6봉 건너뜀)", dict(start=6, edge=0.01)), ("테마 = 상위 3종목 평균", dict(theme_mode="top3", edge=0.01))]:
        R = sim(M, O, C, PC, cost, lim=lim, **kw)
        if not len(R):
            continue
        eq = (1 + R.pnl).cumprod()
        print(f"  {lab:<28} 하루 평균 {R.pnl.mean() * 100:+.2f}% · 이긴 날 {(R.pnl > 0).mean():.0%} · 하루 갈아탄 횟수 {R.sw.mean():.1f}번 · {len(R)}일 누적 {eq.iloc[-1] - 1:+.1%} · 최대 낙폭 {(eq / eq.cummax() - 1).min():.1%} · 비용 빼기 전 하루 {(R.pnl.mean() + cost * (1 + R.sw.mean())) * 100:+.2f}%")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "us")
