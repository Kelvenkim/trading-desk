"""
모의 투자 (가상 $10,000) — 사이트의 전략을 매일 '실제처럼' 굴려서 기록을 쌓음
  계좌 3개:
    basket  오늘의 순위 '추천 바구니' 20종목 같은 비중, 5거래일마다 교체 (검증한 방식 그대로: 손절 없음)
    turtle  터틀 규칙 (20·55일 돌파 매수 스톱, ½N 추가, 2N 손절, 10·20일 최저 청산, 1유닛 = 1% ÷ N, 8% 상한, 12유닛, 시장 필터)
    spy     비교용: 첫날 S&P500 지수를 사서 그냥 보유 (배당 제외)
  주문은 장 마감 뒤에 내고 다음 거래일 시세로 체결 (시가 주문은 시가, 스톱 주문은 그 가격에 닿으면 — 갭이면 시가)
  비용: 매매마다 수수료 0.1% + 체결 차이 0.05%
  걸러내기: 3일 안에 실적 발표가 있으면 새로 사지 않음 (터틀은 시장 필터도). 걸러낸 이유는 모두 기록
  결과 → data/us/paper.json (화면용), data/us/paper_state.json (이어서 계산할 상태)
"""
import json, math
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us"
STATE = OUT / "paper_state.json"
START_CASH = 10000.0
FEE, SLIP = 0.001, 0.0005
REBAL = 5


def bar(P, t, day):
    for r in reversed(P.get(t, [])[-15:]):
        if r[0] == day:
            return {"o": r[1], "h": r[2], "l": r[3], "c": r[4]}
        if r[0] < day:
            break
    return None


def last_close(P, t, day):
    for r in reversed(P.get(t, [])):
        if r[0] <= day:
            return r[4]
    return None


def earnings_soon(t, day, days=3):
    f = OUT / "profile" / f"{t}.json"
    try:
        nx = json.loads(f.read_text()).get("earn", {}).get("next")
    except Exception:
        return None
    if not nx:
        return None
    d0, d1 = date.fromisoformat(day), date.fromisoformat(nx[:10])
    return nx[:10] if 1 <= (d1 - d0).days <= days + 2 else None      # 주말 포함 대략 3거래일


def new_acct(kind):
    return {"kind": kind, "cash": START_CASH, "pos": {}, "orders": [], "eq": [], "trades": [], "log": [], "n": 0}


def buy(a, t, px, sh, day, why, extra=None):
    px = px * (1 + SLIP)
    sh = min(sh, a["cash"] / (px * (1 + FEE)))
    if sh <= 0.0001:
        a["log"].append({"d": day, "t": t, "k": "skip", "why": "현금 부족"}); return 0
    a["cash"] -= sh * px * (1 + FEE)
    p = a["pos"].get(t)
    if p:
        p["avg"] = (p["avg"] * p["sh"] + px * sh) / (p["sh"] + sh); p["sh"] += sh
    else:
        p = a["pos"][t] = {"sh": sh, "avg": px, "since": day, **(extra or {})}
    a["log"].append({"d": day, "t": t, "k": "buy", "px": round(px, 2), "sh": round(sh, 4), "why": why})
    return sh


def sell(a, t, px, day, why):
    p = a["pos"].pop(t, None)
    if not p:
        return
    px = px * (1 - SLIP)
    a["cash"] += p["sh"] * px * (1 - FEE)
    pl = px * (1 - FEE) / (p["avg"] * (1 + FEE)) - 1
    a["trades"].append({"t": t, "in": p["since"], "out": day, "avg": round(p["avg"], 2), "px": round(px, 2), "pl": round(pl, 4),
                        "why": why, "units": p.get("units")})
    a["log"].append({"d": day, "t": t, "k": "sell", "px": round(px, 2), "pl": round(pl, 4), "why": why})


def equity(a, P, day):
    return a["cash"] + sum(p["sh"] * (last_close(P, t, day) or p["avg"]) for t, p in a["pos"].items())


