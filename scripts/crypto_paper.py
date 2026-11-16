"""
코인 모의 계좌 (BTC·ETH, 주말 포함 24시간) — 가상 $10,000
  규칙(시험으로 고름): 하루 종가(UTC 0시 마감)가 50일선 위면 보유, 아래로 내려가면 전량 매도.
    - 코인마다 계좌의 최대 50%. 수수료+미끄러짐 한쪽 0.15%.
    - 1시간 돌파 매매는 2년 시험에서 BTC -65~-93%로 크게 져서 뺐어요 (README 보고서 참고).
  하루 4번(UTC 0·4·8·11시) 실행되지만, 매매 판단은 '새 일봉이 마감됐을 때' 한 번만 해요. 체결가는 그때 시세.
  숏(공매도): 규칙이 숏(-1)을 내면 하락에 돈을 거는 자리를 잡음(하루 펀딩 0.03%). 시작 규칙은 롱만 —
    2018~ 시험에서 숏을 섞으면 BTC +2407%→+1174%, 낙폭 -58%→-66%로 나빠졌고, 최근 1년 같은 약세장에서만 나았음.
    그래서 숏 규칙 2개(ls50·ls_bear)는 그림자로 굴리고, 실제로 이기면 아래 점검에서 자동으로 넘어감.
  스스로 발전: 같은 기간에 다른 규칙들(그냥 보유·200일선·50>200·돈치안 20/10·숏 2개)도 그림자 계좌로 같이 굴려서,
    일요일마다 비교. 28일 이상 지나고 어떤 규칙이 지금 규칙보다 5%p 넘게 앞서면서 낙폭도 더 작으면 그 규칙으로 바꿈.
  결과: data/us/crypto_paper.json (사이트·보고서용), 상태: data/us/crypto_state.json
"""
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us"
SF, OF = D / "crypto_state.json", D / "crypto_paper.json"
COINS = {"BTC-USD": "비트코인", "ETH-USD": "이더리움"}
CASH0, COST, MAXW = 10000.0, 0.0015, 0.5
RULES = {
    "ma50": "종가가 50일선 위면 보유",
    "ma200": "종가가 200일선 위면 보유",
    "gold": "50일선>200일선 이고 종가가 50일선 위면 보유",
    "don": "20일 신고가면 사고 10일 신저가면 팔기",
    "hold": "그냥 계속 보유",
    "ls50": "50일선 위면 롱, 아래면 숏",
    "ls_bear": "50일선 위면 롱, 50<200 약세에서 50일선 아래면 숏",
    "vote": "20·50·100·200일선 중 위에 있는 비율만큼 보유 (선 하나에 기대지 않기)",
}
FUND = 0.0003  # 숏 유지 비용(펀딩) 하루 0.03%
SWITCH_DAYS, SWITCH_GAP = 28, 0.05


def now():
    return datetime.now(timezone.utc)


def say(S, who, text):
    S.setdefault("chat", []).append({"at": now().isoformat(timespec="seconds"), "who": who, "text": text})
    S["chat"] = S["chat"][-400:]


def load_bars():
    import yfinance as yf
    out = {}
    for s in COINS:
        h = yf.Ticker(s).history(period="400d", interval="1d").dropna(subset=["Close"])
        bar = {ix.strftime("%Y-%m-%d"): float(x) for ix, x in h.Close.items()}
        today = now().strftime("%Y-%m-%d")
        # yfinance 일봉이 가끔 하루씩 빠짐(11/14 사례) → 최근 10일은 1시간봉으로 일봉 종가를 다시 만들어 채움
        try:
            h1 = yf.Ticker(s).history(period="10d", interval="1h").dropna(subset=["Close"])
            h1.index = h1.index.tz_convert("UTC")
            for dd, g in h1.groupby(h1.index.strftime("%Y-%m-%d")):
                if dd < today and len(g) >= 20:
                    bar[dd] = float(g.Close.iloc[-1])
        except Exception as e:
            print("1시간봉 보정 실패:", e)
        days = sorted(bar); cl = [bar[x] for x in days]
        live = cl[-1]
        try:
            m = yf.Ticker(s).history(period="1d", interval="5m").dropna(subset=["Close"])
            if len(m):
                live = float(m.Close.iloc[-1])
        except Exception:
            pass
        if days and days[-1] >= today:  # 아직 안 끝난 오늘 봉은 판단에서 뺌
            days, cl = days[:-1], cl[:-1]
        out[s] = {"days": days, "close": cl, "live": live}
    return out


