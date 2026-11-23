"""
한국 주식 모의 계좌 (11/23 형: "미국이랑 한국 같이 운영해")
가상 1,000만 원 · 코스피·코스닥 300종목(data/rank/universe.json) · 일봉 · 장 마감 뒤 하루 한 번 (.github/workflows/kr.yml, 15:50 한국 시간 + 예비)

규칙 고른 과정 (research/kr/bt.py, 2015~2026 한국 300종목, 비용·거래세 포함):
  미국 주식 계좌 규칙 그대로(점수 0.6↑ 눌림 매수) → 연 −3.6% · 최대 낙폭 −66% (코스피 그냥 보유 +7.8% · −48%) → 탈락
  주도주 돌파 + 코스피 200일선 위만 → 연 +19.9% · 최대 낙폭 −38% · 11년 중 마이너스 1해 · 앞 5년 +13.5% / 뒤 5년 +27.6% → 채택
  ※ 지금 300종목으로 과거를 시험해서(생존 편향) 실제보다 좋게 나왔을 수 있음

규칙 (주도주 돌파, 오닐식):
  매수 신호(장 마감 기준): 종가가 52주 신고가 첫 돌파(직전 20일 안 첫 돌파) + 거래량 ≥ 50일 평균 × 1.5 + 상대강도(RS, 300종목 중 순위) 80↑
           + 하루 거래대금 약 28억 원↑ · 주가 1,000원↑ + 코스피가 200일선 위 (아래면 새로 안 삼)
           여러 개면 '2년 바닥 대비 2~3배'인 것 먼저, 그다음 RS 높은 순 · 하루 최대 2종목
  매수: 다음 날 시가 · 크기 = 한 번 손절 시 계좌 −2% (손절 7% → 계좌의 약 28%) 와 계좌의 20% 중 작은 것 · 최대 8종목 · 현금 20% 남김
  손절: 산 가격 −7% (장중 저가가 닿으면, 갭이면 시가)
  매도: RS 70 아래 + 종가 50일선 아래로 마감 → 다음 날 시가
  비용: 사고팔 때 수수료 0.015% + 체결 차이 0.05%, 팔 때 거래세 0.2%
"""
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/kr/kr_paper.json"
KST = timezone(timedelta(hours=9))
CASH0 = 10_000_000
BUY_C, SELL_C = 0.00015 + 0.0005, 0.00015 + 0.002 + 0.0005
STOP, RISK, MAXW, MAXN, CASHMIN, NEWMAX = 0.07, 0.02, 0.20, 8, 0.20, 2
sys.path.insert(0, str(Path(__file__).resolve().parent))


def now():
    return datetime.now(KST)


def say(S, who, text):
    S["chat"].append({"at": now().isoformat(timespec="seconds"), "who": who, "text": text}); S["chat"] = S["chat"][-400:]


def won(x):
    return f"{x:,.0f}원"


def load_data():
    import yfinance as yf
    U = json.loads((ROOT / "data/rank/universe.json").read_text())
    tk = {c + (".KS" if m == "KOSPI" else ".KQ"): n for c, n, m in U}
    P = yf.download(list(tk) + ["^KS11"], period="3y", auto_adjust=True, group_by="ticker", progress=False, threads=True)
    W = lambda k: pd.DataFrame({t: P[t][k] for t in tk if t in P.columns.get_level_values(0)})
    O, H, L, C, V = W("Open"), W("High"), W("Low"), W("Close"), W("Volume")
    C = C.dropna(how="all", axis=1); O, H, L, V = (X[C.columns] for X in (O, H, L, V))
    C = C.dropna(how="all"); O, H, L, V = (X.reindex(C.index) for X in (O, H, L, V))
    ks = P["^KS11"]["Close"].reindex(C.index).ffill()
    C.index = O.index = H.index = L.index = V.index = ks.index = pd.DatetimeIndex(C.index).tz_localize(None).normalize()
    return tk, O, H, L, C.ffill(), V, ks


