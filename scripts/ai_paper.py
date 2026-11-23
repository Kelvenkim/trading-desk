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
import argparse, json, math, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data/us/ai_paper_state.json"
VIEW = ROOT / "data/us/ai_paper.json"
KST = timezone(timedelta(hours=9))
FEE, SLIP = 0.001, 0.0005
MAX_W, MAX_N, MAX_RISK = 0.20, 8, 0.02
TRAIL_ON, TRAIL = 0.15, 0.08       # +15% 넘으면 고점 대비 -8% 추적 손절
HALT_DROP = -0.03                  # SPY가 전날 종가 대비 -3%면 새 매수 중단
# 11/23 형: "진짜 AI 에이전트 매매" → 같은 체결 엔진, 따로 계좌 (PAPER_ACCT=agent)
#   판단은 전부 Claude 에이전트(예약 실행, 매일 미국장 열리고 약 50분 뒤) · 자동 관리 규칙(본전 손절·조기 정리·약세 익절·추적 손절)은 끔 → 판단 자체를 시험
#   대신 매수마다 확신 점수(1~5)가 필수, 손절 시 계좌 손실 한도가 확신에 따라 0.5%~1.5% (형 장기 과제 ① 확실한 자리엔 큰 금액 — 데이터 쌓기)
ACCT = os.environ.get("PAPER_ACCT", "ai")
AUTO_MGMT = ACCT != "agent"
CONV_RISK = {1: 0.005, 2: 0.0075, 3: 0.01, 4: 0.0125, 5: 0.015}
# 11/23 형: "에이전트가 하는 건 투자가 아니라 트레이딩" → 매수마다 익절가(최소 1.5R)와 보유 기한(0=당일 청산 ~ 최대 5거래일) 필수,
#   기한 날 뉴욕 15:50 봉에서 자동 청산
MAX_HOLD, MIN_RR, EXIT_HM = 5, 1.5, (15, 50)
if ACCT == "agent":
    STATE = ROOT / "data/us/agent_paper_state.json"
    VIEW = ROOT / "data/us/agent_paper.json"


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


def say(S, who, text, **kw):
    """에이전트 대화방"""
    S.setdefault("chat", []).append({"at": now().astimezone(KST).strftime("%Y-%m-%d %H:%M"), "who": who, "text": text, **kw})
    S["chat"] = S["chat"][-800:]


def log(S, kind, text, **kw):
    S["journal"].append({"at": now().astimezone(KST).strftime("%Y-%m-%d %H:%M"), "k": kind, "text": text, **kw})


# ---------------- 판단 기록 (Claude가 실행) ----------------
def last_price(sym):
    import yfinance as yf
    h = yf.Ticker(sym).history(period="5d", interval="1d")
    return float(h["Close"].iloc[-1]) if len(h) else None


def check(S, sym, side, usd, px, stop, conv=None, target=None, hold=None):
    """Risk 규칙 검사 → 문제 있으면 이유(문자열), 없으면 None"""
    if side != "buy":
        return None if sym in S["pos"] else "보유하지 않은 종목"
    if S.get("halt"):
        return "시장 급락으로 신규 매수 중단 중"
    if stop is None:
        return "매수에는 손절가가 꼭 있어야 해요"
    if stop >= px:
        return "손절가가 매수가보다 높아요"
    eq = equity(S)
    held = S["pos"].get(sym, {}).get("sh", 0) * px
    if held + usd > eq * MAX_W + 1:
        return f"한 종목 최대 {MAX_W:.0%} 초과 (보유 ${held:,.0f} + 주문 ${usd:,.0f} > ${eq * MAX_W:,.0f})"
    names = set(S["pos"]) | {o["sym"] for o in S["orders"] if o["side"] == "buy"}
    if sym not in names and len(names) >= MAX_N:
        return f"최대 {MAX_N}종목 초과"
    if any(o["sym"] == sym and o["side"] == "buy" for o in S["orders"]):
        return "같은 종목 매수 주문이 이미 대기 중 (중복 방지)"
    if ACCT == "agent" and stop < px * 0.93 - 0.01:
        return f"손절이 산 가격의 -7%보다 멀어요 (손절 ${stop} < ${px * 0.93:.2f})"
    risk = usd * (px - stop) / px
    if ACCT == "agent":
        if conv not in CONV_RISK:
            return "에이전트 계좌는 매수마다 확신 점수(--conv 1~5)가 필요해요"
        if hold is None or not 0 <= hold <= MAX_HOLD:
            return f"트레이딩 계좌라 보유 기한(--hold 0~{MAX_HOLD}거래일, 0=당일 청산)이 필요해요"
        if not target or (target - px) < MIN_RR * (px - stop) - 0.01:
            return f"익절가가 필요하고 최소 {MIN_RR}R 이상이어야 해요 (손절 폭 ${px - stop:.2f} → 익절 ${px + MIN_RR * (px - stop):.2f} 이상)"
        if risk > eq * CONV_RISK[conv] + 1:
            return f"확신 {conv} → 손절 시 손실 한도 계좌 {CONV_RISK[conv]:.2%}(${eq * CONV_RISK[conv]:,.0f}) 초과 (지금 ${risk:,.0f})"
    if risk > eq * MAX_RISK + 1:
        return f"손절 시 손실 ${risk:,.0f} > 한도 ${eq * MAX_RISK:,.0f} (계좌 {MAX_RISK:.0%})"
    return None


