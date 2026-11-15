"""
코인 5배 레버리지 실험 계좌 (11/15 사용자 요청으로 10배→5배) — 가상 $10,000, 비트코인만 (사용자 요청 실험, 11/15~)
  규칙은 코인 본 계좌와 같음: 일봉 종가가 50일선 위면 롱, 아래면 정리 (본 계좌가 숏 규칙으로 바뀌어도 이건 롱만)
  레버리지: 들어갈 때 계좌의 50%를 증거금으로 걸고 5배 → 포지션 = 계좌의 2.5배 (격리 증거금)
    - 진입가에서 약 -19.5% 내려가면 강제 청산 = 그 증거금 전부 잃음 (나머지 50%는 남아서 다음 신호 때 다시 50% 걸기)
    - 강제 청산은 하루 중 언제든 일어나니 1시간봉 저가로 확인
    - 비용: 매매 0.15% × 5배(증거금의 0.75%), 펀딩 하루 0.03% × 5배(증거금의 0.15%/일)
  시험(2018~): 10배는 강제 청산 7번·최대 낙폭 -99%, 2022년 시작이면 그해 11월에 거의 0. 5배·3배가 오히려 나았음.
  결과: data/us/crypto_lev.json, 상태: data/us/crypto_lev_state.json
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import crypto_paper as cp

D = cp.D
SF, OF = D / "crypto_lev_state.json", D / "crypto_lev.json"
SYM, LEV, MARGIN_W, COST, FUND, MM = "BTC-USD", 5, 0.5, 0.0015, 0.0003, 0.005
CASH0 = 10000.0


def liq_px(entry):
    return entry * (1 - (1 / LEV - MM))


def pval(p, px):
    return max(0.0, p["margin"] * (1 + LEV * (px / p["entry"] - 1)))


def run():
    import yfinance as yf
    t = cp.now(); today = t.strftime("%Y-%m-%d")
    B = cp.load_bars()[SYM]
    c, d, px = B["close"], B["days"], B["live"]
    S = json.loads(SF.read_text()) if SF.exists() else {}
    if not S:
        S = {"start": today, "cash": CASH0, "pos": None, "trades": [], "eq": [], "last_bar": None, "liq": 0, "last_chk": t.isoformat(), "p0": px}
        cp.say(S, "claude", "── 10배 레버리지 실험 계좌 개설 · 가상 $10,000 · 비트코인만 ──")
        cp.say(S, "risk", f"들어갈 때 계좌의 50%를 증거금으로 10배 → 포지션은 계좌의 5배. 진입가에서 약 {(1 / LEV - MM) * 100:.1f}% 빠지면 강제 청산(증거금 전부 손실).")
        cp.say(S, "analyst", "시험(2018~): 1배 +760%(낙폭 -35%) · 5배 +5,985%(낙폭 -88%) · 10배 +270%(강제 청산 7번, 낙폭 -99%). 2022년에 시작했으면 10배는 그해 11월 거의 0. 실험이니 기록용으로 굴려봐요.")
    p = S["pos"]
    # 1) 강제 청산 확인: 마지막 확인 이후 1시간봉 최저가
    if p:
        try:
            h1 = yf.Ticker(SYM).history(period="5d", interval="1h").dropna(subset=["Low"])
            h1.index = h1.index.tz_convert("UTC")
            since = datetime.fromisoformat(S.get("last_chk") or p["at"])
            low = float(h1[h1.index >= since.replace(minute=0, second=0, microsecond=0)].Low.min())
        except Exception:
            low = px
        low = min(low, px)
        days_held = max(0, (t.date() - datetime.fromisoformat(S.get("fund_day") or p["since"]).date()).days)
        if days_held:
            p["margin"] *= (1 - FUND * LEV) ** days_held; S["fund_day"] = today
        if low <= p["liq"]:
            S["trades"].append({"in": p["since"], "out": today, "entry": p["entry"], "exit": p["liq"], "pl": -1.0, "liq": True})
            S["liq"] += 1
            cp.say(S, "risk", f"💥 강제 청산 — 비트코인이 ${low:,.0f}까지 빠져 청산가 ${p['liq']:,.0f} 터치. 증거금 ${p['margin']:,.0f} 전부 손실.")
            S["pos"] = p = None
    S["last_chk"] = t.isoformat()
    # 2) 새 일봉 마감 때 판단
    if c and S["last_bar"] != d[-1]:
        S["last_bar"] = d[-1]
        m50 = cp.ma(c, 50, len(c) - 1)
        want = m50 is not None and c[-1] > m50
        cp.say(S, "scout", f"비트코인 {d[-1]} 마감 ${c[-1]:,.0f} · 50일선 ${m50:,.0f} ({(c[-1] / m50 - 1) * 100:+.1f}%)")
        if p and not want:
            val = pval(p, px) - p["margin"] * LEV * COST * px / p["entry"]
            S["cash"] += max(0, val)
            pl = val / p["margin0"] - 1
            S["trades"].append({"in": p["since"], "out": today, "entry": p["entry"], "exit": px, "pl": pl, "liq": False})
            cp.say(S, "executor", ff"{LEV}배 롱 정리 @ ${px:,.0f} — 증거금 대비 {pl * 100:+.1f}% (50일선 아래 마감)")
            S["pos"] = p = None
        elif want and not p:
            eqv = S["cash"]
            m = eqv * MARGIN_W
            if m > 10:
                S["cash"] -= m
                fee = m * LEV * COST
                S["pos"] = p = {"since": today, "at": t.isoformat(), "entry": px, "margin0": m, "margin": m - fee, "liq": liq_px(px)}
                S["fund_day"] = today
                cp.say(S, "executor", ff"{LEV}배 롱 진입 @ ${px:,.0f} · 증거금 ${m:,.0f} → 포지션 ${m * LEV:,.0f} · 강제 청산가 ${p['liq']:,.0f}")
        else:
            cp.say(S, "logger", "변화 없음 — " + (f"{LEV}배 롱 유지" if p else "현금 대기 (50일선 아래)"))
    # 3) 평가
    eqv = S["cash"] + (pval(p, px) if p else 0)
    hr = t.strftime("%Y-%m-%dT%H:00")
    if not S["eq"] or S["eq"][-1][0] != hr:
        S["eq"].append([hr, round(eqv, 2)])
    S["eq"] = S["eq"][-2000:]
    peak, mdd = CASH0, 0.0
    for _, v in S["eq"]:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1)
    SF.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    OF.write_text(json.dumps({
        "start": S["start"], "made": t.isoformat(timespec="minutes"), "eq_now": round(eqv, 2), "cash": round(S["cash"], 2), "mdd": mdd,
        "lev": LEV, "btc_ret": px / S["p0"] - 1, "now": px, "liq_n": S["liq"],
        "pos": ({**p, "val": pval(p, px), "pl": pval(p, px) / p["margin0"] - 1, "dist": px / p["liq"] - 1} if p else None),
        "trades": S["trades"][-20:], "chat": S["chat"][-100:], "eq": S["eq"][-500:],
    }, ensure_ascii=False, separators=(",", ":")))
    print(f"{LEV}배 계좌 ${eqv:,.2f} ({eqv / CASH0 - 1:+.2%}) 포지션 {'있음' if p else '없음'} 강제청산 {S['liq']}번")


if __name__ == "__main__":
    run()