def run():
    S = json.loads(OUT.read_text()) if OUT.exists() else None
    tk, O, H, L, C, V, ks = load_data()
    t = now()
    done_day = pd.Timestamp(t.date()) if (t.hour, t.minute) >= (15, 45) else pd.Timestamp(t.date()) - pd.Timedelta(days=1)
    days = [d for d in C.index if d <= done_day]
    hi252 = H.rolling(252, min_periods=200).max().shift(1)
    brk = (C > hi252) & ~((C > hi252).rolling(20, min_periods=1).max().shift(1).fillna(0).astype(bool))
    v50 = V.rolling(50).mean().shift(1)
    rs = (0.4 * C / C.shift(63) + 0.2 * C / C.shift(126) + 0.2 * C / C.shift(189) + 0.2 * C / C.shift(252)).rank(axis=1, pct=True) * 99
    m50 = C.rolling(50).mean(); base = C / L.rolling(504, min_periods=300).min(); dv = (C * V).rolling(20).mean()
    k200 = ks.rolling(200).mean()
    if not S:
        S = {"start": str(days[-1].date()), "cash0": CASH0, "cash": float(CASH0), "pos": {}, "orders": [], "trades": [], "journal": [], "chat": [], "eq": [],
             "last": str(days[-2].date()), "rule": "주도주 돌파: 52주 신고가 첫 돌파 + 거래량 50일 평균 1.5배↑ + 상대강도 80↑ + 코스피 200일선 위 → 다음 날 시가 · 손절 −7% · RS 70↓+50일선 이탈 매도 · 한 번 손절 시 계좌 −2%"}
        say(S, "claude", "── 한국 주식 계좌 개설 · 가상 1,000만 원 · 코스피·코스닥 300종목 · 주도주 돌파 규칙 (11/23 형 결정: 미국·한국 같이) ──")
        say(S, "analyst", "같은 규칙 시험(2015~): 미국 계좌 규칙 그대로는 연 −3.6%로 탈락, 주도주 돌파+코스피 200일선 위만 → 연 +19.9%·최대 낙폭 −38% (코스피 +7.8%). 지금 종목으로 과거를 시험해서 실제는 더 나쁠 수 있어요.")
    last = pd.Timestamp(S["last"])
    for d in [x for x in days if x > last]:
        i = C.index.get_loc(d); ds = str(d.date())
        # 1) 시가: 어제 낸 매수 주문 · 매도 예약
        for sym in [s for s, p in S["pos"].items() if p.get("sell_next")]:
            px = O.at[d, sym]
            if np.isfinite(px):
                close(S, sym, float(px), ds, S["pos"][sym]["sell_next"], tk)
        new = []
        for o in S["orders"]:
            sym = o["sym"]; px = O.at[d, sym]
            if sym in S["pos"] or len(S["pos"]) >= MAXN or not np.isfinite(px):
                continue
            eq = equity(S, C, i - 1)
            krw = min(eq * RISK / STOP, eq * MAXW, S["cash"] - eq * CASHMIN)
            if krw < 300_000:
                say(S, "risk", f"{tk.get(sym, sym)} 매수 못 함 — 현금 20% 유지 규칙 (남은 현금 {won(S['cash'])})"); continue
            fill = float(px) * (1 + 0.0005); sh = int(krw // fill)
            if sh < 1:
                continue
            S["cash"] -= sh * fill * (1 + 0.00015)
            jid = len(S["journal"])
            S["pos"][sym] = dict(name=tk.get(sym, sym), sh=sh, entry=fill, stop=round(fill * (1 - STOP)), since=ds, jid=jid, why=o["why"], feat=o.get("feat"))
            S["journal"].append(dict(id=jid, sym=sym, name=tk.get(sym, sym), side="롱", in_at=ds, fill=round(fill), stop=round(fill * (1 - STOP)), why_in=o["why_list"], feat=o.get("feat"), exit=None))
            new.append(sym)
            say(S, "executor", f"{tk.get(sym, sym)} 매수 {sh}주 @ {won(fill)} (시가) = {won(sh * fill)} · 손절 {won(fill * (1 - STOP))} (−7%) — {o['why']}")
        S["orders"] = []
        # 2) 장중: 손절
        for sym in list(S["pos"]):
            p = S["pos"][sym]; lo = L.at[d, sym]; op = O.at[d, sym]
            if np.isfinite(lo) and lo <= p["stop"]:
                xp = min(float(op), p["stop"]) if sym not in new and np.isfinite(op) else p["stop"]
                close(S, sym, xp, ds, "손절 −7%", tk)
        # 3) 종가: 매도 신호 · 새 매수 신호
        for sym, p in S["pos"].items():
            if rs.at[d, sym] < 70 and C.at[d, sym] < m50.at[d, sym]:
                p["sell_next"] = f"추세 꺾임 — RS {rs.at[d, sym]:.0f}(70 아래) + 종가 50일선 아래"
                say(S, "risk", f"{p['name']} 내일 시가 매도 예약 — {p['sell_next']}")
        up = ks.iat[i] > k200.iat[i]
        if up and len(S["pos"]) < MAXN:
            ok = brk.iloc[i] & (V.iloc[i] >= 1.5 * v50.iloc[i]) & (rs.iloc[i] >= 80) & (dv.iloc[i] >= 2.8e9) & (C.iloc[i] >= 1000)
            js = [s for s in ok[ok].index if s not in S["pos"]]
            js = sorted(js, key=lambda s: (-int(2 <= base.at[d, s] < 3), -rs.at[d, s]))[:NEWMAX]
            for s in js:
                why_list = [f"52주 신고가 첫 돌파 — 종가 {won(C.at[d, s])} > 1년 최고 {won(hi252.at[d, s])}",
                            f"거래량 {V.at[d, s] / v50.at[d, s]:.1f}배 (50일 평균 대비, 기준 1.5배)",
                            f"상대강도 RS {rs.at[d, s]:.0f} (300종목 중 상위 {100 - rs.at[d, s]:.0f}%)",
                            f"2년 바닥 대비 {base.at[d, s]:.1f}배" + (" (2~3배 — 우선)" if 2 <= base.at[d, s] < 3 else ""),
                            f"코스피 {ks.iat[i]:,.0f} > 200일선 {k200.iat[i]:,.0f} (시장 상승 국면)"]
                S["orders"].append(dict(sym=s, why=f"신고가 돌파·거래량 {V.at[d, s] / v50.at[d, s]:.1f}배·RS {rs.at[d, s]:.0f}", why_list=why_list,
                                        feat=dict(rs=round(float(rs.at[d, s]), 1), vr=round(float(V.at[d, s] / v50.at[d, s]), 2), base=round(float(base.at[d, s]), 2),
                                                  ext50=round(float(C.at[d, s] / m50.at[d, s] - 1) * 100, 1), kospi200=round(float(ks.iat[i] / k200.iat[i] - 1) * 100, 1))))
                say(S, "scout", f"{tk.get(s, s)} 매수 신호 → 다음 거래일 시가에 매수 · " + " · ".join(why_list[:3]))
        elif not up:
            if not S.get("_down_said") or S["_down_said"] != ds:
                say(S, "analyst", f"{ds} 코스피 {ks.iat[i]:,.0f} < 200일선 {k200.iat[i]:,.0f} → 새 매수 안 함 (보유 종목 손절·매도 규칙은 그대로)"); S["_down_said"] = ds
        eq = equity(S, C, i)
        S["eq"].append([ds, round(eq)]); S["last"] = ds
    i = len(days) - 1
    eq = equity(S, C, C.index.get_loc(days[-1]))
    k0 = ks.loc[pd.Timestamp(S["start"])] if pd.Timestamp(S["start"]) in ks.index else ks.iloc[-1]
    view_pos = [dict(sym=s, name=p["name"], sh=p["sh"], entry=round(p["entry"]), px=round(float(C[s].iloc[-1])), pl=float(C[s].iloc[-1] / p["entry"] - 1),
                     stop=p["stop"], since=p["since"], why=p["why"], sell_next=p.get("sell_next")) for s, p in S["pos"].items()]
    S.update(eq_now=round(eq), made=now().isoformat(timespec="minutes"), bench=float(ks.iloc[-1] / k0 - 1), kospi=float(ks.iloc[-1]), kospi200=float(k200.iloc[-1]),
             view_pos=view_pos, n_trades=len(S["trades"]))
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":"), default=float))
    print(f"한국 주식 계좌 {won(eq)} ({eq / CASH0 - 1:+.2%}) 보유 {[p['name'] for p in S['pos'].values()]} 내일 주문 {[o['sym'] for o in S['orders']]}")


def equity(S, C, i):
    return S["cash"] + sum(p["sh"] * float(C[s].iat[i]) for s, p in S["pos"].items() if np.isfinite(C[s].iat[i]))


def close(S, sym, xp, ds, why, tk):
    p = S["pos"].pop(sym); xp = xp * (1 - 0.0005)
    S["cash"] += p["sh"] * xp * (1 - 0.00015 - 0.002)
    pl = xp * (1 - 0.00215) / p["entry"] - 1
    J = S["journal"][p["jid"]]
    R = pl / STOP
    J.update(exit=round(xp), out_at=ds, why_out=why, pl=round(pl, 4), R=round(R, 2), pnl=round(p["sh"] * p["entry"] * pl))
    S["trades"].append(dict(sym=sym, name=p["name"], **{"in": p["since"], "out": ds}, entry=round(p["entry"]), exit=round(xp), pl=round(pl, 4), R=round(R, 2),
                            usd=None, krw=round(p["sh"] * p["entry"] * pl), why=why, entry_why=p["why"], feat=p.get("feat")))
    say(S, "executor", f"{p['name']} 매도 @ {won(xp)} · {pl * 100:+.1f}% ({R:+.2f}R) — {why}")


if __name__ == "__main__":
    run()