def place(S, sym, side, usd=0, typ="market", px=None, stop=None, target=None, days=2, why="", pct=None, src=None, score=None, ref=None, sig=None, conv=None, hold=None):
    sym = sym.upper()
    ref = px or ref or S["px"].get(sym) or (last_price(sym) if side == "buy" else None)
    bad = check(S, sym, side, usd, ref, stop, conv, target, hold)
    if bad:
        return None, bad
    S["seq"] += 1
    o = {"id": S["seq"], "sym": sym, "side": side, "type": typ, "px": px, "usd": usd, "pct": pct, "stop": stop, "target": target,
         "why": why, "at": now().isoformat(), "exp": (now() + timedelta(days=days)).isoformat(), "src": src, "score": score, "sig": sig, "conv": conv, "hold": hold}
    S["orders"].append(o)
    log(S, "order", why, sym=sym, side=side, detail=desc(o))
    return o, None


def cmd_order(S, a):
    o, bad = place(S, a.sym, a.side, a.usd, a.type, a.px, a.stop, a.target, a.days, a.why, a.pct, src="AI 에이전트" if ACCT == "agent" else "Claude 직접", conv=a.conv, hold=a.hold)
    if bad:
        sys.exit("규칙 위반: " + bad)
    say(S, "claude", f"{'' if ACCT == 'agent' else '직접 '}주문: {desc(o)}{f' · 확신 {a.conv}/5' if a.conv else ''}{(' · 당일 청산' if a.hold == 0 else f' · 최대 {a.hold}거래일') if a.hold is not None else ''} — {a.why}")
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
        p = S["pos"][o["sym"]] = {"sh": sh, "avg": px, "since": t.isoformat(), "why": o["why"], "src": o.get("src") or "Claude 직접", "score": o.get("score"), "sig": o.get("sig"), "conv": o.get("conv"), "stop0": o.get("stop"), "peak": px}
        if o.get("hold") is not None:
            import numpy as _np
            from zoneinfo import ZoneInfo
            d_ny = t.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
            p["exit_by"] = str(_np.busday_offset(d_ny, int(o["hold"]), roll="forward")); p["hold"] = o["hold"]
    if o.get("stop"): p["stop"] = o["stop"]
    if o.get("target"): p["target"] = o["target"]
    log(S, "fill", f"매수 체결 ${px:,.2f} × {sh:.4f}주", sym=o["sym"], side="buy", t=t.isoformat())
    tn = t.astimezone(timezone(timedelta(hours=-5))).strftime("%H:%M")
    say(S, "executor", f"{o['sym']} 매수 체결됐어요. 뉴욕 {tn}, ${px:,.2f}에 ${usd:,.0f}어치. 손절 ${p.get('stop')}{' · 익절 $' + str(p['target']) if p.get('target') else ''} 걸어뒀어요. @Risk 감시 부탁해요.")


