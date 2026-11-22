"""
코인 10배 '추세 눌림' 모의 계좌 (11/22 형 요청: 10배 단타 평균 회귀를 접고 다른 방법으로 다시 시작)
가상 $10,000, BTC·ETH·SOL 1시간봉. 매시간 GitHub Actions(.github/workflows/ob.yml)에서 밀린 봉까지 순서대로 처리.
규칙 (research/orderblock/alt.py 1시간봉 2년 시험에서 고름 — 코인 3개 모두 플러스, 6개월 단위 12칸 중 10칸 플러스):
  방향: EMA50 > EMA200 이고 종가 > EMA200 이면 롱만, 반대면 숏만 (추세 쪽으로만)
  진입: 그 봉 저가가 EMA20까지 눌렸다가 양봉으로 마감 + 직전 RSI(14) < 50 → 다음 봉 시가 진입 (숏은 반대)
  손절: 진입가 − ATR(14)×1.5 · 추적 손절: 진입 뒤 최고가 − ATR×5 (손절선은 유리한 쪽으로만 이동) · 최대 96봉
  크기: 한 번 손절 시 계좌 손실 1% (손실 최소화) · 노출은 계좌의 최대 10배 (10배 레버리지 = 증거금 한도)
  비용: 한쪽 0.05%. 시험 성적: 거래당 평균 +0.16R(수수료 0.05%) — 과거 결과라 앞으로는 더 나쁠 수 있음
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import formula_rules as FR
FC = None
CTX = {}

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us/trend10.json"
SYMS = ["BTC-USD", "ETH-USD", "SOL-USD"]
# 11/22 저녁: 1회 손실 1% → 0.25% (Claude 결정 — 2년 시험 최대 낙폭 −63% → 약 −20%, 형 원칙 '손실 최소화 먼저')
CFG = dict(sm=1.5, tr=5.0, mx=96, rsi=50, risk=0.0025, maxE=10.0, fee=0.0005)
NM = {"BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL"}


def now():
    return datetime.now(timezone.utc)


def bars(sym):
    d = yf.Ticker(sym).history(period="180d", interval="1h").dropna()
    d.index = d.index.tz_convert("UTC"); d.columns = [c.lower() for c in d.columns]
    d = d[d.index + pd.Timedelta(hours=1) <= pd.Timestamp(now())]
    return d[["open", "high", "low", "close", "volume"]]


def ind(d):
    c = d.close; e = lambda n: c.ewm(span=n, adjust=False).mean()
    dl = c.diff(); u = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); v = (-dl.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    pc = c.shift(); tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return dict(e20=e(20).values, e50=e(50).values, e200=e(200).values, rsi=(100 - 100 / (1 + u / v)).values, atr=tr.ewm(alpha=1 / 14, adjust=False).mean().values)


def say(S, who, text):
    S["chat"].append({"at": now().isoformat(timespec="seconds"), "who": who, "text": text}); S["chat"] = S["chat"][-400:]


def f(x):
    return f"{x:,.2f}" if x < 1000 else f"{x:,.0f}"


def equity(S, px):
    return S["cash"] + sum(p["qty"] * (px.get(s, p["entry"]) - p["entry"]) * p["side"] for s, p in S["pos"].items())


def run():
    FC = FR.load(); CFG.update(FR.params("tr10"))                # 코치(scripts/coach.py)가 바꾼 숫자·조건
    S = json.loads(OUT.read_text()) if OUT.exists() else None
    if not S:
        S = {"start": now().date().isoformat(), "cash": 10000.0, "pos": {}, "trades": [], "chat": [], "eq": [], "last": {}, "lev": 10,
             "rule": "1시간봉 추세 눌림: EMA50·EMA200 추세 쪽으로만, EMA20까지 눌렸다 반등 마감(RSI<50 뒤)에 진입 · 손절 ATR×1.5 · 추적 손절 ATR×5 · 1회 손실 계좌 1% · 노출 최대 10배"}
        say(S, "claude", "── 코인 10배 '추세 눌림' 계좌 개설 · 가상 $10,000 · BTC·ETH·SOL 1시간봉 (평균 회귀 단타는 11/22 종료) ──")
    px = {}
    for sym in SYMS:
        try:
            d = bars(sym)
        except Exception as e:
            print(sym, "시세 실패", e); continue
        if len(d) < 220:
            continue
        I = ind(d); o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values; t = d.index
        X = FR.context(d)
        px[sym] = float(c[-1])
        last = pd.Timestamp(S["last"].get(sym)) if S["last"].get(sym) else t[-2]
        for k in range(210, len(d)):
            if t[k] <= last:
                continue
            tk = t[k].isoformat(); A = I["atr"]
            p = S["pos"].get(sym)
            if p:                                                         # 손절·추적 손절·시간
                s = p["side"]; p["bars"] += 1
                hit = l[k] <= p["stop"] if s > 0 else h[k] >= p["stop"]
                if hit:
                    xp = min(o[k], p["stop"]) if s > 0 else max(o[k], p["stop"])
                    close(S, sym, float(xp), "추적 손절" if p["trailed"] else "손절 (ATR×1.5)", tk)
                else:
                    p["best"] = float(max(p["best"], h[k]) if s > 0 else min(p["best"], l[k]))
                    trail = p["best"] - s * CFG["tr"] * A[k]
                    if (s > 0 and trail > p["stop"]) or (s < 0 and trail < p["stop"]):
                        p["stop"] = float(trail); p["trailed"] = True
                    if p["bars"] >= CFG["mx"]:
                        close(S, sym, float(c[k]), f"최대 보유 {CFG['mx']}봉 — 시간 정리", tk)
                if S["pos"].get(sym):
                    continue
            # 진입 신호: 봉 k-1 마감 기준 → 봉 k 시가 진입
            j = k - 1
            up = I["e50"][j] > I["e200"][j] and c[j] > I["e200"][j]; dn = I["e50"][j] < I["e200"][j] and c[j] < I["e200"][j]
            s = 0
            if up and l[j] <= I["e20"][j] and c[j] > o[j] and I["rsi"][j - 1] < CFG["rsi"]:
                s = 1
            elif dn and h[j] >= I["e20"][j] and c[j] < o[j] and I["rsi"][j - 1] > 100 - CFG["rsi"]:
                s = -1
            if not s:
                continue
            e = float(o[k]); risk = CFG["sm"] * A[j]; stop = e - s * risk
            bad = FR.check("tr10", dict(t=t[k], htf=X["htf"][j] == s, volhi=bool(X["volhi"][j]), risk=risk / e), FC)
            if bad:
                S.setdefault("skips", []).append({"at": tk, "sym": sym, "side": s, "why": " · ".join(bad)}); S["skips"] = S["skips"][-200:]
                continue
            eq = equity(S, {}); qty = min(eq * CFG["risk"] / risk, eq * CFG["maxE"] / e)
            fee = qty * e * CFG["fee"]; S["cash"] -= fee
            why = (f"{'상승' if s > 0 else '하락'} 추세(EMA50 {f(I['e50'][j])} {'>' if s > 0 else '<'} EMA200 {f(I['e200'][j])}) 안에서 "
                   f"EMA20({f(I['e20'][j])})까지 {'눌렸다 양봉' if s > 0 else '반등했다 음봉'} 마감 · 직전 RSI {I['rsi'][j - 1]:.0f}")
            S["pos"][sym] = dict(side=s, qty=float(qty), entry=e, stop=float(stop), stop0=float(stop), best=e, trailed=False, bars=0, at=tk, fee=float(fee), why=why,
                                 feat=FR.feat(X, j, s, t[k], risk / e),
                                 risk_usd=float(qty * risk), expo=round(float(qty * e / eq), 2))
            say(S, "executor", f"{NM[sym]} {'롱' if s > 0 else '숏'} {f(e)} — {why} · 손절 {f(stop)} ({risk / e * 100:.2f}%) · 계좌의 {qty * e / eq:.1f}배 노출")
        S["last"][sym] = t[-1].isoformat()
    eq = equity(S, px)
    S["eq"].append([now().isoformat(timespec="minutes"), round(eq, 2)]); S["eq"] = S["eq"][-3000:]
    S.update(eq_now=round(eq, 2), px=px, made=now().isoformat(timespec="minutes"), n_trades=len(S["trades"]), coach=FR.active_text("tr10", FC))
    OUT.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    print("추세 눌림 계좌", round(eq, 2), "보유", list(S["pos"]), "거래", len(S["trades"]))


def close(S, sym, xp, why, tk):
    p = S["pos"].pop(sym); s = p["side"]
    pnl = p["qty"] * (xp - p["entry"]) * s - p["qty"] * xp * CFG["fee"]
    S["cash"] += pnl; tot = pnl - p["fee"]; R = tot / p["risk_usd"] if p["risk_usd"] else 0
    S["trades"].append(dict(sym=sym, side=s, **{"in": p["at"], "out": tk}, entry=p["entry"], exit=xp, usd=round(tot, 2), R=round(R, 2), feat=p.get("feat"),
                            acct=round(tot / 10000, 5), why=why, entry_why=p["why"], bars=p["bars"], expo=p["expo"]))
    say(S, "risk", f"{NM[sym]} {'롱' if s > 0 else '숏'} 정리 {f(xp)} — {why} · {tot:+,.0f}$ ({R:+.2f}R, {p['bars']}봉 보유)")


if __name__ == "__main__":
    run()
