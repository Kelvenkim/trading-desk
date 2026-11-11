"""
AI 트레이딩 데스크 — 6명의 에이전트가 순서대로 일하고, 서로 대화방에 이야기를 남김
  Scout → Filter → Analyst → Risk → Executor → Logger   (규칙 기반 + Claude의 판단을 더하는 하이브리드)
  · Scout   후보 찾기: 추천 바구니, 터틀 진입·돌파 직전, 오늘 급등·거래량 급증, 이미 보유 중인 종목
  · Filter  걸러내기: 3일 안 실적 발표, 하루 거래대금 $2,000만 미만, 주가 $5 미만, 하루 변동 10% 넘는 과열, 시장 이상(VIX 35↑)
  · Analyst 0~1점: 추세(20·50·200일선) 0.30, RSI 0.20, MACD 0.10, 거래량 0.10, S&P500 대비 강도 0.15, 애널리스트 여력 0.10, 사이트 신호 0.05
            0.6 미만 탈락. 진입가(종가 − ¼N 지정가), 손절(기본 -8%, 변동성 2N에 맞춰 5~12%), 목표(손절 폭의 2.5배)
  · Risk    손절 시 손실 ≤ 계좌 2%로 금액 계산, 종목 20%·8종목·하루 신규 2개, 시장이 200일선 아래면 크기 절반·하루 1개
            장중엔 ai_paper.py fill에서 손절·+15% 추적 손절·S&P500 -3% 신규 매수 중단을 감시
  · Executor 지정가 주문(2일 유효), 중복 주문 방지
  · Logger  승률·손익비·최대 낙폭·누적 수익·후보 출처별 성적
us_daily.py 끝에서 run(P)로 불러요 (장 마감 뒤 하루 한 번). 체결은 update-data.yml이 30분마다.
"""
import json, math
from datetime import date
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us"
import ai_paper as AP

NAMES = {"scout": "Scout", "filter": "Filter", "analyst": "Analyst", "risk": "Risk", "executor": "Executor", "logger": "Logger", "claude": "Claude"}


def j(p, d=None):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return d


def prof(t):
    try:
        return json.loads((D / "profile" / f"{t}.json").read_text())
    except Exception:
        return None


def ind(rows):
    """일봉 → 지표"""
    a = np.array([r[1:6] for r in rows], float)
    o, h, l, c, v = a.T
    n = len(c)
    ma = lambda k: c[-k:].mean() if n >= k else np.nan
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    d = np.diff(c[-15:]); up = d.clip(min=0).mean(); dn = (-d.clip(max=0)).mean()
    rsi = 100 - 100 / (1 + up / dn) if dn > 0 else 100
    def ema(x, k):
        e = [x[0]]
        for y in x[1:]:
            e.append(e[-1] + 2 / (k + 1) * (y - e[-1]))
        return np.array(e)
    m = ema(c[-120:], 12) - ema(c[-120:], 26); sig = ema(m, 9)
    return {"c": c[-1], "chg": c[-1] / c[-2] - 1, "ma20": ma(20), "ma50": ma(50), "ma200": ma(200), "N": tr[-20:].mean(), "rsi": rsi,
            "macd": m[-1] - sig[-1], "vr": v[-5:].mean() / max(1, v[-20:].mean()), "r20": c[-1] / c[-21] - 1 if n > 21 else 0,
            "dv": (c[-20:] * v[-20:]).mean(), "range": (h[-1] - l[-1]) / c[-2], "n": n}