def fill_sell(S, sym, t, px, frac, why):
    p = S["pos"].get(sym)
    if not p:
        return
    px *= 1 - SLIP
    sh = p["sh"] * frac
    S["cash"] += sh * px * (1 - FEE)
    pl = px * (1 - FEE) / (p["avg"] * (1 + FEE)) - 1
    S["trades"].append({"sym": sym, "in": p["since"][:10], "out": t.astimezone(KST).strftime("%Y-%m-%d"), "avg": round(p["avg"], 2), "px": round(px, 2),
                        "pl": round(pl, 4), "usd": round(sh * (px - p["avg"]), 2), "why": why, "entry_why": p.get("why"), "src": p.get("src"), "score": p.get("score"), "sig": p.get("sig"), "conv": p.get("conv"), "hold": p.get("hold"), "R": round((px - p["avg"]) / (p["avg"] - p["stop0"]), 2) if p.get("stop0") and p["avg"] > p["stop0"] else None,
                        "stop_pl": round(p["stop0"] / p["avg"] - 1, 4) if p.get("stop0") else None})
    who = "risk" if ("손절" in why or "추적" in why) else "executor"
    say(S, who, f"{sym} {'전량' if frac >= 0.999 else f'{frac:.0%}'} 매도 — {why}. ${px:,.2f}, 손익 {pl * 100:+.1f}%.")
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
        if s == "SPY":
            if not S.get("bench0"):
                S["bench0"] = o_
            d_ny = (t - timedelta(hours=5)).strftime("%Y-%m-%d")
            if S.get("spy_day") != d_ny:                      # 새 거래일 → 전날 마지막 가격을 기준으로
                S["spy_prev"], S["spy_day"] = S.get("spy_last"), d_ny
            S["spy_last"] = c
        # 위험 감시: SPY 급락이면 새 매수 중단
        if s == "SPY" and S.get("spy_prev") and c <= S["spy_prev"] * (1 + HALT_DROP) and not S.get("halt"):
            S["halt"] = t.isoformat()
            buys = [o for o in S["orders"] if o["side"] == "buy"]
            for o in buys:
                S["orders"].remove(o)
            say(S, "risk", f"🚨 S&P500(SPY)이 전날보다 {c / S['spy_prev'] - 1:+.1%}예요. 새 매수 주문 {len(buys)}건 모두 취소하고 오늘은 신규 진입 막을게요. 보유 종목 손절은 그대로 작동해요.")
        # 보유: 손절 → 익절, +15% 넘으면 추적 손절
        p = S["pos"].get(s)
        if p:
            if p.get("stop") and l <= p["stop"]:
                why = "추적 손절 도달" if p.get("trail") else "본전·수익 확보 손절" if p["stop"] >= p["avg"] else "손절가 도달"
                fill_sell(S, s, t, min(o_, p["stop"]), 1, why)
            elif p.get("target") and h >= p["target"]:
                fill_sell(S, s, t, max(o_, p["target"]), 1, "익절가 도달")
            elif not AUTO_MGMT:
                p["peak"] = max(p.get("peak", p["avg"]), h)
                from zoneinfo import ZoneInfo
                tn = t.astimezone(ZoneInfo("America/New_York"))          # 서머타임 반영
                if p.get("exit_by") and (tn.strftime("%Y-%m-%d") > p["exit_by"] or (tn.strftime("%Y-%m-%d") == p["exit_by"] and (tn.hour, tn.minute) >= EXIT_HM)):
                    fill_sell(S, s, t, o_, 1, "당일 청산 (장 마감 10분 전)" if p.get("hold") == 0 else f"보유 기한 {p.get('hold')}거래일 끝 — 장 마감 10분 전 청산")
                    continue
            else:
                p["peak"] = max(p.get("peak", p["avg"]), h)
                # 본전 손절: +1R(처음 손절 폭만큼 오름) → 손절을 본전+수수료로, +2R → 손절을 +1R로
                p.setdefault("stop0", p.get("stop"))
                R = p["avg"] - (p.get("stop0") or 0)
                # 조기 정리 (11/16 검증): 산 지 5거래일째에 -0.5R 이하면 92%가 결국 손절까지 감 → 그때 정리하면 평균 0.075R 덜 잃음
                if p.get("stop0") and R > 0 and (p.get("stop") or 0) < p["avg"] and c <= p["avg"] - 0.5 * R:
                    import numpy as _np
                    d_buy = p["since"][:10]; d_now = (t - timedelta(hours=5)).strftime("%Y-%m-%d")
                    if _np.busday_count(d_buy, d_now) >= 5:
                        fill_sell(S, s, t, c, 1, f"조기 정리: 5거래일째 -{(p['avg'] - c) / R:.1f}R (이런 경우 92%가 결국 손절)")
                        continue
                if p.get("stop0") and R > 0 and S.get("mode") == "약세" and h >= p["avg"] + R:
                    # 약세장(S&P500 200일선 아래 또는 VIX 28↑)에서는 +1R에서 전량 익절 — 과거 검증상 이쪽이 평균이 더 좋음
                    fill_sell(S, s, t, max(o_, p["avg"] + R), 1, "약세장 +1R 익절")
                    continue
                if p.get("stop0") and R > 0:
                    be = round(p["avg"] * (1 + 2 * (FEE + SLIP)), 2)
                    if p["peak"] >= p["avg"] + R and (p.get("stop") or 0) < be:
                        p["stop"] = be
                        say(S, "risk", f"{s}가 +{R / p['avg']:.1%}(손절 폭만큼) 올랐어요. 손절을 본전 ${be}로 올려요 — 이제 최악이어도 손해 없어요.")
                    lv = round(p["avg"] + R, 2)
                    if p["peak"] >= p["avg"] + 2 * R and (p.get("stop") or 0) < lv:
                        p["stop"] = lv
                        say(S, "risk", f"{s}가 +{2 * R / p['avg']:.1%}(손절 폭의 2배)까지 갔어요. 손절을 ${lv}(+{R / p['avg']:.1%})로 올려서 수익 일부 확보해요.")
                if p["peak"] >= p["avg"] * (1 + TRAIL_ON):
                    ts = round(p["peak"] * (1 - TRAIL), 2)
                    if not p.get("trail"):
                        p["trail"] = True
                        say(S, "risk", f"{s}가 +{(p['peak'] / p['avg'] - 1) * 100:.0f}% 넘었어요. 이제부터 고점 대비 -8% 추적 손절로 바꿔요 (지금 ${ts}).")
                    if ts > (p.get("stop") or 0):
                        p["stop"] = ts
        # 주문
        for od in [x for x in S["orders"] if x["sym"] == s]:
            if t + timedelta(minutes=5) <= datetime.fromisoformat(od["at"]):
                continue
            done = False
            if od["side"] == "buy" and S.get("halt"):
                continue
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
    if S.get("halt") and (now() - datetime.fromisoformat(S["halt"])).total_seconds() > 16 * 3600:
        S["halt"] = None
    print(f"{'에이전트' if ACCT == 'agent' else 'AI'} 계좌 ${e:,.2f} · 보유 {len(S['pos'])} · 대기 주문 {len(S['orders'])}")


