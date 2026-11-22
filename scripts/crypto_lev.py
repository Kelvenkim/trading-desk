"""
코인 10배 레버리지 실험 계좌 — 가상 $10,000, 비트코인만
  (11/15 사용자 요청 10배→5배 · 11/21 사용자 요청 다시 10배: 증거금 10배 + 노출 목표 2배(최대 5배, 연 120% ÷ 변동성))
  10배 격리 증거금 → 강제 청산선 진입가 ±9.5%. 추적 손절 8%가 그보다 먼저 걸리도록 유지
  방향: 일봉 종가가 50일선 위면 롱, 아래면 숏 (하루 한 번, 일봉 마감 뒤)
  위험 줄이기 (11/16 추가, 2018~ 시험으로 고름):
    ① 크기 = 변동성 맞춤: 계좌 대비 노출 = min(2.5배, 연 60% ÷ 최근 20일 변동성). 출렁이는 때일수록 작게.
       증거금은 그 노출의 1/5 (5배 격리 증거금) → 강제 청산선은 진입가 ±19.5% 그대로.
    ② 추적 손절 -8%: 들고 있는 동안 가장 좋았던 가격에서 8% 되돌리면 1시간 단위로 바로 정리.
       정리 뒤 다음 일봉 마감에 신호가 같으면 같은 방향으로 바로 재진입 (11/22 형: '쉬는 건 사람 심리용 — 공식이면 쉬지 마'.
       예전엔 50일선 신호가 바뀔 때까지 쉬었음. 시험(research/crypto/lev_block.py): 안 쉬면 2018~ 수익↑·최대 낙폭 −61%→−84%, 2022~는 수익도↓)
    ③ 노출이 목표와 25% 넘게 벌어지면 일봉 마감 때 크기 조정.
    시험(수익·최대 낙폭): 그대로 5배 롱+숏 2018~ -78%·-98% / 2022~ -84%·-97%
                         ①+② 2018~ +2,675%·-47% / 2022~ +657%·-41% / 24.11~ +224%·-41%
    주의: 비트코인 하나·과거 데이터로 고른 값이라 실제는 이보다 나쁠 수 있음 (추적 폭 6~15%에 따라 결과가 크게 갈림)
  비용: 매매 0.15% × 포지션, 펀딩 하루 0.03% × 포지션 (롱·숏 모두 냄으로 보수적으로)
  결과: data/us/crypto_lev.json, 상태: data/us/crypto_lev_state.json
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import crypto_paper as cp

D = cp.D
SF, OF = D / "crypto_lev_state.json", D / "crypto_lev.json"
SYM, LEV, MAXE, COST, FUND, MM = "BTC-USD", 10, 5.0, 0.0015, 0.0003, 0.005
VT, TRAIL, REBAL = 1.20, 0.07, 0.25   # 11/21: 10배라 청산선(±9.5%)과 거리 두려고 추적 손절 8%→7%
DD_CUT = -0.15                          # 손실 최소화: 계좌가 최고점보다 15%↓면 노출 절반
CASH0 = 10000.0


def liq_px(entry, side=1):
    """롱은 아래로, 숏은 위로 약 (1/배수 - 0.5%) 움직이면 강제 청산"""
    return entry * (1 - side * (1 / LEV - MM))


def pval(p, px):
    return max(0.0, p["margin"] * (1 + p.get("side", 1) * LEV * (px / p["entry"] - 1)))


def vol20(c):
    import math
    r = [math.log(c[i] / c[i - 1]) for i in range(len(c) - 20, len(c))]
    m = sum(r) / len(r)
    return (sum((x - m) ** 2 for x in r) / (len(r) - 1)) ** 0.5 * math.sqrt(365)


def notional(p, px):
    return p["margin"] * LEV * px / p["entry"]


def close(S, p, px, today, why, liq=False):
    val = 0.0 if liq else max(0.0, pval(p, px) - notional(p, px) * COST)
    S["cash"] += val
    pl_usd = val - p["basis"]
    S["trades"].append({"side": p["side"], "in": p["since"], "out": today, "entry": p["entry0"], "exit": px, "pl": pl_usd / p["eq_in"],
                        "usd": round(pl_usd, 2), "liq": liq, "why": why})
    S["pos"] = None
    return pl_usd


def open_(S, side, px, eqv, E, today, t):
    m = eqv * E / LEV
    m = min(m, S["cash"])
    S["cash"] -= m
    fee = m * LEV * COST
    S["pos"] = {"side": side, "since": today, "at": t.isoformat(), "entry": px, "entry0": px, "margin": m - fee, "basis": m,
                "margin0": m, "liq": liq_px(px, side), "ext": px, "E": E, "eq_in": eqv, "lev": LEV}
    S["fund_day"] = today
    return S["pos"]


def run():
    import yfinance as yf
    t = cp.now(); today = t.strftime("%Y-%m-%d")
    B = cp.load_bars()[SYM]
    c, d, px = B["close"], B["days"], B["live"]
    S = json.loads(SF.read_text()) if SF.exists() else {}
    if S.get("retired"):                                         # 11/22 형 결정으로 새 방식(scripts/amd_paper.py lev10 → data/us/lev10.json)으로 옮김
        print("코인 10배(50일선) 계좌는", S["retired"], "에 새 방식으로 옮겨서 더 안 돌림"); return
    if not S:
        S = {"start": today, "cash": CASH0, "pos": None, "trades": [], "eq": [], "last_bar": None, "liq": 0, "last_chk": t.isoformat(), "p0": px}
        cp.say(S, "claude", f"── {LEV}배 레버리지 실험 계좌 개설 · 가상 $10,000 · 비트코인만 ──")
    p = S["pos"]
    # 배수 바꾸기 (11/21 5배 → 10배): 옛 배수로 지금 가격에 정리하고, 바로 새 배수로 다시 판단
    if p and p.get("lev", 5) != LEV:
        old = p.get("lev", 5)
        val = max(0.0, p["margin"] * (1 + p["side"] * old * (px / p["entry"] - 1)) - p["margin"] * old * px / p["entry"] * COST)
        S["cash"] += val; pl_usd = val - p["basis"]
        S["trades"].append({"side": p["side"], "in": p["since"], "out": today, "entry": p.get("entry0", p["entry"]), "exit": px, "pl": pl_usd / p.get("eq_in", CASH0),
                            "usd": round(pl_usd, 2), "liq": False, "why": f"{old}배 → {LEV}배 전환으로 정리 (사용자 요청)"})
        cp.say(S, "claude", f"사용자 요청으로 {old}배 → {LEV}배 전환. 지금 {('롱' if p['side'] > 0 else '숏')}을 ${px:,.0f}에 정리({pl_usd:+,.0f}$)하고, 같은 규칙(50일선·변동성 맞춤·추적 손절 8%)으로 {LEV}배 다시 판단해요. 강제 청산선이 ±19.5% → ±9.5%로 가까워져요.")
        S["pos"] = p = None; S["last_bar"] = None; S.pop("block", None)
    nm = lambda x: "롱" if x > 0 else "숏"
    if p:  # 옛 형식 → 새 형식
        p.setdefault("side", 1); p.setdefault("entry0", p["entry"]); p.setdefault("basis", p.get("margin0", p["margin"])); p.setdefault("ext", p["entry"]); p.setdefault("eq_in", CASH0)
        p.setdefault("E", p["margin0"] * LEV / CASH0 if "margin0" in p else MAXE)
    # 1) 1시간 단위: 펀딩, 강제 청산, 추적 손절
    if p:
        side = p["side"]
        days_held = max(0, (t.date() - datetime.fromisoformat(S.get("fund_day") or p["since"]).date()).days)
        if days_held:
            p["margin"] -= notional(p, px) * FUND * days_held; S["fund_day"] = today
        try:
            h1 = yf.Ticker(SYM).history(period="5d", interval="1h").dropna(subset=["Low"])
            h1.index = h1.index.tz_convert("UTC")
            since = datetime.fromisoformat(S.get("last_chk") or p["at"])
            bars = [(float(r.High), float(r.Low)) for ix, r in h1[h1.index >= since.replace(minute=0, second=0, microsecond=0)].iterrows()]
        except Exception:
            bars = []
        bars.append((px, px))
        for hi_, lo_ in bars:
            stop = p["ext"] * (1 - side * TRAIL)
            adverse = lo_ if side > 0 else hi_
            if (side > 0 and adverse <= p["liq"]) or (side < 0 and adverse >= p["liq"]):
                if not ((side > 0 and stop > p["liq"]) or (side < 0 and stop < p["liq"])):
                    m_ = p["margin"]; close(S, p, p["liq"], today, "강제 청산", liq=True); S["liq"] += 1
                    cp.say(S, "risk", f"💥 강제 청산 — 비트코인 ${adverse:,.0f}, 청산가 ${p['liq']:,.0f}. 증거금 ${m_:,.0f} 전부 손실.")
                    p = None; break
            if (side > 0 and adverse <= stop) or (side < 0 and adverse >= stop):
                pl_usd = close(S, p, stop, today, f"추적 손절 (최고점 ${p['ext']:,.0f}에서 {TRAIL:.0%} 되돌림)")
                cp.say(S, "risk", f"✂️ 추적 손절 — {nm(side)} 정리 @ ${stop:,.0f} (가장 좋았던 ${p['ext']:,.0f}에서 {TRAIL:.0%} 되돌림) · {pl_usd:+,.0f}$. 다음 일봉 마감에 신호가 같으면 바로 다시 들어가요.")
                p = None; break
            p["ext"] = max(p["ext"], hi_) if side > 0 else min(p["ext"], lo_)
    S["last_chk"] = t.isoformat()
    # 2) 새 일봉 마감 때: 방향 · 크기
    if c and S["last_bar"] != d[-1]:
        S["last_bar"] = d[-1]
        m50 = cp.ma(c, 50, len(c) - 1)
        want = 0 if m50 is None else (1 if c[-1] > m50 else -1)
        S.pop("block", None)                                    # 11/22: 재진입 금지 규칙 없앰
        v = vol20(c); E = round(min(MAXE, VT / v), 2)
        pk = max([CASH0] + [x for _, x in S["eq"]]); eq_now_ = S["cash"] + (pval(p, px) if p else 0)
        if eq_now_ / pk - 1 <= DD_CUT:
            E = round(E / 2, 2); cp.say(S, "risk", f"손실 최소화: 계좌가 최고점 대비 {eq_now_ / pk - 1:+.1%} → 노출 절반({E:.2f}배)")
        cur = p["side"] if p else 0
        cp.say(S, "scout", f"비트코인 {d[-1]} 마감 ${c[-1]:,.0f} · 50일선 ${m50:,.0f} ({(c[-1] / m50 - 1) * 100:+.1f}%) · 20일 변동성 연 {v:.0%} → 목표 노출 {E:.2f}배")
        if p and want != cur:
            pl_usd = close(S, p, px, today, f"50일선 {'아래' if cur > 0 else '위'}로 마감")
            cp.say(S, "executor", f"{nm(cur)} 정리 @ ${px:,.0f} · {pl_usd:+,.0f}$ (50일선 {'아래' if cur > 0 else '위'}로 마감)")
            p = None
        eqv = S["cash"] + (pval(p, px) if p else 0)
        if want and not p:
            if True:
                p = open_(S, want, px, eqv, E, today, t)
                cp.say(S, "executor", f"{nm(want)} 진입 @ ${px:,.0f} · 증거금 ${p['basis']:,.0f} × {LEV}배 = 포지션 ${p['basis'] * LEV:,.0f} (계좌의 {E:.2f}배) · 강제 청산 ${p['liq']:,.0f} · 추적 손절 ${px * (1 - want * TRAIL):,.0f}")
        elif p:
            curE = notional(p, px) / eqv if eqv else 0
            if curE and abs(E - curE) / curE > REBAL:
                val = pval(p, px); S["cash"] += val
                fee = abs(eqv * E - notional(p, px)) * COST
                newm = min(eqv * E / LEV, S["cash"]); S["cash"] -= newm
                p["basis"] += newm - val
                p.update({"entry": px, "margin": newm - fee, "liq": liq_px(px, p["side"]), "E": E})
                cp.say(S, "risk", f"크기 조정 {curE:.2f}배 → {E:.2f}배 (변동성 연 {v:.0%}) · 강제 청산가 ${p['liq']:,.0f}로 다시 계산")
            else:
                cp.say(S, "logger", f"변화 없음 — {nm(p['side'])} 유지 · 지금 노출 {curE:.2f}배 · 추적 손절 ${p['ext'] * (1 - p['side'] * TRAIL):,.0f}")
    # 3) 평가
    eqv = S["cash"] + (pval(p, px) if p else 0)
    hr = t.strftime("%Y-%m-%dT%H:00")
    if not S["eq"] or S["eq"][-1][0] != hr:
        S["eq"].append([hr, round(eqv, 2)])
    S["eq"] = S["eq"][-2000:]
    peak, mdd = CASH0, 0.0
    for _, v_ in S["eq"]:
        peak = max(peak, v_); mdd = min(mdd, v_ / peak - 1)
    SF.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    view_p = None
    if p:
        view_p = {**p, "entry": p["entry0"], "val": pval(p, px), "pl": (pval(p, px) - p["basis"]) / p["eq_in"], "dist": abs(p["liq"] / px - 1),
                  "stop": p["ext"] * (1 - p["side"] * TRAIL), "expo": notional(p, px) / eqv if eqv else 0, "margin0": p["basis"]}
    OF.write_text(json.dumps({
        "start": S["start"], "made": t.isoformat(timespec="minutes"), "eq_now": round(eqv, 2), "cash": round(S["cash"], 2), "mdd": mdd,
        "lev": LEV, "btc_ret": px / S["p0"] - 1, "now": px, "liq_n": S["liq"], "trail": TRAIL, "vt": VT, "block": S.get("block"),
        "pos": view_p, "trades": S["trades"][-20:], "chat": S["chat"][-100:], "eq": S["eq"][-500:],
    }, ensure_ascii=False, separators=(",", ":")))
    print(f"{LEV}배 계좌 ${eqv:,.2f} ({eqv / CASH0 - 1:+.2%}) 포지션 {nm(p['side']) if p else '없음'} 강제청산 {S['liq']}번")


if __name__ == "__main__":
    run()
