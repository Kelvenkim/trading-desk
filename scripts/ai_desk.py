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
from datetime import date, datetime
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


def score(t, x, pf, srcs, spy_r20):
    """Analyst 일봉 점수 0~1"""
    p_tr = 0.1 * (x["c"] > x["ma20"]) + 0.1 * (x["c"] > x["ma50"]) + 0.1 * (not math.isnan(x["ma200"]) and x["ma50"] > x["ma200"])
    p_rsi = 0.2 if 45 <= x["rsi"] <= 70 else 0.1 if 70 < x["rsi"] <= 80 or 35 <= x["rsi"] < 45 else 0.03
    p_macd = 0.1 if x["macd"] > 0 else 0
    p_vol = 0.1 if x["vr"] > 1.2 and x["chg"] > 0 else 0.05 if x["vr"] > 1 else 0
    rs = x["r20"] - (spy_r20 or 0)
    p_rs = max(0, min(0.15, rs / 0.10 * 0.15))
    tg = (pf.get("analyst") or {}).get("mean")
    up = tg / x["c"] - 1 if tg else None
    p_an = 0.1 if up and up > 0.15 else 0.05 if up and up > 0 else 0
    p_sig = 0.05 if srcs & {"추천 바구니", "터틀 진입"} else 0.025 if srcs - {"보유 중"} else 0
    sc = round(p_tr + p_rsi + p_macd + p_vol + p_rs + p_an + p_sig, 2)
    why = ["추세↑" if p_tr >= 0.2 else "추세 약함" if p_tr <= 0.1 else "추세 보통", f"RSI {x['rsi']:.0f}", f"S&P 대비 {rs:+.0%}"]
    if up is not None: why.append(f"목표가 여력 {up:+.0%}")
    if x["vr"] > 1.2: why.append(f"거래량 {x['vr']:.1f}배")
    return {"t": t, "score": sc, "stop_pct": min(0.12, max(0.05, 2 * x["N"] / x["c"])), "why": ", ".join(why),
            "src": " + ".join(sorted(srcs)), "held": "보유 중" in srcs}


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
        z = score(t, I[t], prof(t) or {}, C[t], spy_r20)
        z["entry"] = round(I[t]["c"] - 0.25 * I[t]["N"], 2)
        z["stop"] = round(z["entry"] * (1 - z["stop_pct"]), 2)
        z["target"] = round(z["entry"] * (1 + 2.5 * z["stop_pct"]), 2)
        scored.append(z)
    # 장중 회의용: 전체 종목 일봉 점수 저장
    ds = {}
    for t in ko:
        rows = P.get(t)
        if not rows or len(rows) < 60:
            continue
        try:
            x = ind(rows[-260:]); z = score(t, x, prof(t) or {}, C.get(t, set()), spy_r20)
            ds[t] = [z["score"], round(z["stop_pct"], 4), round(x["c"], 2), round(x["N"], 3), z["why"], round(x["dv"] / 1e6)]
        except Exception:
            pass
    S["dscore"] = ds
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


# ======================= 장중·장전 회의 =======================
def ny_now():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def intraday(tickers, prepost=False):
    """오늘 5분봉 → 종목별 {p: 지금가, o: 시가, vwap, vol, hi, lo, first} (오늘 것만)"""
    import yfinance as yf, pandas as pd
    df = yf.download(sorted(tickers), period="2d", interval="5m", group_by="ticker", auto_adjust=False, progress=False, threads=True, prepost=prepost)
    today = ny_now().strftime("%Y-%m-%d"); out = {}
    for t in tickers:
        try:
            d = df[t] if isinstance(df.columns, pd.MultiIndex) else df
            d = d.dropna(subset=["Close"])
            d = d[d.index <= pd.Timestamp(ny_now()) - pd.Timedelta(minutes=5)]      # 아직 안 끝난 봉 제외 (모의 시험 때도 그 시각까지만)
            days = [ix.tz_convert("America/New_York").strftime("%Y-%m-%d") for ix in d.index]
            prevd = [i for i, x in enumerate(days) if x < today]
            pc = float(d["Close"].iloc[prevd[-1]]) if prevd else None
            d = d[[x == today for x in days]]
            if not len(d):
                continue
            tp = (d["High"] + d["Low"] + d["Close"]) / 3
            v = d["Volume"].fillna(0)
            cv = (tp * v).cumsum() / v.cumsum().replace(0, float("nan"))           # 시간별 VWAP
            below = (d["Close"] < cv).tolist()
            orng = d.iloc[:6]                                                      # 첫 30분 (개장 범위)
            out[t] = {"p": float(d["Close"].iloc[-1]), "o": float(d["Open"].iloc[0]), "hi": float(d["High"].max()), "lo": float(d["Low"].min()),
                      "vwap": float(cv.iloc[-1]) if cv.notna().any() else float(d["Close"].mean()), "vol": float(v.sum()), "bars": len(d), "pc": pc,
                      "orh": float(orng["High"].max()), "orl": float(orng["Low"].min()),
                      "reclaim": len(below) > 8 and any(below[:-3]) and not any(below[-3:]),       # 아래 있다가 최근 15분 VWAP 위로
                      "mom30": float(d["Close"].iloc[-1] / d["Close"].iloc[max(0, len(d) - 7)] - 1)}
        except Exception:
            pass
    return out


