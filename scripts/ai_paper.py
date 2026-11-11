"""
AI 모의 트레이딩 (Claude가 가상 $10,000로 스스로 판단해서 매매)
  · 판단: Claude가 매일 아침(한국 시간) 시장·순위·뉴스를 보고 주문을 냄 → 이 스크립트의 order/cancel/note 명령으로 기록
  · 체결: 미국장 중 30분마다 GitHub Actions가 5분봉으로 주문을 처리 (Claude가 없어도 손절·익절·지정가가 알아서 체결)
      시장가 = 주문 뒤 첫 5분봉 시가 · 지정가 매수 = 저가가 지정가 이하 · 스톱 매수 = 고가가 스톱 이상 (갭이면 시가)
      보유 종목: 손절가(저가 ≤ 손절) → 익절가(고가 ≥ 익절) 순서로 확인, 같은 봉에서 둘 다 닿으면 손절로 봄(보수적)
  · 비용: 매매마다 수수료 0.1% + 체결 차이 0.05%
  · 스스로 지키는 규칙 (주문 때 검사): 한 종목 최대 계좌의 20% · 최대 8종목 · 모든 매수에 손절가 필수 · 한 번에 잃을 수 있는 돈 ≤ 계좌의 1.5%
명령:
  python scripts/ai_paper.py fill                  # 체결 처리 + 평가 (Actions가 실행)
  python scripts/ai_paper.py order SYM buy --usd 1500 [--type market|limit|stop --px 210] --stop 190 [--target 260] [--days 3] --why "이유"
  python scripts/ai_paper.py order SYM sell [--pct 100] [--type market|limit --px] --why "이유"
  python scripts/ai_paper.py modify SYM [--stop X] [--target Y] --why "이유"
  python scripts/ai_paper.py cancel ID --why "이유"
  python scripts/ai_paper.py note "오늘의 판단 요약"
"""
import argparse, json, math, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data/us/ai_paper_state.json"
VIEW = ROOT / "data/us/ai_paper.json"
KST = timezone(timedelta(hours=9))
FEE, SLIP = 0.001, 0.0005
MAX_W, MAX_N, MAX_RISK = 0.20, 8, 0.015


def now():
    return datetime.now(timezone.utc)


def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    t = now().isoformat()
    return {"start": t, "cash": 10000.0, "pos": {}, "orders": [], "trades": [], "journal": [], "eq": [], "last": t, "seq": 0, "px": {}}


def save(S):
    S["journal"] = S["journal"][-400:]
    STATE.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    view(S)


def equity(S):
    return S["cash"] + sum(p["sh"] * S["px"].get(t, p["avg"]) for t, p in S["pos"].items())   # px에는 SPY 비교용 가격도 있음(보유와 무관)


def log(S, kind, text, **kw):
    S["journal"].append({"at": now().astimezone(KST).strftime("%Y-%m-%d %H:%M"), "k": kind, "text": text, **kw})


# ---------------- 판단 기록 (Claude가 실행) ----------------
def last_price(sym):
    import yfinance as yf
    h = yf.Ticker(sym).history(period="5d", interval="1d")
    return float(h["Close"].iloc[-1]) if len(h) else None


def cmd_order(S, a):
    sym = a.sym.upper()
    if a.side == "buy":
        if a.stop is None:
            sys.exit("규칙: 매수에는 손절가가 꼭 있어야 해요 (--stop)")
        px = a.px or S["px"].get(sym) or last_price(sym)
        eq = equity(S)
        usd = a.usd
        held = S["pos"].get(sym, {}).get("sh", 0) * px
        if held + usd > eq * MAX_W + 1:
            sys.exit(f"규칙: 한 종목 최대 {MAX_W:.0%} (지금 {held:.0f} + 주문 {usd:.0f} > {eq * MAX_W:.0f})")
        names = set(S["pos"]) | {o["sym"] for o in S["orders"] if o["side"] == "buy"}
        if sym not in names and len(names) >= MAX_N:
            sys.exit(f"규칙: 최대 {MAX_N}종목")
        risk = usd * (px - a.stop) / px
        if risk > eq * MAX_RISK + 1:
            sys.exit(f"규칙: 한 번에 잃을 수 있는 돈 ≤ 계좌의 {MAX_RISK:.1%} (이 주문은 손절 시 ${risk:.0f} > ${eq * MAX_RISK:.0f}) → 금액을 줄이거나 손절을 가깝게")
        if a.stop >= px:
            sys.exit("손절가가 매수가보다 높아요")
    S["seq"] += 1
    o = {"id": S["seq"], "sym": sym, "side": a.side, "type": a.type, "px": a.px, "usd": a.usd, "pct": a.pct, "stop": a.stop, "target": a.target,
         "why": a.why, "at": now().isoformat(), "exp": (now() + timedelta(days=a.days)).isoformat()}
    S["orders"].append(o)
    log(S, "order", a.why, sym=sym, side=a.side, detail=desc(o))
    print("주문:", desc(o))