def metrics(S):
    """Logger: 승률·손익비·최대 낙폭·누적 수익"""
    tr = S["trades"]; w = [x["pl"] for x in tr if x["pl"] > 0]; lo = [x["pl"] for x in tr if x["pl"] <= 0]
    eqs = [e for _, e in S["eq"]] or [10000]
    peak, mdd = eqs[0], 0
    for e in eqs:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    by = {}
    for x in tr:
        b = by.setdefault(x.get("src") or "기타", {"n": 0, "w": 0, "pl": 0}); b["n"] += 1; b["w"] += x["pl"] > 0; b["pl"] += x["pl"]
    return {"n": len(tr), "win": len(w) / len(tr) if tr else None, "avg_win": sum(w) / len(w) if w else None, "avg_loss": sum(lo) / len(lo) if lo else None,
            "payoff": (sum(w) / len(w)) / abs(sum(lo) / len(lo)) if w and lo and sum(lo) else None, "mdd": mdd, "cum": equity(S) / 10000 - 1, "by_src": by}


AGENT_RULES = ("트레이딩 계좌(투자 아님) · 판단은 전부 Claude 에이전트 (장 열리고 약 50분 뒤 진입 판단 + 마감 1시간 전 점검) · 매수마다 확신 점수 1~5 → 손절 시 계좌 손실 한도 0.5/0.75/1/1.25/1.5% · "
               "익절가 필수(최소 1.5R) · 보유 기한 필수(당일 청산 ~ 최대 5거래일, 기한 날 마감 10분 전 자동 청산) · "
               "손절가 필수(산 가격의 최대 -7%) · 한 종목 최대 20% · 최대 8종목 · S&P500 -3%면 신규 매수 중단 · 손절·익절은 장중 5분봉으로 자동 체결 · "
               "본전 손절·추적 손절 같은 자동 관리는 없음(에이전트가 직접 손절을 옮김) · 수수료 0.1% + 체결 차이 0.05%")