def live():
    """미국장 전·중에 30분마다 (update-data.yml). 장 전: 갭 점검 / 장중: 새 기회·보유 점검 / 마감 30분 전: 신규 중단"""
    S = AP.load()
    ny = ny_now(); hm = ny.hour * 60 + ny.minute; day = ny.strftime("%Y-%m-%d")
    if ny.weekday() >= 5 or hm < 7 * 60 or hm >= 16 * 60:
        print("AI 데스크: 장 시간 아님"); return
    phase = "pre" if hm < 9 * 60 + 30 else "open" if hm < 15 * 60 + 30 else "close"
    M = S.setdefault("meet", {})
    if M.get("day") != day:
        M.clear(); M["day"] = day; M["n"] = 0
    if phase == "pre" and M.get("pre"):
        print("AI 데스크: 장전 회의 이미 함"); return
    say = lambda who, t, **kw: AP.say(S, who, t, **kw)
    rank = j("rank.json", {}); ko = {r["code"]: (r.get("ko") or r["code"]) for r in rank.get("rows", [])}
    nm = lambda t: f"{ko.get(t, t)}({t})" if ko.get(t, t) != t else t
    ds = S.get("dscore", {})
    mine = set(S["pos"]) | {o["sym"] for o in S["orders"]}
    universe = set(ds) | mine | {"SPY"}
    X = intraday(universe, prepost=(phase == "pre"))
    spy = X.get("SPY")
    prev = lambda t: (X.get(t) or {}).get("pc") or (ds.get(t) or [None, None, None])[2]
    spy_prev = prev("SPY")
    spy_chg = spy["p"] / spy_prev - 1 if spy and spy_prev else 0
    M["n"] = M.get("n", 0) + 1
    t_ny = ny.strftime("%H:%M")

    if phase == "pre":
        M["pre"] = True
        say("logger", f"── {day} 장 전 회의 (뉴욕 {t_ny}) ──", sep=True)
        msgs = []
        for o in list(S["orders"]):
            x = X.get(o["sym"]); pc = prev(o["sym"])
            if not x or not pc or o["side"] != "buy":
                continue
            g = x["p"] / pc - 1
            if o.get("stop") and x["p"] <= o["stop"]:
                S["orders"].remove(o); AP.log(S, "cancel", "장 전 가격이 이미 손절가 아래", sym=o["sym"], detail=AP.desc(o))
                msgs.append(f"{nm(o['sym'])} 장 전 {g:+.1%}로 손절가 아래라 주문 취소")
            elif abs(g) >= 0.03:
                msgs.append(f"{nm(o['sym'])} 장 전 {g:+.1%}")
        held = [f"{nm(t)} {X[t]['p'] / prev(t) - 1:+.1%}" for t in S["pos"] if t in X and prev(t)]
        say("scout", f"장 전 S&P500(SPY) {spy_chg:+.2%}." + (f" 보유 종목 장 전: {', '.join(held)}." if held else "") + (f" 대기 주문 점검: {'; '.join(msgs)}." if msgs else " 대기 주문은 그대로 가요."))
        if spy_chg <= -0.02:
            say("risk", f"장 전부터 {spy_chg:+.1%}예요. 개장 15분은 신규 진입 없이 지켜보고, -3% 넘으면 신규 매수를 막을게요.")
        AP.save(S); print("AI 데스크: 장전 회의"); return

    # ---- 장중 ----
    if hm < 9 * 60 + 45:
        print("AI 데스크: 개장 15분 관망"); AP.save(S); return
    full = M["n"] == 1 or (hm >= 12 * 60 + 30 and not M.get("mid")) or (phase == "close" and not M.get("close"))
    if hm >= 12 * 60 + 30: M["mid"] = True
    if phase == "close": M["close"] = True
    acts = []
    # Risk: 보유 종목 장중 점검 (20일 최저 아래로 무너지면 정리 — 손절가와 별개)
    for t, p in list(S["pos"].items()):
        x = X.get(t); d = ds.get(t)
        if not x or not d:
            continue
        chg = x["p"] / (prev(t) or d[2]) - 1
        if chg <= -2.5 * d[3] / d[2] and x["p"] < x["vwap"]:
            acts.append(("risk", f"{nm(t)}가 오늘 {chg:+.1%}로 평소 변동의 2.5배 넘게 빠지고 VWAP 아래예요. 손절가(${p.get('stop')})까진 여유가 있어 규칙대로 두되 지켜볼게요."))
    # Scout: 장중 신호를 전체 종목에서 직접 찾음 (전날 종가 점수로 미리 거르지 않음)
    #   ① 개장 범위 돌파(ORB): 10시 이후 첫 30분 고점 위 + VWAP 위
    #   ② VWAP 회복: 오늘 VWAP 아래 있다가 다시 위로 올라와 15분 유지
    #   ③ 상대강도 급등: S&P500보다 +2% 이상 + VWAP 위
    #   공통: 오늘 거래대금이 평소 하루치의 1.3배 속도 이상, 평소 변동의 3배 넘게 이미 오른 건 추격 안 함
    cands = []
    if phase == "open" and not S.get("halt"):
        frac = max(0.08, (hm - 570) / 390)
        for t, x in X.items():
            d = ds.get(t)
            if t == "SPY" or t in mine or not d or not prev(t):
                continue
            pc = prev(t); chg = x["p"] / pc - 1; rel = chg - spy_chg; Np = d[3] / pc
            if x["p"] < x["vwap"] or chg > 3 * Np or x["p"] < 5:
                continue
            rv = (x["vol"] * x["p"] / frac) / max(1, d[5] * 1e6)                  # 거래대금 속도 (평소 하루 대비)
            if rv < 1.3:
                continue
            sig = []
            if hm >= 600 and x["p"] > x["orh"] * 1.001: sig.append("개장 범위 돌파")
            if x["reclaim"]: sig.append("VWAP 회복")
            if rel >= 0.02: sig.append(f"S&P 대비 {rel:+.1%}")
            if not sig:
                continue
            # Analyst 장중 점수 (0~1): 장중 60% + 일봉 맥락 40%
            p_sig = min(0.25, 0.12 * len(sig))
            p_rel = max(0, min(0.15, rel / 0.03 * 0.15))
            p_rv = max(0, min(0.12, (rv - 1) / 2 * 0.12))
            p_mom = 0.08 if x["mom30"] > 0 else 0
            isc = round(p_sig + p_rel + p_rv + p_mom + 0.4 * d[0], 2)
            stop = max(x["orl"] if "개장 범위 돌파" in sig else x["vwap"] - 0.5 * d[3], x["p"] * (1 - d[1]))
            stop = min(stop, x["p"] * 0.98)                                       # 최소 2% 여유
            cands.append({"t": t, "score": isc, "chg": chg, "rel": rel, "rv": rv, "sig": sig, "x": x, "d": d, "stop": round(stop, 2)})
        cands.sort(key=lambda z: -z["score"])
    # Risk: 장중에 산 종목이 개장 범위 저점을 깨면 그날 정리 (장중 진입 실패)
    for t, p in list(S["pos"].items()):
        x = X.get(t)
        if x and p.get("src") == "장중 신호" and p["since"][:10] == day and x["p"] < x["orl"] and not any(o["sym"] == t and o["side"] == "sell" for o in S["orders"]):
            o, _ = AP.place(S, t, "sell", typ="market", pct=100, why=f"장중 진입 실패: 개장 범위 저점(${x['orl']:.2f}) 이탈", src="장중 신호")
            acts.append(("risk", f"{nm(t)} 오늘 장중에 샀는데 개장 범위 저점 ${x['orl']:.2f} 아래로 밀렸어요. 신호 실패로 보고 시장가 정리할게요. @Executor"))
    seen = set(M.get("seen", []))
    new_c = [z for z in cands if z["t"] not in seen]
    M["seen"] = sorted(seen | {z["t"] for z in cands})
    cands = new_c                                            # 이미 오늘 이야기한 종목은 다시 안 꺼냄
    if cands:
        acts.append(("scout", f"장중 신호 {len(cands)}개 새로 잡혔어요: " + ", ".join(f"{nm(z['t'])} {z['chg']:+.1%} ({' · '.join(z['sig'])}, 거래 {z['rv']:.1f}배 속도)" for z in cands[:5]) + ". @Analyst"))
        ok = [z for z in cands if z["score"] >= 0.6][:3]
        acts.append(("analyst", ("장중 점수(장중 신호 60% + 일봉 맥락 40%, 0.6↑ 통과): " + "; ".join(f"{nm(z['t'])} {z['score']:.2f} (일봉 {z['d'][0]:.2f})" for z in ok) + ". @Risk") if ok else
                     "장중 신호는 있지만 0.6 넘는 건 없어요 — 일봉 추세가 약하거나 거래가 덜 붙었어요. 패스할게요. 최고: " + ", ".join(f"{nm(z['t'])} {z['score']:.2f}" for z in cands[:3])))
        if ok:
            new_today = sum(1 for o in S["orders"] if (o.get("src") or "").startswith("장중")) + M.get("bought", 0)
            eq = AP.equity(S); pend = sum(o["usd"] for o in S["orders"] if o["side"] == "buy")
            room = eq * 0.80 - (eq - S["cash"]) - pend
            placed, rej = [], []
            for z in ok:
                if new_today + len(placed) >= 2:
                    rej.append((z["t"], "장중 신규는 하루 2개까지")); continue
                px = round(z["x"]["p"] * 1.002, 2); sp = 1 - z["stop"] / px
                usd = math.floor(min(eq * AP.MAX_RISK / sp, eq * AP.MAX_W, room) / 10) * 10
                if usd < 200:
                    rej.append((z["t"], "현금 20% 유지 규칙")); continue
                o, bad = AP.place(S, z["t"], "buy", usd, "limit", px, z["stop"], round(px * (1 + 2.5 * sp), 2), 1,
                                  f"장중 회의 {t_ny}: {' · '.join(z['sig'])}, 거래 {z['rv']:.1f}배 속도, VWAP 위 → 장중 점수 {z['score']:.2f} (일봉 {z['d'][0]:.2f})", src="장중 신호", score=z["score"])
                if bad: rej.append((z["t"], bad)); continue
                placed.append((z, o, usd)); room -= usd
            if placed:
                M["bought"] = M.get("bought", 0) + len(placed)
                acts.append(("risk", "승인: " + "; ".join(f"{nm(z['t'])} ${u:,.0f} (손절 ${o['stop']}, -{1 - o['stop'] / o['px']:.1%})" for z, o, u in placed) + (" / 보류: " + "; ".join(f"{nm(t)} — {r}" for t, r in rej) if rej else "")))
                acts.append(("executor", "지정가 넣었어요 (오늘만 유효): " + "; ".join(f"{z['t']} ${o['px']} · 손절 ${o['stop']} · 목표 ${o['target']}" for z, o, u in placed)))
            elif rej:
                acts.append(("risk", "보류: " + "; ".join(f"{nm(t)} — {r}" for t, r in rej)))
    if phase == "close" and M.get("close") and full:
        canc = [o for o in S["orders"] if o["side"] == "buy" and o.get("src") == "장중 신호"]
        for o in canc:
            S["orders"].remove(o); AP.log(S, "cancel", "장 마감 전 미체결 장중 주문 취소", sym=o["sym"], detail=AP.desc(o))
        acts.append(("risk", "마감 30분 전이라 신규 진입은 여기까지예요." + (f" 안 채워진 장중 주문 {len(canc)}건 취소했어요." if canc else "")))
    if acts or full:
        e = AP.equity(S); r = e / 10000 - 1
        b = (S["px"].get("SPY") / S["bench0"] - 1) if S.get("bench0") and S["px"].get("SPY") else None
        say("logger", f"── 장중 회의 (뉴욕 {t_ny}, S&P500 {spy_chg:+.2%}) ──", sep=True)
        for who, t in acts:
            say(who, t)
        if full or acts:
            pos = ", ".join(f"{t} {S['px'].get(t, p['avg']) / p['avg'] - 1:+.1%}" for t, p in S["pos"].items()) or "없음"
            say("logger", f"지금 계좌 ${e:,.0f} ({r:+.2%})" + (f", S&P500 대비 {r - b:+.2%}p" if b is not None else "") + f". 보유: {pos}. 대기 주문 {len(S['orders'])}건.")
    S["agents"] = {**S.get("agents", {}), "live": f"뉴욕 {t_ny} 장중 회의 · 후보 {len(cands)}개"}
    AP.save(S)
    print("AI 데스크 장중:", phase, len(cands), len(acts))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    if "live" in sys.argv:
        live(); sys.exit()
    import us_prices as UP
    rank = j("rank.json"); tt = j("turtle.json")
    tick = sorted({r["code"] for r in rank["rows"]} | set(AP.load()["pos"]) | {"SPY", "^GSPC"})
    run(UP.download(tick, period="1y"), "--force" in sys.argv and None)