def ma(c, k, i):
    return sum(c[i - k + 1:i + 1]) / k if i >= k - 1 else None


def want(rule, c, i, prev):
    """i번째 마감 봉 기준 목표 방향: 1 롱, 0 현금, -1 숏. prev = 직전 방향(돈치안용)"""
    if rule == "hold":
        return 1
    m50, m200 = ma(c, 50, i), ma(c, 200, i)
    if m50 is None:
        return 0
    up = c[i] > m50
    if rule == "ma50":
        return int(up)
    if rule == "ma200":
        return int(m200 is not None and c[i] > m200)
    if rule == "gold":
        return int(m200 is not None and m50 > m200 and up)
    if rule == "ls50":
        return 1 if up else -1
    if rule == "ls_bear":
        return 1 if up else (-1 if m200 is not None and m50 < m200 else 0)
    if rule == "vote":
        ms = [ma(c, L, i) for L in (20, 50, 100, 200)]
        return 0 if None in ms else round(sum(c[i] > m for m in ms) / 4, 2)
    if rule == "don":
        if i < 21:
            return 0
        if c[i] > max(c[i - 20:i]):
            return 1
        if c[i] < min(c[i - 10:i]):
            return 0
        return prev
    return 0


def shadow(B, start, rule, p0):
    """개설 시점부터 규칙대로 굴린 그림자 계좌 (코인 반반, 일봉 종가 체결 근사, 지금 시세로 평가)"""
    tot_now, curve_parts = 0.0, []
    for s, b in B.items():
        c, d = b["close"], b["days"]
        st = next((i for i, x in enumerate(d) if x >= start), len(c))
        side = 0
        for i in range(max(1, st - 60), st):
            side = want(rule, c, i, side)
        v, last, vals = CASH0 * MAXW, p0.get(s) or b["live"], []
        v *= 1 - COST * abs(side)
        for i in range(st, len(c)):
            v *= 1 + side * (c[i] / last - 1) - (FUND if side < 0 else 0)
            last = c[i]
            w = want(rule, c, i, side)
            if w != side:
                v *= 1 - COST * abs(w - side); side = w
            vals.append((d[i], v))
        v *= 1 + side * (b["live"] / last - 1)
        tot_now += v
        curve_parts.append(vals)
    days = sorted({x for vs in curve_parts for x, _ in vs})
    curve, peak, mdd = [], CASH0, 0.0
    for dd in days:
        tot = sum(next((v for x, v in reversed(vs) if x <= dd), CASH0 * MAXW) for vs in curve_parts)
        curve.append([dd, round(tot, 2)]); peak = max(peak, tot); mdd = min(mdd, tot / peak - 1)
    peak = max(peak, tot_now); mdd = min(mdd, tot_now / peak - 1)
    return {"eq": round(tot_now, 2), "ret": tot_now / CASH0 - 1, "mdd": mdd, "curve": curve}


def pval(p, px):
    """포지션 평가액: 넣은 돈 × (1 + 방향 × 수익률). 롱은 qty×가격과 같음"""
    if "usd" not in p:
        p["usd"] = p["qty"] * p["entry"]; p.setdefault("side", 1)
    return p["usd"] * (1 + p.get("side", 1) * (px / p["entry"] - 1))