def desc(o):
    s = f"{'매수' if o['side'] == 'buy' else '매도'} {o['sym']} "
    s += f"${o['usd']:,.0f}" if o["side"] == "buy" else f"{o.get('pct') or 100:.0f}%"
    s += {"market": " 시장가", "limit": f" 지정가 ${o['px']}", "stop": f" ${o['px']} 넘으면"}[o["type"]]
    if o.get("stop"): s += f" · 손절 ${o['stop']}"
    if o.get("target"): s += f" · 익절 ${o['target']}"
    return s


def cmd_modify(S, a):
    p = S["pos"].get(a.sym.upper())
    if not p:
        sys.exit("보유하지 않은 종목")
    old = (p.get("stop"), p.get("target"))
    if a.stop is not None: p["stop"] = a.stop
    if a.target is not None: p["target"] = a.target
    log(S, "modify", a.why, sym=a.sym.upper(), detail=f"손절 {old[0]}→{p.get('stop')} · 익절 {old[1]}→{p.get('target')}")


def cmd_cancel(S, a):
    o = next((o for o in S["orders"] if o["id"] == a.id), None)
    if not o:
        sys.exit("없는 주문")
    S["orders"].remove(o)
    log(S, "cancel", a.why, sym=o["sym"], detail=desc(o))


# ---------------- 체결 (Actions가 실행) ----------------
def bars5(syms, since):
    import yfinance as yf, pandas as pd
    out = {}
    if not syms:
        return out
    df = yf.download(sorted(syms), period="5d", interval="5m", group_by="ticker", auto_adjust=False, progress=False, threads=True, prepost=False)
    for s in syms:
        try:
            d = df[s] if isinstance(df.columns, pd.MultiIndex) else df
            d = d.dropna(subset=["Open", "High", "Low", "Close"])
            rows = [(ix.to_pydatetime().astimezone(timezone.utc), float(r.Open), float(r.High), float(r.Low), float(r.Close)) for ix, r in d.iterrows()]
            out[s] = [r for r in rows if r[0] + timedelta(minutes=5) > since]
        except Exception:
            out[s] = []
    return out


def fill_buy(S, o, t, px):
    px *= 1 + SLIP
    usd = min(o["usd"], S["cash"] / (1 + FEE))
    if usd < 10:
        log(S, "skip", "현금 부족으로 주문 취소", sym=o["sym"]); return
    sh = usd / px
    S["cash"] -= usd * (1 + FEE)
    p = S["pos"].get(o["sym"])
    if p:
        p["avg"] = (p["avg"] * p["sh"] + px * sh) / (p["sh"] + sh); p["sh"] += sh
    else:
        p = S["pos"][o["sym"]] = {"sh": sh, "avg": px, "since": t.isoformat(), "why": o["why"]}
    if o.get("stop"): p["stop"] = o["stop"]
    if o.get("target"): p["target"] = o["target"]
    log(S, "fill", f"매수 체결 ${px:,.2f} × {sh:.4f}주", sym=o["sym"], side="buy", t=t.isoformat())


def fill_sell(S, sym, t, px, frac, why):
    p = S["pos"].get(sym)
    if not p:
        return
    px *= 1 - SLIP
    sh = p["sh"] * frac
    S["cash"] += sh * px * (1 - FEE)
    pl = px * (1 - FEE) / (p["avg"] * (1 + FEE)) - 1
    S["trades"].append({"sym": sym, "in": p["since"][:10], "out": t.astimezone(KST).strftime("%Y-%m-%d"), "avg": round(p["avg"], 2), "px": round(px, 2),
                        "pl": round(pl, 4), "usd": round(sh * (px - p["avg"]), 2), "why": why, "entry_why": p.get("why")})
    p["sh"] -= sh
    if p["sh"] < 1e-6 or frac >= 0.999:
        del S["pos"][sym]
    log(S, "fill", f"매도 체결 ${px:,.2f} ({pl * 100:+.1f}%) — {why}", sym=sym, side="sell", t=t.isoformat())


