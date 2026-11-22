"""
코인 AMD(매집 → 조작 → 분산) 모의 계좌 (11/22 형 아이디어, 그림 formulas/amd.png) — 가상 $10,000, BTC·ETH·SOL 1시간봉
매시간 GitHub Actions(ob.yml)에서 밀린 봉까지 순서대로 처리. 규칙은 research/amd/amd.py 2년 시험에서 고름:
  ① 매집: 최근 24봉 박스(최고가~최저가) 폭 ≤ ATR(14) × 6 → 박스 안 볼륨 프로파일로 POC
  ② 조작: 박스 아래(위)를 깨는 봉 → 3봉 안에 다시 박스 안으로 마감 (가짜 이탈, 손절 물량 쓸기)
  ③ 진입: POC 지정가 (12봉 안에 닿으면, 더 좋은 가격으로 열리면 그 가격) · 그 전에 손절가에 닿으면 취소
  손절: 조작 극단(꼬리 끝) ± ATR × 0.1 · ④ 목표: 손익비 2 · 최대 48봉
  크기: 한 번 손절 시 계좌 손실 0.5% (손실 최소화 — 시험상 최대 낙폭 약 −13%) · 노출 최대 계좌 5배
  비용: 한쪽 0.05%. 시험: 2년 1,567번 · 승률 46% · 평균 +0.18R · 코인 3개·앞뒤 1년 모두 플러스 (단, 비용 0.1%면 거의 본전)
매매일지(진입·손절/익절 이유·자동 피드백) → data/us/amd_paper.json → 사이트 AI 데스크 '코인 AMD' 탭
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
OUT = ROOT / "data/us/amd_paper.json"
SYMS = ["BTC-USD", "ETH-USD", "SOL-USD"]
CFG = dict(N=24, m=6.0, reclaim=3, W=12, rr=2.0, hold=48, buf=0.1, risk=0.005, maxE=5.0, fee=0.0005, rows=24)
NM = {"BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL"}


def now():
    return datetime.now(timezone.utc)


def bars(sym):
    d = yf.Ticker(sym).history(period="180d", interval="1h").dropna()
    d.index = d.index.tz_convert("UTC"); d.columns = [c.lower() for c in d.columns]
    d = d[d.index + pd.Timedelta(hours=1) <= pd.Timestamp(now())]
    return d[["open", "high", "low", "close", "volume"]]


def atr(d, n=14):
    pc = d.close.shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().values


def poc_of(h, l, v, rows):
    lo, hi = l.min(), h.max(); st = (hi - lo) / rows; prof = np.zeros(rows)
    for hh, ll, vv in zip(h, l, v):
        if vv <= 0 or hh <= ll:
            continue
        r0 = min(rows - 1, int((ll - lo) / st)); r1 = min(rows - 1, int((hh - lo) / st))
        for r in range(r0, r1 + 1):
            bl = lo + r * st; prof[r] += vv * (min(bl + st, hh) - max(bl, ll)) / (hh - ll)
    return float(lo + (prof.argmax() + .5) * st)


def f(x):
    return f"{x:,.2f}" if abs(x) < 1000 else f"{x:,.0f}"


def say(S, who, text):
    S["chat"].append({"at": now().isoformat(timespec="seconds"), "who": who, "text": text}); S["chat"] = S["chat"][-400:]


def run():
    global FC
    FC = FR.load(); CFG.update(FR.params("amd"))                 # 코치(scripts/coach.py)가 바꾼 숫자·조건
    S = json.loads(OUT.read_text()) if OUT.exists() else None
    if not S:
        S = {"start": now().date().isoformat(), "cash": 10000.0, "pos": {}, "pend": {}, "manip": {}, "journal": [], "chat": [], "eq": [], "last": {},
             "rule": "1시간봉 · 24봉 박스(폭 ≤ ATR×6)에 POC → 박스를 가짜로 깼다가 3봉 안에 복귀(조작) → POC 지정가 진입 · 손절 조작 꼬리 끝 · 목표 손익비 2 · 1회 손실 0.5%", "cfg": CFG}
        say(S, "claude", "── 코인 AMD(매집→조작→분산) 계좌 개설 · 가상 $10,000 · BTC·ETH·SOL 1시간봉 ──")
    S.setdefault("manip", {})
    px = {}
    for sym in SYMS:
        try:
            d = bars(sym)
        except Exception as e:
            print(sym, "시세 실패", e); continue
        if len(d) < CFG["N"] + 30:
            continue
        A = atr(d); o, h, l, c, v = (d[k].values for k in ("open", "high", "low", "close", "volume")); t = d.index
        CTX[sym] = FR.context(d)
        px[sym] = float(c[-1])
        last = pd.Timestamp(S["last"][sym]) if S["last"].get(sym) else t[-2]
        for j in range(CFG["N"] + 20, len(d)):
            if t[j] <= last:
                continue
            step(S, sym, j, o, h, l, c, v, A, t)
        S["last"][sym] = t[-1].isoformat()
    eq = S["cash"] + sum(p["qty"] * (px.get(s, p["fill"]) - p["fill"]) * p["side"] for s, p in S["pos"].items())
    S["eq"].append([now().isoformat(timespec="minutes"), round(eq, 2)]); S["eq"] = S["eq"][-3000:]
    done = [j for j in S["journal"] if j.get("exit") is not None]
    S.update(eq_now=round(eq, 2), px=px, made=now().isoformat(timespec="minutes"), n_trades=len(done), coach=FR.active_text("amd", FC))
    OUT.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    print("AMD 계좌", round(eq, 2), "보유", list(S["pos"]), "대기", list(S["pend"]), "끝난 거래", len(done))


def step(S, sym, j, o, h, l, c, v, A, t):
    tk = t[j].isoformat(); nm = NM[sym]
    p = S["pos"].get(sym)
    if p:                                                          # 보유 중: 손절 → 목표 → 시간
        s = p["side"]; p["bars"] += 1
        p["mfe"] = max(p["mfe"], (h[j] / p["fill"] - 1) * s if s > 0 else (1 - l[j] / p["fill"]))
        p["mae"] = max(p["mae"], (1 - l[j] / p["fill"]) if s > 0 else (h[j] / p["fill"] - 1))
        if (s > 0 and l[j] <= p["stop"]) or (s < 0 and h[j] >= p["stop"]):
            xp = (min(o[j], p["stop"]) if s > 0 else max(o[j], p["stop"])) if p["bars"] > 1 else p["stop"]
            close(S, sym, xp, "손절 — 조작 꼬리 끝을 다시 깸 (가짜 이탈이 아니라 진짜 이탈이었음)", tk)
        elif (s > 0 and h[j] >= p["target"]) or (s < 0 and l[j] <= p["target"]):
            close(S, sym, p["target"], f"목표 도달 (손익비 {CFG['rr']:.0f}) — 분산 구간에서 수익 실현", tk)
        elif p["bars"] >= CFG["hold"]:
            close(S, sym, float(c[j]), f"최대 보유 {CFG['hold']}봉 — 시간 정리", tk)
        return
    q = S["pend"].get(sym)
    if q:                                                          # POC 지정가 대기
        s = q["side"]; q["left"] -= 1
        if (s > 0 and l[j] <= q["stop"]) or (s < 0 and h[j] >= q["stop"]):
            say(S, "risk", f"{nm} 대기 취소 — POC에 닿기 전에 손절가를 깸"); S["pend"].pop(sym); return
        if (s > 0 and l[j] <= q["poc"]) or (s < 0 and h[j] >= q["poc"]):
            e = float(min(o[j], q["poc"]) if s > 0 else max(o[j], q["poc"]))
            S["pend"].pop(sym)
            X = CTX[sym]
            bad = FR.check("amd", dict(t=t[j], htf=X["htf"][j] == s, volhi=bool(X["volhi"][j]), risk=(e - q["stop"]) * s / e,
                                       mvol=q.get("mvol", 1.0), boxw=q["width_atr"]), FC)
            if bad:
                say(S, "risk", f"{nm} POC 체결 자리지만 진입 안 함 — 공식 점검이 붙인 조건 불통과: {' · '.join(bad)}"); return
            q["feat"] = FR.feat(X, j, s, t[j], (e - q["stop"]) * s / e, mvol=q.get("mvol", 1.0), boxw=q["width_atr"])
            open_pos(S, sym, q, e, tk)
            step_same_bar(S, sym, j, o, h, l, c, tk)
            return
        if q["left"] <= 0:
            say(S, "risk", f"{nm} 대기 취소 — {CFG['W']}봉 안에 POC로 안 돌아옴"); S["pend"].pop(sym)
        return
    m = S["manip"].get(sym)
    if m:                                                          # 조작 진행 중: 박스 안으로 마감하나
        s = m["side"]; m["ext"] = float(min(m["ext"], l[j]) if s > 0 else max(m["ext"], h[j])); m["n"] += 1
        m["mv"] = float(max(m.get("mv", 0.0), v[j])); m["mvol"] = round(m["mv"] / m["vb"], 2) if m.get("vb") else 1.0
        if (s > 0 and c[j] > m["blo"]) or (s < 0 and c[j] < m["bhi"]):
            reclaim(S, sym, m, A[j], tk); S["manip"].pop(sym)
        elif m["n"] >= CFG["reclaim"]:
            S["manip"].pop(sym)                                    # 3봉 안에 못 돌아옴 = 진짜 이탈
        return
    N = CFG["N"]; blo, bhi = float(l[j - N:j].min()), float(h[j - N:j].max())
    if bhi - blo > CFG["m"] * A[j - 1]:
        return
    s = 1 if l[j] < blo else -1 if h[j] > bhi else 0
    if not s:
        return
    poc = poc_of(h[j - N:j], l[j - N:j], v[j - N:j], CFG["rows"])
    vb = float(v[j - N:j].mean())
    m = dict(side=s, blo=blo, bhi=bhi, poc=poc, ext=float(l[j] if s > 0 else h[j]), n=1, at=tk, width_atr=round((bhi - blo) / A[j - 1], 1), box_from=t[j - N].isoformat(),
             vb=vb, mv=float(v[j]), mvol=round(float(v[j]) / vb, 2) if vb > 0 else 1.0)
    if (s > 0 and c[j] > blo) or (s < 0 and c[j] < bhi):          # 같은 봉에 바로 복귀 (긴 꼬리)
        reclaim(S, sym, m, A[j], tk)
    else:
        S["manip"][sym] = m


def reclaim(S, sym, m, a, tk):
    s = m["side"]; stop = m["ext"] - s * CFG["buf"] * a
    if (m["poc"] - stop) * s <= 0.05 * a:
        return
    S["pend"][sym] = dict(m, stop=float(stop), left=CFG["W"], reclaim_at=tk)
    say(S, "scout", f"{NM[sym]} {'롱' if s > 0 else '숏'} 준비 — 박스 {f(m['blo'])}~{f(m['bhi'])}({m['width_atr']}ATR) {'아래' if s > 0 else '위'}를 {f(m['ext'])}까지 깼다가 복귀 → POC {f(m['poc'])} 지정가 대기 (손절 {f(stop)})")


def open_pos(S, sym, q, e, tk):
    s = q["side"]; risk = (e - q["stop"]) * s
    eq = S["cash"]; qty = min(eq * CFG["risk"] / risk, eq * CFG["maxE"] / e)
    fee = qty * e * CFG["fee"]; S["cash"] -= fee
    tgt = e + s * CFG["rr"] * risk
    why = [f"① 매집: {q['box_from'][5:16].replace('T', ' ')}부터 24봉 박스 {f(q['blo'])}~{f(q['bhi'])} (폭 {q['width_atr']} ATR) · POC {f(q['poc'])}",
           f"② 조작: 박스 {'아래' if s > 0 else '위'}를 {f(q['ext'])}까지 깼다가 {q['reclaim_at'][5:16].replace('T', ' ')} 봉에 박스 안으로 마감",
           (f"③ 진입: POC {f(q['poc'])}로 되돌아와 {f(e)}에 체결" if (e - q['poc']) * s >= -1e-9 else f"③ 진입: 복귀 뒤 가격이 POC {f(q['poc'])}보다 {'아래' if s > 0 else '위'}(더 좋은 자리)라 {f(e)}에 바로 체결") + f" · 손절 {f(q['stop'])}(조작 꼬리 끝 밖) · 목표 {f(tgt)}(손익비 {CFG['rr']:.0f})"]
    jid = len(S["journal"])
    S["journal"].append(dict(id=jid, sym=sym, side="롱" if s > 0 else "숏", in_at=tk, fill=round(e, 4), stop=round(q["stop"], 4), target=round(tgt, 4),
                             risk_pct=round(risk / e * 100, 2), size=round(qty * e, 2), why_in=why, exit=None, feat=q.get("feat")))
    S["pos"][sym] = dict(side=s, qty=float(qty), fill=e, stop=float(q["stop"]), target=float(tgt), bars=0, at=tk, fee=float(fee), risk_usd=float(qty * risk),
                         risk_pct=risk / e, mfe=0.0, mae=0.0, jid=jid)
    say(S, "executor", f"{NM[sym]} {'롱' if s > 0 else '숏'} {f(e)} 진입 — POC 되돌림 · 손절 {f(q['stop'])} ({risk / e * 100:.2f}%) · 목표 {f(tgt)} · 계좌의 {qty * e / eq:.1f}배")


def step_same_bar(S, sym, j, o, h, l, c, tk):
    p = S["pos"].get(sym)
    if not p:
        return
    s = p["side"]
    if (s > 0 and l[j] <= p["stop"]) or (s < 0 and h[j] >= p["stop"]):
        close(S, sym, p["stop"], "손절 — 진입한 봉에서 바로 조작 꼬리 끝을 깸", tk)
    elif (s > 0 and h[j] >= p["target"]) or (s < 0 and l[j] <= p["target"]):
        close(S, sym, p["target"], "목표 도달 — 진입한 봉에서 바로", tk)


def close(S, sym, xp, why, tk):
    p = S["pos"].pop(sym); s = p["side"]; xp = float(xp)
    pnl = p["qty"] * (xp - p["fill"]) * s - p["qty"] * xp * CFG["fee"]; S["cash"] += pnl
    tot = pnl - p["fee"]; R = tot / p["risk_usd"] if p["risk_usd"] else 0
    J = S["journal"][p["jid"]]
    J.update(exit=round(xp, 4), out_at=tk, why_out=why, pnl=round(tot, 2), R=round(R, 2), bars=p["bars"],
             mfe=round(p["mfe"] * 100, 2), mae=round(p["mae"] * 100, 2), feedback=feedback(p, R, why))
    say(S, "risk", f"{NM[sym]} {'롱' if s > 0 else '숏'} 정리 {f(xp)} — {why} · {tot:+,.0f}$ ({R:+.2f}R, {p['bars']}봉)")


def feedback(p, R, why):
    out = []; rp = p["risk_pct"] * 100; mfe = p["mfe"] * 100
    if "손절" in why:
        if p["bars"] <= 2:
            out.append(f"{p['bars']}봉 만에 손절 — 복귀가 약했음. 복귀 봉 몸통 크기·거래량을 다음 기록과 비교")
        if mfe >= rp:
            out.append(f"한때 +{mfe:.2f}%(1R 이상) 갔다가 손절 — 1R 본전 이동을 시험할 근거로 기록")
        if not out:
            out.append("규칙대로 손절 — 이탈이 가짜가 아니었음. 손실은 계획한 1R 안")
    elif "목표" in why:
        out.append(f"분산까지 이어짐 ({R:+.2f}R) — 목표 뒤 추가 움직임을 기록해 손익비 3 목표와 비교")
    else:
        out.append(f"{why} ({R:+.2f}R) — 시간 안에 목표·손절 둘 다 안 닿음 = 매집이 더 길었을 수 있음")
    return out


if __name__ == "__main__":
    import sys
    # 11/22 형: 코인·코인 10배 계좌는 AMD + 오더블록을 같이 씀 → 계좌 돈을 1/3씩 나눈 세 칸(AMD·오더블록·50일선 칸, 11/22 저녁부터)으로 굴리고 사이트에서 합쳐 보여줌
    #   위험은 '전체 계좌' 기준으로 맞춤: 칸 안 위험 % = 전체 기준 × 3
    prof = sys.argv[1] if len(sys.argv) > 1 else ""
    if prof == "lev10":      # 코인 10배 AMD 칸: 비트코인 · 한 번 손절 시 전체 계좌 −2% · 노출 최대 10배 (시험 BTC 2년 550번: 평균 노출 4.6배·+84%·최대 낙폭 −34%)
        OUT = ROOT / "data/us/lev10.json"; SYMS = ["BTC-USD"]; CFG.update(risk=0.06, maxE=10.0)
    elif prof == "coin":     # 코인(1배) AMD 칸: BTC·ETH · 한 번 손절 시 전체 계좌 −1% · 레버리지 없음(노출 최대 1배)
        OUT = ROOT / "data/us/coin_amd.json"; SYMS = ["BTC-USD", "ETH-USD"]; CFG.update(risk=0.03, maxE=1.0)
    run()