def run():
    S = json.loads(SF.read_text()) if SF.exists() else {}
    B = load_bars()
    t = now(); today = t.strftime("%Y-%m-%d")
    if not S:
        S = {"start": today, "cash": CASH0, "pos": {}, "trades": [], "rule": "ma50", "eq": [], "history": [], "last_bar": {}, "p0": {k: b["live"] for k, b in B.items()}}
        say(S, "claude", "── 코인 계좌 개설 · 가상 $10,000 · 비트코인·이더리움 · 주말에도 돌아가요 ──")
        say(S, "analyst", "시험 결과: 1시간 돌파 매매는 최근 2년 BTC -65~-93%(그냥 보유 -35%)로 탈락. 하루 단위 50일선 추세 추종은 2018년·2022년·2024년 어디서 시작해도 그냥 보유보다 나았어요(BTC 2022~: +101% vs +35%).")
        say(S, "risk", "코인마다 계좌의 최대 50%. 일봉 종가가 50일선 아래로 마감하면 전량 정리. 하루 안의 출렁임엔 바로 반응하지 않아요(1시간 단위 손절은 시험에서 계속 털려서 크게 졌어요).")
    rule = S["rule"]
    # 1) 새로 마감된 일봉마다 판단 (코인별)
    for s, b in B.items():
        c, d = b["close"], b["days"]
        if not c:
            continue
        last = d[-1]
        if S["last_bar"].get(s) == last:
            continue
        S["last_bar"][s] = last
        p = S["pos"].get(s)
        if p:  # 숏은 하루마다 펀딩 비용
            p.setdefault("side", 1)
            if p["side"] < 0:
                p["usd"] *= 1 - FUND
        m50 = ma(c, 50, len(c) - 1); m200 = ma(c, 200, len(c) - 1)
        cur = p["side"] if p else 0
        w = want(rule, c, len(c) - 1, cur)
        nm = COINS[s]
        gap = (c[-1] / m50 - 1) if m50 else None
        say(S, "scout", f"{nm} {last} 일봉 마감 ${c[-1]:,.0f} · 50일선 ${m50:,.0f} ({gap * 100:+.1f}%) · 200일선 ${m200:,.0f}" if m50 and m200 else f"{nm} {last} 마감 ${c[-1]:,.0f}")
        px = b["live"]
        if p and w != cur:
            val = pval(p, px) * (1 - COST)
            S["cash"] += val
            pl = p["side"] * (px / p["entry"] - 1) - 2 * COST
            S["trades"].append({"sym": s, "side": p["side"], "in": p["since"], "out": today, "entry": p["entry"], "exit": px, "pl": pl, "rule": rule})
            del S["pos"][s]
            say(S, "executor", f"{nm} {'롱 매도' if cur > 0 else '숏 청산(되사기)'} @ ${px:,.0f} ({pl * 100:+.1f}%) — 이유: 조건 바뀜 ({RULES[rule]})")
        if w and w != cur:
            eqv = S["cash"] + sum(pval(q, B[k]["live"]) for k, q in S["pos"].items())
            usd = min(eqv * MAXW, S["cash"])
            if usd > 50:
                S["cash"] -= usd
                S["pos"][s] = {"side": w, "usd": usd * (1 - COST), "qty": usd * (1 - COST) / px, "entry": px, "since": today, "why": RULES[rule]}
                say(S, "executor", f"{nm} {'롱 매수' if w > 0 else '숏(공매도)'} ${usd:,.0f} @ ${px:,.0f} — 이유: {RULES[rule]}")
        elif w == cur:
            say(S, "logger", f"{nm} 변화 없음 — {'롱 유지' if cur > 0 else '숏 유지' if cur < 0 else '현금 대기'}")
    # 2) 평가
    eqv = S["cash"] + sum(pval(q, B[k]["live"]) for k, q in S["pos"].items())
    hr = t.strftime("%Y-%m-%dT%H:00")
    if not S["eq"] or S["eq"][-1][0] != hr:
        S["eq"].append([hr, round(eqv, 2)])
    S["eq"] = S["eq"][-2000:]
    # 3) 그림자 계좌 비교 + 일요일 자가 점검
    sh = {k: shadow(B, S["start"], k, S.get("p0", {})) for k in RULES}
    peak, mdd = CASH0, 0.0
    for _, v in S["eq"]:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1)
    age = (t.date() - datetime.fromisoformat(S["start"]).date()).days
    if t.weekday() == 6 and S.get("review") != today:
        S["review"] = today
        me = sh[rule]
        best = max((k for k in RULES if k != rule), key=lambda k: sh[k]["ret"])
        b_ = sh[best]
        line = " · ".join(f"{k} {sh[k]['ret'] * 100:+.1f}%" for k in RULES)
        say(S, "logger", f"── 주간 점검 ({age}일째) ── 그림자 계좌 성적: {line}")
        if S.get("lock"):
            say(S, "analyst", f"규칙 고정 중 ({S['lock']}) — 비교만 기록하고 자동 교체는 안 해요.")
        elif age >= SWITCH_DAYS and b_["ret"] - me["ret"] > SWITCH_GAP and b_["mdd"] >= me["mdd"]:
            S["history"].append({"day": today, "from": rule, "to": best, "why": f"{age}일 동안 {b_['ret'] * 100:+.1f}% vs {me['ret'] * 100:+.1f}%, 낙폭 {b_['mdd'] * 100:.1f}% vs {me['mdd'] * 100:.1f}%"})
            S["rule"] = best
            say(S, "analyst", f"규칙 변경: '{RULES[rule]}' → '{RULES[best]}' ({S['history'][-1]['why']}). 다음 일봉부터 적용.")
        else:
            why = "아직 28일 안 됨" if age < SWITCH_DAYS else "5%p 넘게 앞서면서 낙폭도 작은 규칙 없음"
            say(S, "analyst", f"규칙 유지 ({why}). 한두 주 성적으로 바꾸면 운에 휘둘려요.")
    SF.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    # 4) 사이트용
    btc = B["BTC-USD"]
    b0 = S.get("p0", {}).get("BTC-USD") or btc["live"]
    view = {
        "start": S["start"], "made": t.isoformat(timespec="minutes"), "rule": S["rule"], "rule_txt": RULES[S["rule"]],
        "eq_now": round(eqv, 2), "cash": round(S["cash"], 2), "mdd": mdd, "eq": S["eq"][-500:],
        "btc_ret": btc["live"] / b0 - 1,
        "pos": [{"sym": k, "name": COINS[k], "qty": q["qty"], "entry": q["entry"], "now": B[k]["live"], "pl": q.get("side", 1) * (B[k]["live"] / q["entry"] - 1), "side": q.get("side", 1),
                 "val": pval(q, B[k]["live"]), "since": q["since"],
                 "ma50": ma(B[k]["close"], 50, len(B[k]["close"]) - 1)} for k, q in S["pos"].items()],
        "watch": [{"sym": k, "name": COINS[k], "now": b["live"], "close": b["close"][-1], "ma50": ma(b["close"], 50, len(b["close"]) - 1),
                   "ma200": ma(b["close"], 200, len(b["close"]) - 1)} for k, b in B.items()],
        "trades": S["trades"][-30:], "history": S["history"], "chat": S["chat"][-200:],
        "shadow": {k: {"name": RULES[k], "ret": v["ret"], "mdd": v["mdd"]} for k, v in sh.items()},
        "rules_all": RULES,
    }
    OF.write_text(json.dumps(view, ensure_ascii=False, separators=(",", ":")))
    print(f"코인 계좌 ${eqv:,.2f} ({eqv / CASH0 - 1:+.2%}) 보유 {list(S['pos'])} 규칙 {S['rule']}")


if __name__ == "__main__":
    run()