# ---------- 1) 어제 낸 주문을 오늘 시세로 체결 ----------
def fill_basket(a, P, day):
    for o in a["orders"]:
        b = bar(P, o["t"], day)
        if not b:
            a["log"].append({"d": day, "t": o["t"], "k": "skip", "why": "시세 없음"}); continue
        if o["side"] == "sell":
            sell(a, o["t"], b["o"], day, o["why"])
    for o in a["orders"]:
        b = bar(P, o["t"], day)
        if b and o["side"] == "buy":
            buy(a, o["t"], b["o"], o["usd"] / b["o"], day, o["why"])
    a["orders"] = []


def fill_turtle(a, P, day):
    # 보유 종목: 손절·청산선 먼저, 그다음 추가 매수
    for t in list(a["pos"]):
        p, b = a["pos"][t], bar(P, t, day)
        if not b:
            continue
        lvl = max(p["stop"], p.get("exit") or -1)
        if b["l"] <= lvl:
            sell(a, t, min(b["o"], lvl), day, "2N 손절" if lvl == p["stop"] else ("10일" if p["sys"] == 1 else "20일") + " 최저 이탈")
            continue
        while p["units"] < 4 and b["h"] >= p["next"] and a["units"] < 12:
            px = max(b["o"], p["next"])
            if not buy(a, t, px, p["ush"], day, f"추가 {p['units'] + 1}유닛 (+½N)"):
                break
            p["units"] += 1; a["units"] += 1
            p["stop"] = px - 2 * p["n"]; p["next"] = px + 0.5 * p["n"]
    # 새 진입 (매수 스톱)
    for o in a["orders"]:
        if o["t"] in a["pos"] or a["units"] >= 12:
            continue
        b = bar(P, o["t"], day)
        if not b or b["h"] < o["trigger"]:
            continue
        px = max(b["o"], o["trigger"])
        if buy(a, o["t"], px, o["ush"], day, f"시스템{o['sys']} {'20' if o['sys'] == 1 else '55'}일 돌파",
               {"sys": o["sys"], "n": o["n"], "ush": o["ush"], "units": 1, "stop": px - 2 * o["n"], "next": px + 0.5 * o["n"]}):
            a["units"] += 1
            p = a["pos"][o["t"]]
            while p["units"] < 4 and b["h"] >= p["next"] and a["units"] < 12:
                px2 = max(b["o"], p["next"])
                if not buy(a, o["t"], px2, p["ush"], day, f"추가 {p['units'] + 1}유닛 (+½N)"):
                    break
                p["units"] += 1; a["units"] += 1; p["stop"] = px2 - 2 * p["n"]; p["next"] = px2 + 0.5 * p["n"]
    a["orders"] = []


# ---------- 2) 장 마감 뒤 내일 주문 ----------
def order_basket(a, P, day, rank):
    a["n"] += 1
    if (a["n"] - 1) % REBAL:
        return
    eq = equity(a, P, day)
    target = []
    for r in rank["rows"]:
        if not r.get("basket"):
            continue
        e = earnings_soon(r["code"], day)
        if e and r["code"] not in a["pos"]:
            a["log"].append({"d": day, "t": r["code"], "k": "kill", "why": f"실적 발표 임박 ({e[5:]})"}); continue
        target.append(r["code"])
    for t in a["pos"]:
        if t not in target:
            a["orders"].append({"t": t, "side": "sell", "why": "바구니에서 빠짐"})
    for t in target:
        if t not in a["pos"]:
            a["orders"].append({"t": t, "side": "buy", "usd": eq / 20, "why": "추천 바구니"})
    a["log"].append({"d": day, "t": "", "k": "note", "why": f"교체일: {len(target)}종목 목표, 매도 주문 {sum(o['side'] == 'sell' for o in a['orders'])} · 매수 주문 {sum(o['side'] == 'buy' for o in a['orders'])}"})


def lows(P, t, day, n):
    rows = [r for r in P.get(t, []) if r[0] <= day][-n:]
    return min(r[3] for r in rows) if len(rows) == n else None