def run(P, day=None):
    S = AP.load()
    rank, tt, mk = j("rank.json", {}), j("turtle.json", {}), j("market.json", {})
    day = day or rank.get("date")
    if S.get("desk_day") == day:
        print("AI 데스크: 이미 처리한 날", day); return
    S["desk_day"] = day
    say = lambda who, t, **kw: AP.say(S, who, t, **kw)
    ko = {r["code"]: (r.get("ko") or r["code"]) for r in rank.get("rows", [])}
    nm = lambda t: f"{ko.get(t, t)}({t})" if ko.get(t, t) != t else t
    say("logger", f"── {day} 미국장 마감 회의 시작 ──", sep=True)

    # ① Scout
    C = {}
    for r in rank.get("rows", []):
        if r.get("basket"):
            C.setdefault(r["code"], set()).add("추천 바구니")
    for r in tt.get("rows", []):
        if r["st"]["kind"] == "new":
            C.setdefault(r["code"], set()).add("터틀 진입")
        elif r["st"]["kind"] == "near" and r["st"].get("distN", 9) <= 0.5:
            C.setdefault(r["code"], set()).add("터틀 돌파 직전")
    for x in (mk.get("up") or [])[:10]:
        t = x.get("t") or x.get("code")
        if t:
            C.setdefault(t, set()).add("오늘 급등")
    surge = []
    for t in list(P)[:]:
        rows = P[t]
        if t.startswith("^") or "=" in t or len(rows) < 30 or t not in ko:
            continue
        v = [r[5] for r in rows[-21:]]
        if v[-1] > 3 * (sum(v[:-1]) / 20 or 1) and rows[-1][4] > rows[-2][4]:
            surge.append(t)
    for t in surge[:8]:
        C.setdefault(t, set()).add("거래량 급증")
    for t in S["pos"]:
        C.setdefault(t, set()).add("보유 중")
    src_cnt = {}
    for v in C.values():
        for s_ in v:
            src_cnt[s_] = src_cnt.get(s_, 0) + 1
    say("scout", f"오늘 후보 {len(C)}개 찾았어요 — " + " · ".join(f"{k} {v}" for k, v in src_cnt.items()) +
        (f". 거래량이 평소 3배 넘게 터진 건 {', '.join(nm(t) for t in surge[:4])}." if surge else ".") + " @Filter 넘길게요.")

    # ② Filter
    vix = next((a["last"] for a in mk.get("assets", []) if a["t"] == "^VIX"), None)
    regime_up = (rank.get("regime") or {}).get("up", True)
    kill, keep, I = {}, [], {}
    abnormal = vix is not None and vix >= 35
    for t in C:
        rows = P.get(t)
        if not rows or len(rows) < 60:
            kill[t] = "시세 부족"; continue
        x = I[t] = ind(rows[-260:])
        pf = prof(t)
        nx = pf and pf.get("earn", {}).get("next")
        if nx and "보유 중" not in C[t]:
            dd = (date.fromisoformat(nx[:10]) - date.fromisoformat(day)).days
            if 0 < dd <= 4:
                kill[t] = f"실적 발표 {nx[5:10]}"; continue
        if x["dv"] < 2e7:
            kill[t] = f"거래대금 부족(하루 ${x['dv'] / 1e6:.0f}M)"; continue
        if x["c"] < 5:
            kill[t] = "주가 $5 미만"; continue
        if x["range"] > 0.10 and "보유 중" not in C[t]:
            kill[t] = f"하루 변동 {x['range']:.0%} 과열"; continue
        keep.append(t)
    if abnormal:
        say("filter", f"⚠️ VIX가 {vix:.0f}로 공포 구간이에요. 오늘은 신규 후보를 모두 보류할게요 (보유 종목 점검만).")
        keep = [t for t in keep if "보유 중" in C[t]]
    reasons = {}
    for t, r in kill.items():
        reasons.setdefault(r.split("(")[0].split(" ")[0] if r.startswith("실적") else r.split("(")[0], []).append(nm(t))
    say("filter", f"{len(C)}개 중 {len(kill)}개 뺐어요" + (" — " + " / ".join(f"{k}: {', '.join(v[:4])}{'…' if len(v) > 4 else ''}" for k, v in reasons.items()) if kill else "") +
        f". 남은 {len(keep)}개 @Analyst 봐주세요.")

    # ③ Analyst
    spy_r20 = I.get("SPY", {}).get("r20")
    if spy_r20 is None and P.get("^GSPC"):
        g = [r[4] for r in P["^GSPC"][-21:]]; spy_r20 = g[-1] / g[0] - 1
    scored = []
    for t in keep:
        x = I[t]; pf = prof(t) or {}
        p_tr = 0.1 * (x["c"] > x["ma20"]) + 0.1 * (x["c"] > x["ma50"]) + 0.1 * (not math.isnan(x["ma200"]) and x["ma50"] > x["ma200"])
        p_rsi = 0.2 if 45 <= x["rsi"] <= 70 else 0.1 if 70 < x["rsi"] <= 80 or 35 <= x["rsi"] < 45 else 0.03
        p_macd = 0.1 if x["macd"] > 0 else 0
        p_vol = 0.1 if x["vr"] > 1.2 and x["chg"] > 0 else 0.05 if x["vr"] > 1 else 0
        rs = x["r20"] - (spy_r20 or 0)
        p_rs = max(0, min(0.15, rs / 0.10 * 0.15))
        tg = (pf.get("analyst") or {}).get("mean")
        up = tg / x["c"] - 1 if tg else None
        p_an = 0.1 if up and up > 0.15 else 0.05 if up and up > 0 else 0
        p_sig = 0.05 if C[t] & {"추천 바구니", "터틀 진입"} else 0.025 if C[t] - {"보유 중"} else 0
        sc = round(p_tr + p_rsi + p_macd + p_vol + p_rs + p_an + p_sig, 2)
        stop_pct = min(0.12, max(0.05, 2 * x["N"] / x["c"]))
        if not (0.06 <= stop_pct <= 0.10):
            pass
        entry = round(x["c"] - 0.25 * x["N"], 2)
        stop = round(entry * (1 - stop_pct), 2)
        target = round(entry * (1 + 2.5 * stop_pct), 2)
        why = []
        why.append("추세↑" if p_tr >= 0.2 else "추세 약함" if p_tr <= 0.1 else "추세 보통")
        why.append(f"RSI {x['rsi']:.0f}")
        why.append(f"S&P 대비 {rs:+.0%}")
        if up is not None: why.append(f"목표가 여력 {up:+.0%}")
        if x["vr"] > 1.2: why.append(f"거래량 {x['vr']:.1f}배")
        scored.append({"t": t, "score": sc, "entry": entry, "stop": stop, "target": target, "stop_pct": stop_pct, "why": ", ".join(why),
                       "src": " + ".join(sorted(C[t])), "held": "보유 중" in C[t]})
    scored.sort(key=lambda z: -z["score"])
    passed = [z for z in scored if z["score"] >= 0.6 and not z["held"]]
    held_low = [z for z in scored if z["held"] and z["score"] < 0.4]
    top = scored[:12]
    say("analyst", (f"점수 매겼어요(0~1, 0.6 넘어야 통과). 통과 {len(passed)}개: " + "; ".join(f"{nm(z['t'])} {z['score']:.2f} — {z['why']}" for z in passed[:5])
                    if passed else f"오늘은 0.6 넘는 후보가 없어요. 가장 높은 건 " + "; ".join(f"{nm(z['t'])} {z['score']:.2f}({z['why']})" for z in top[:3]) + ". 억지로 사지 않을게요.") +
        (" @Risk 검토 부탁해요." if passed else ""))
    if held_low:
        say("analyst", "보유 중인데 점수가 많이 떨어진 종목: " + ", ".join(f"{nm(z['t'])} {z['score']:.2f}" for z in held_low) + " — 손절선은 그대로 두고 지켜볼게요.")
    S["cands"] = [{"t": z["t"], "name": ko.get(z["t"], z["t"]), "score": z["score"], "why": z["why"], "src": z["src"], "entry": z["entry"], "stop": z["stop"], "target": z["target"]} for z in top]

    # ④ Risk  ⑤ Executor
    eq = AP.equity(S)
    max_new = 2 if regime_up else 1
    size_k = 1.0 if regime_up else 0.5
    if not regime_up:
        say("risk", "S&P500이 200일선 아래예요. 오늘은 크기 절반, 신규 1개까지만 허용할게요.")
    placed, rej = [], []
    pend = sum(o["usd"] for o in S["orders"] if o["side"] == "buy")
    invested = eq - S["cash"]
    room = eq * 0.80 - invested - pend          # 현금 20%는 항상 남김
    for z in passed:
        if len(placed) >= max_new:
            rej.append((z["t"], f"하루 신규 {max_new}개 한도")); continue
        usd = min(eq * AP.MAX_RISK / z["stop_pct"] * size_k, eq * AP.MAX_W, room)
        usd = math.floor(usd / 10) * 10
        if usd < 200:
            rej.append((z["t"], "현금 20% 유지 규칙 (투자+대기 주문이 80% 찼어요)")); continue
        o, bad = AP.place(S, z["t"], "buy", usd, "limit", z["entry"], z["stop"], z["target"], 2,
                          f"Analyst {z['score']:.2f}점({z['why']}) · 출처: {z['src']}", src=z["src"], score=z["score"])
        if bad:
            rej.append((z["t"], bad)); continue
        placed.append((z, o, usd)); room -= usd
    cash_pct = S["cash"] / eq if eq else 1
    say("risk", f"지금 계좌 ${eq:,.0f}, 현금 {cash_pct:.0%}, 보유 {len(S['pos'])}종목. " +
        ("승인: " + "; ".join(f"{nm(z['t'])} ${u:,.0f} (손절 -{z['stop_pct']:.1%} → 최대 손실 ${u * z['stop_pct']:,.0f})" for z, o, u in placed) if placed else "오늘 승인한 신규 매수 없어요.") +
        (" / 보류: " + "; ".join(f"{', '.join(nm(t) for t, r2 in rej if r2 == r)} — {r}" for r in dict.fromkeys(r for _, r in rej)) if rej else ""))
    if placed:
        say("executor", "주문 넣었어요 (지정가, 2일 유효): " + "; ".join(f"{z['t']} ${z['entry']} 이하면 ${u:,.0f} · 손절 ${z['stop']} · 목표 ${z['target']}" for z, o, u in placed) +
            ". 미국장 열리면 30분마다 체결 확인할게요.")
    elif S["orders"]:
        say("executor", f"새 주문은 없고, 대기 중인 주문 {len(S['orders'])}건 계속 지켜볼게요.")

    # ⑥ Logger
    m = AP.metrics(S)
    bench = (S["px"].get("SPY") / S["bench0"] - 1) if S.get("bench0") and S["px"].get("SPY") else None
    say("logger", f"누적 {m['cum'] * 100:+.2f}%" + (f" (같은 기간 S&P500 {bench * 100:+.2f}%)" if bench is not None else "") +
        f" · 끝난 거래 {m['n']}건" + (f" · 승률 {m['win']:.0%} · 손익비 {m['payoff']:.1f}" if m["n"] and m["payoff"] else "") + f" · 최대 낙폭 {m['mdd'] * 100:.1f}%." +
        (" 아직 표본이 적어서 전략 평가는 이르다고 기록해 둘게요." if m["n"] < 20 else ""))
    S["agents"] = {"scout": f"후보 {len(C)}개", "filter": f"{len(kill)}개 제외 · {len(keep)}개 통과", "analyst": f"0.6↑ {len(passed)}개",
                   "risk": f"승인 {len(placed)} · 거절 {len(rej)}" + (" · 🚨 신규 중단" if S.get("halt") else ""), "executor": f"대기 주문 {len(S['orders'])}건",
                   "logger": f"누적 {m['cum'] * 100:+.2f}% · 거래 {m['n']}건", "day": day}
    AP.save(S)
    print("AI 데스크:", S["agents"])


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import us_prices as UP
    rank = j("rank.json"); tt = j("turtle.json")
    tick = sorted({r["code"] for r in rank["rows"]} | set(AP.load()["pos"]) | {"SPY", "^GSPC"})
    run(UP.download(tick, period="1y"), "--force" in sys.argv and None)