def cmd_fill(S):
    since = datetime.fromisoformat(S["last"])
    syms = set(S["pos"]) | {o["sym"] for o in S["orders"]} | {"SPY"}       # SPY는 같은 기간 비교용
    B = bars5(syms, since)
    events = sorted((r[0], s, r) for s, rows in B.items() for r in rows)
    for t, s, (_, o_, h, l, c) in events:
        S["px"][s] = c
        if s == "SPY" and not S.get("bench0"):
            S["bench0"] = o_
        # 보유: 손절 → 익절
        p = S["pos"].get(s)
        if p:
            if p.get("stop") and l <= p["stop"]:
                fill_sell(S, s, t, min(o_, p["stop"]), 1, "손절가 도달")
            elif p.get("target") and h >= p["target"]:
                fill_sell(S, s, t, max(o_, p["target"]), 1, "익절가 도달")
        # 주문
        for od in [x for x in S["orders"] if x["sym"] == s]:
            if t + timedelta(minutes=5) <= datetime.fromisoformat(od["at"]):
                continue
            done = False
            if od["side"] == "buy":
                if od["type"] == "market": fill_buy(S, od, t, o_); done = True
                elif od["type"] == "limit" and l <= od["px"]: fill_buy(S, od, t, min(o_, od["px"])); done = True
                elif od["type"] == "stop" and h >= od["px"]: fill_buy(S, od, t, max(o_, od["px"])); done = True
            else:
                frac = (od.get("pct") or 100) / 100
                if od["type"] == "market": fill_sell(S, s, t, o_, frac, od["why"]); done = True
                elif od["type"] == "limit" and h >= od["px"]: fill_sell(S, s, t, max(o_, od["px"]), frac, od["why"]); done = True
            if done:
                S["orders"].remove(od)
    for od in list(S["orders"]):
        if now() > datetime.fromisoformat(od["exp"]):
            S["orders"].remove(od); log(S, "expire", "기한 지나 주문 취소", sym=od["sym"], detail=desc(od))
    if events:
        S["last"] = max(e[0] for e in events).isoformat()
    day = (datetime.fromisoformat(S["last"]) - timedelta(hours=5)).strftime("%Y-%m-%d")      # 뉴욕 날짜
    e = round(equity(S), 2)
    if S["eq"] and S["eq"][-1][0] == day:
        S["eq"][-1][1] = e
    else:
        S["eq"].append([day, e])
    print(f"AI 계좌 ${e:,.2f} · 보유 {len(S['pos'])} · 대기 주문 {len(S['orders'])}")


def view(S):
    e = equity(S)
    tr = S["trades"]; w = [x for x in tr if x["pl"] > 0]
    out = {"start": S["start"][:10], "cash0": 10000, "eq_now": round(e, 2), "cash": round(S["cash"], 2), "eq": S["eq"],
           "pos": [{"sym": t, "sh": round(p["sh"], 4), "avg": round(p["avg"], 2), "px": S["px"].get(t), "pl": (S["px"].get(t, p["avg"]) / p["avg"] - 1),
                    "val": round(p["sh"] * S["px"].get(t, p["avg"]), 2), "stop": p.get("stop"), "target": p.get("target"), "since": p["since"][:10], "why": p.get("why")}
                   for t, p in S["pos"].items()],
           "orders": [{**o, "desc": desc(o)} for o in S["orders"]], "trades": tr[::-1][:100], "journal": S["journal"][::-1][:150],
           "stats": {"n": len(tr), "win": len(w) / len(tr) if tr else None},
           "bench": (S["px"]["SPY"] / S["bench0"] - 1) if S.get("bench0") and S["px"].get("SPY") else None,
           "rules": f"한 종목 최대 {MAX_W:.0%} · 최대 {MAX_N}종목 · 모든 매수에 손절가 · 한 번에 잃을 수 있는 돈 ≤ 계좌의 {MAX_RISK:.1%} · 수수료 0.1% + 체결 차이 0.05%"}
    VIEW.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=str))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("fill")
    o = sp.add_parser("order"); o.add_argument("sym"); o.add_argument("side", choices=["buy", "sell"])
    o.add_argument("--usd", type=float, default=0); o.add_argument("--pct", type=float); o.add_argument("--type", default="market", choices=["market", "limit", "stop"])
    o.add_argument("--px", type=float); o.add_argument("--stop", type=float); o.add_argument("--target", type=float); o.add_argument("--days", type=float, default=2)
    o.add_argument("--why", required=True)
    m = sp.add_parser("modify"); m.add_argument("sym"); m.add_argument("--stop", type=float); m.add_argument("--target", type=float); m.add_argument("--why", required=True)
    c = sp.add_parser("cancel"); c.add_argument("id", type=int); c.add_argument("--why", required=True)
    n = sp.add_parser("note"); n.add_argument("text")
    a = ap.parse_args()
    S = load()
    if a.cmd == "fill": cmd_fill(S)
    elif a.cmd == "order": cmd_order(S, a)
    elif a.cmd == "modify": cmd_modify(S, a)
    elif a.cmd == "cancel": cmd_cancel(S, a)
    elif a.cmd == "note": log(S, "note", a.text)
    save(S)


if __name__ == "__main__":
    main()