def order_turtle(a, P, day, tt):
    eq = equity(a, P, day)
    for t, p in a["pos"].items():          # 청산선은 매일 새로 (오늘까지 포함한 10·20일 최저)
        p["exit"] = lows(P, t, day, 10 if p["sys"] == 1 else 20)
    if not tt.get("regime", {}).get("up"):
        a["log"].append({"d": day, "t": "", "k": "kill", "why": "시장 필터: S&P500이 200일선 아래 → 새 진입 쉼"})
        return
    for r in sorted(tt["rows"], key=lambda r: r["st"].get("distN", 9)):
        s = r["st"]
        if s["kind"] != "near" or r["code"] in a["pos"]:
            continue
        e = earnings_soon(r["code"], day)
        if e:
            a["log"].append({"d": day, "t": r["code"], "k": "kill", "why": f"실적 발표 임박 ({e[5:]})"}); continue
        n = r["N"]
        if not n or n <= 0:
            continue
        ush = min(eq * 0.01 / n, eq * 0.08 / s["trigger"])
        a["orders"].append({"t": r["code"], "trigger": s["trigger"], "sys": s["sys"], "n": n, "ush": ush})


def run(P, day=None):
    rank = json.loads((OUT / "rank.json").read_text())
    tt = json.loads((OUT / "turtle.json").read_text())
    day = day or rank["date"]
    S = json.loads(STATE.read_text()) if STATE.exists() else {"start": day, "last": None, "acct": {k: new_acct(k) for k in ("basket", "turtle", "spy")}}
    A = S["acct"]
    A["turtle"].setdefault("units", 0)
    if S["last"] and day <= S["last"]:
        print("모의 투자: 이미 처리한 날", day); return
    if S["last"]:
        fill_basket(A["basket"], P, day)
        fill_turtle(A["turtle"], P, day)
        A["turtle"]["units"] = sum(p["units"] for p in A["turtle"]["pos"].values())
        sp = A["spy"]
        for o in sp["orders"]:
            b = bar(P, "^GSPC", day)
            if b:
                buy(sp, "^GSPC", b["o"], sp["cash"] / (b["o"] * (1 + SLIP) * (1 + FEE)), day, "S&P500 그냥 보유")
        sp["orders"] = []
    for k, a in A.items():
        a["eq"].append([day, round(equity(a, P, day), 2)])
    order_basket(A["basket"], P, day, rank)
    order_turtle(A["turtle"], P, day, tt)
    if not A["spy"]["pos"] and not A["spy"]["orders"]:
        A["spy"]["orders"].append({"t": "^GSPC", "side": "buy"})
    S["last"] = day
    for a in A.values():
        a["log"] = a["log"][-600:]
    STATE.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    # 화면용
    names = {r["code"]: (r.get("ko") or r.get("name")) for r in rank["rows"]}
    view = {"start": S["start"], "date": day, "cash0": START_CASH, "cost": "매매마다 수수료 0.1% + 체결 차이 0.05%", "acct": {}}
    for k, a in A.items():
        pos = []
        for t, p in a["pos"].items():
            c = last_close(P, t, day)
            pos.append({"t": t, "name": names.get(t, t), "sh": round(p["sh"], 4), "avg": round(p["avg"], 2), "px": c, "pl": round(c / p["avg"] - 1, 4) if c else None,
                        "val": round(p["sh"] * c, 2) if c else None, "since": p["since"], "units": p.get("units"),
                        "stop": round(max(p["stop"], p.get("exit") or -1), 2) if "stop" in p else None})
        tr = a["trades"]
        wins = [x for x in tr if x["pl"] > 0]
        view["acct"][k] = {"eq": a["eq"], "cash": round(a["cash"], 2), "pos": sorted(pos, key=lambda x: -(x["val"] or 0)),
                           "orders": a["orders"], "trades": tr[-200:][::-1], "log": a["log"][-200:][::-1],
                           "stats": {"n": len(tr), "win": round(len(wins) / len(tr), 3) if tr else None,
                                     "avg_win": round(sum(x["pl"] for x in wins) / len(wins), 4) if wins else None,
                                     "avg_loss": round(sum(x["pl"] for x in tr if x["pl"] <= 0) / max(1, len(tr) - len(wins)), 4) if len(tr) > len(wins) else None}}
    (OUT / "paper.json").write_text(json.dumps(view, ensure_ascii=False, separators=(",", ":")))
    print("모의 투자:", {k: v["eq"][-1][1] for k, v in A.items()}, flush=True)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import us_prices as UP
    rank = json.loads((OUT / "rank.json").read_text()); tt = json.loads((OUT / "turtle.json").read_text())
    tick = sorted({r["code"] for r in rank["rows"]} | {"^GSPC"})
    run(UP.download(tick, period="3mo"))