def view(S):
    e = equity(S)
    tr = S["trades"]; w = [x for x in tr if x["pl"] > 0]
    out = {"start": S["start"][:10], "cash0": 10000, "eq_now": round(e, 2), "cash": round(S["cash"], 2), "eq": S["eq"],
           "pos": [{"sym": t, "sh": round(p["sh"], 4), "avg": round(p["avg"], 2), "px": S["px"].get(t), "pl": (S["px"].get(t, p["avg"]) / p["avg"] - 1),
                    "val": round(p["sh"] * S["px"].get(t, p["avg"]), 2), "stop": p.get("stop"), "target": p.get("target"), "since": p["since"][:10], "why": p.get("why"), "src": p.get("src"), "conv": p.get("conv"), "exit_by": p.get("exit_by")}
                   for t, p in S["pos"].items()],
           "orders": [{**o, "desc": desc(o)} for o in S["orders"]], "trades": tr[::-1][:100], "journal": S["journal"][::-1][:150],
           "stats": metrics(S),
           "chat": S.get("chat", [])[-300:], "adj": {"src": S.get("src_adj", {}), "sig": S.get("sig_adj", {})}, "adj_log": S.get("adj_log", [])[-30:][::-1], "review": S.get("review"), "agents": S.get("agents", {}), "halt": S.get("halt"), "cands": S.get("cands", []),
           "bench": (S["px"]["SPY"] / S["bench0"] - 1) if S.get("bench0") and S["px"].get("SPY") else None,
           "acct": ACCT,
           "mode": S.get("mode"), "mode_why": S.get("mode_why"), "rules": AGENT_RULES if ACCT == "agent" else f"한 종목 최대 {MAX_W:.0%} · 최대 {MAX_N}종목 · 모든 매수에 손절가(산 가격의 최대 -7%) · 손절 시 손실 ≤ 계좌의 {MAX_RISK:.0%} · +1R이면 손절을 본전으로, +2R이면 +1R로 · 5거래일째 -0.5R 이하면 조기 정리 · +15%부터 고점 대비 -8% 추적 손절 · S&P500 -3%면 신규 매수 중단 · 수수료 0.1% + 체결 차이 0.05%"}
    VIEW.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=str))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("fill")
    o = sp.add_parser("order"); o.add_argument("sym"); o.add_argument("side", choices=["buy", "sell"])
    o.add_argument("--usd", type=float, default=0); o.add_argument("--pct", type=float); o.add_argument("--type", default="market", choices=["market", "limit", "stop"])
    o.add_argument("--px", type=float); o.add_argument("--stop", type=float); o.add_argument("--target", type=float); o.add_argument("--days", type=float, default=2)
    o.add_argument("--why", required=True); o.add_argument("--conv", type=int, choices=[1, 2, 3, 4, 5]); o.add_argument("--hold", type=int)
    m = sp.add_parser("modify"); m.add_argument("sym"); m.add_argument("--stop", type=float); m.add_argument("--target", type=float); m.add_argument("--why", required=True)
    c = sp.add_parser("cancel"); c.add_argument("id", type=int); c.add_argument("--why", required=True)
    n = sp.add_parser("note"); n.add_argument("text")
    y = sp.add_parser("say"); y.add_argument("who"); y.add_argument("text")
    a = ap.parse_args()
    S = load()
    if a.cmd == "fill": cmd_fill(S)
    elif a.cmd == "order": cmd_order(S, a)
    elif a.cmd == "modify": cmd_modify(S, a)
    elif a.cmd == "cancel": cmd_cancel(S, a)
    elif a.cmd == "note": log(S, "note", a.text); say(S, "claude", a.text)
    elif a.cmd == "say": say(S, a.who, a.text)
    save(S)


if __name__ == "__main__":
    main()
