"""
코인 오더블록 모의 계좌 (2026-11-21 형 요청) — 가상 $10,000, BTC·ETH·SOL
규칙(형): 오더블록 구간에 닿을 때만 진입(지정가), 안 닿으면 안 들어감.
  OB: 음→양(상승) / 양→음(하락). 3캔들(양→음→양)은 백테스트에서 성적이 나빠 2캔들만 (research/orderblock)
  필터: 몸통 2배(앞 캔들 도지 제외) + 유동성 흡수(직전 20봉 저점/고점을 깸) + FVG(직후 빈 구간)
  손절: OB 만든 캔들들의 꼬리 끝 (기준1, 닿으면 바로)
  익절: OB 뒤 파동 고점 갱신 → 절반 익절 + 나머지 진입가 손절 / 반대 OB 나오면 나머지 정리 / 최대 보유 시간
  상위 시간봉(4시간) OB 구간과 겹치면 '일치'로 기록 (신뢰도 표시·피드백용)
크기: 한 번 손절 시 계좌 손실 1% (손실 최소화) · 노출은 계좌의 최대 5배(10배 증거금 기준 증거금 50% 이내)
하루 거래 횟수 제한 없음 (형 요청). 비용: 한쪽 0.05% (수수료+체결 차이)
매매일지: 진입 이유 · 손절/익절 이유 · 자동 피드백 → data/us/ob_paper.json → 사이트 AI 데스크 '오더블록' 탭
"""
import json, math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us/ob_paper.json"
SYMS = ["BTC-USD", "ETH-USD", "SOL-USD"]
# 11/22 형: '기준 너무 빡빡하게 말고 하루 최소 3번은 거래하면서 고쳐가자' → 필터는 유동성 흡수만, 파동 고점 손익비 조건 끔
#   시험(research/orderblock/freq.py, 1시간봉 2년 3개 코인): 하루 4.1번 · 평균 −0.10R(손실 쪽) → 1회 손실을 1%→0.25%로 줄여 고치는 동안 손실을 작게
#   (예전: 갭+흡수+FVG·손익비 1 → 2년 101번, 하루 0.14번, +0.14R)
CFG = dict(iv="1h", K=2.0, dmin=0.15, L=20, need=("sweep",), W=48, hold=72, minrr=0.0,
           risk=0.0025, maxE=5.0, fee=0.0005, k2=False)
IVMIN = {"5m": 5, "15m": 15, "1h": 60}


def now():
    return datetime.now(timezone.utc)


def bars(sym, iv, period):
    d = yf.Ticker(sym).history(period=period, interval=iv).dropna()
    d.index = d.index.tz_convert("UTC"); d.columns = [c.lower() for c in d.columns]
    m = IVMIN[iv]
    d = d[d.index + pd.Timedelta(minutes=m) <= pd.Timestamp(now())]          # 닫힌 봉만
    return d[["open", "high", "low", "close"]]


def atr(d, n=14):
    pc = d.close.shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().values


def ob_at(d, i, A):
    """봉 i에서 끝난 OB(봉 i+1까지 닫혀야 FVG 판단). 없으면 None"""
    o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values
    L, K = CFG["L"], CFG["K"]
    if i < L + 3 or i + 1 >= len(c):
        return None
    for s in (1, -1):
        up = c[i] > o[i] if s > 0 else c[i] < o[i]
        dn = c[i - 1] < o[i - 1] if s > 0 else c[i - 1] > o[i - 1]
        if not (up and dn):
            continue
        k = 3 if ((c[i - 2] > o[i - 2]) if s > 0 else (c[i - 2] < o[i - 2])) else 2
        if k == 3:
            return None                                         # 3캔들은 백테스트 성적이 나빠 제외
        b0, b1 = abs(c[i - 1] - o[i - 1]), abs(c[i] - o[i])
        doji = b0 < CFG["dmin"] * A[i] or b0 < 0.2 * (h[i - 1] - l[i - 1])
        ratio = b1 / b0 if b0 else 0
        gap = (not doji) and ratio >= K
        if s > 0:
            stop = min(l[i - 1], l[i]); entry = h[i - 1]
            prev = l[i - 1 - L:i - 1].min(); sweep = stop < prev; fvg = l[i + 1] > h[i - 1]
            fvg_sz = l[i + 1] - h[i - 1]
        else:
            stop = max(h[i - 1], h[i]); entry = l[i - 1]
            prev = h[i - 1 - L:i - 1].max(); sweep = stop > prev; fvg = h[i + 1] < l[i - 1]
            fvg_sz = l[i - 1] - h[i + 1]
        if abs(entry - stop) < 0.05 * A[i]:
            return None
        disp = c[i] > h[i - 1] if s > 0 else c[i] < l[i - 1]
        return dict(i=i, t=d.index[i].isoformat(), side=s, entry=float(entry), stop=float(stop), gap=bool(gap), sweep=bool(sweep), fvg=bool(fvg), disp=bool(disp),
                    ratio=round(float(ratio), 2), prev=float(prev), fvg_sz=float(fvg_sz), atr=float(A[i]))
    return None


def htf(sym, base=None):
    """상위 시간봉(4시간 = 1시간봉 4개 묶음) OB 구간 (형성 뒤 48봉, 손절가 밖 마감 전까지 살아 있음)"""
    try:
        b = base if base is not None else bars(sym, "1h", "60d")
        d = b.resample("4h", origin="epoch").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        d = d[d.index + pd.Timedelta(hours=4) <= pd.Timestamp(now())]
    except Exception:
        return []
    A = atr(d); c = d.close.values; Z = []
    for i in range(25, len(d) - 1):
        ob = ob_at(d, i, A)
        if not ob or not ob["disp"]:
            continue
        end = min(len(c) - 1, i + 48)
        for j in range(i + 2, end + 1):
            if (ob["side"] > 0 and c[j] < ob["stop"]) or (ob["side"] < 0 and c[j] > ob["stop"]):
                end = j; break
        lo, hi = sorted([ob["entry"], ob["stop"]])
        Z.append((d.index[i + 1] + pd.Timedelta(hours=4), d.index[end] + pd.Timedelta(hours=4), ob["side"], lo, hi))
    return Z


def say(S, text):
    S["chat"].append({"at": now().isoformat(timespec="seconds"), "text": text}); S["chat"] = S["chat"][-300:]


def fmt(x):
    return f"{x:,.2f}" if x < 1000 else f"{x:,.0f}"


def run():
    S = json.loads(OUT.read_text()) if OUT.exists() else None
    if not S:
        S = {"start": now().date().isoformat(), "cash": 10000.0, "pos": {}, "pend": {}, "journal": [], "chat": [], "eq": [], "last": {}, "cfg": {**CFG, "need": list(CFG["need"])},
             "rule": "오더블록(음→양/양→음 2캔들) 구간 터치 시 지정가 진입 · 필터: 몸통 2배+유동성 흡수+FVG · 손절: OB 꼬리 끝 · 익절: 파동 고점에서 절반+본전 손절, 반대 OB에서 나머지 · 1회 손실 계좌 1% · 거래 횟수 제한 없음"}
        say(S, "── 오더블록 모의 계좌 개설 · 가상 $10,000 · BTC·ETH·SOL 1시간봉 (상위: 4시간봉 OB 겹침) ──")
    iv = CFG["iv"]; px = {}
    for sym in SYMS:
        try:
            d = bars(sym, iv, "60d" if iv == "1h" else "5d")
        except Exception as e:
            print(sym, "시세 실패", e); continue
        if len(d) < 60:
            continue
        Z = htf(sym, d if iv == "1h" else None)
        A = atr(d); o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values; t = d.index
        px[sym] = float(c[-1])
        last = pd.Timestamp(S["last"].get(sym)) if S["last"].get(sym) else t[-2]   # 처음엔 마지막 봉부터
        pend = S["pend"].setdefault(sym, [])
        opp = {}                                                                     # 반대 OB(돌파 있는 것) 형성 봉
        for i in range(25, len(d) - 1):
            ob = ob_at(d, i, A)
            if ob and ob["disp"]:
                opp[i + 1] = ob["side"]
        for k in range(len(d)):
            if t[k] <= last:
                continue
            tk = t[k].isoformat()
            # 1) 보유 중: 손절 → 파동 고점(절반) → 반대 OB → 시간
            p = S["pos"].get(sym)
            if p:
                s = p["side"]; p["bars"] += 1
                p["mfe"] = float(max(p["mfe"], (h[k] - p["fill"]) / p["fill"] * s if s > 0 else (p["fill"] - l[k]) / p["fill"]))
                p["mae"] = float(max(p["mae"], (p["fill"] - l[k]) / p["fill"] if s > 0 else (h[k] - p["fill"]) / p["fill"]))
                hit = l[k] <= p["stop"] if s > 0 else h[k] >= p["stop"]
                if hit:
                    xp = min(o[k], p["stop"]) if s > 0 else max(o[k], p["stop"])
                    close_pos(S, sym, xp, "본전 손절 (절반 익절 뒤)" if p["be"] else f"손절 — 오더블록 꼬리 끝 {fmt(p['stop0'])} 이탈", tk); continue
                if not p["be"] and ((s > 0 and h[k] >= p["wave"]) or (s < 0 and l[k] <= p["wave"])):
                    part(S, sym, 0.5, p["wave"], tk); p["be"] = True; p["stop"] = p["fill"]
                    say(S, f"{sym[:3]} 파동 {'고점' if s > 0 else '저점'} {fmt(p['wave'])} 갱신 → 절반 익절, 나머지는 진입가 {fmt(p['fill'])}에 손절"); continue
                if p["be"] and opp.get(k) == -s:
                    close_pos(S, sym, float(c[k]), f"반대 {'하락' if s > 0 else '상승'} 오더블록 출현 — 상승 근거 소멸, 나머지 정리", tk); continue
                if p["bars"] >= CFG["hold"]:
                    close_pos(S, sym, float(c[k]), f"최대 보유 {CFG['hold']}봉 지남 — 시간 정리", tk); continue
            # 2) 대기 주문: 닿으면 체결, 기한 지나거나 손절가 밖 마감이면 취소
            keep = []
            for q in pend:
                s = q["side"]
                if S["pos"].get(sym):
                    keep.append(q); continue
                if (s > 0 and l[k] <= q["entry"]) or (s < 0 and h[k] >= q["entry"]):
                    if abs(q["wave"] - q["entry"]) < CFG["minrr"] * abs(q["entry"] - q["stop"]):
                        log_skip(S, sym, q, "파동 고점까지 거리가 손절 거리보다 짧아 손익비 부족 — 진입 안 함"); continue
                    fill = min(o[k], q["entry"]) if s > 0 else max(o[k], q["entry"])
                    open_pos(S, sym, q, float(fill), tk, Z); continue
                q["wave"] = max(q["wave"], float(h[k])) if s > 0 else min(q["wave"], float(l[k])); q["age"] += 1
                if (s > 0 and c[k] < q["stop"]) or (s < 0 and c[k] > q["stop"]):
                    log_skip(S, sym, q, "구간에 닿기 전에 손절가 밖에서 마감 — 오더블록 무효"); continue
                if q["age"] >= CFG["W"]:
                    log_skip(S, sym, q, f"{CFG['W']}봉 안에 구간에 안 닿음 — 진입 안 함 (형 규칙)"); continue
                keep.append(q)
            pend = keep
            # 3) 새 오더블록: 봉 k-1에서 끝나고 봉 k로 FVG 확인
            ob = ob_at(d, k - 1, A) if k >= 1 else None
            if ob:
                ok = all(ob[f] for f in CFG["need"])
                if ok:
                    ob.update(sym=sym, wave=float(max(h[k - 1], h[k]) if ob["side"] > 0 else min(l[k - 1], l[k])), age=0)
                    pend.append(ob)
                    say(S, f"{sym[:3]} {'상승' if ob['side'] > 0 else '하락'} 오더블록 발견 ({t[k-1].strftime('%m/%d %H:%M')} UTC) — 진입 대기 {fmt(ob['entry'])} · 손절 {fmt(ob['stop'])}")
        S["pend"][sym] = pend
        S["last"][sym] = t[-1].isoformat()
    eq = equity(S, px)
    S["eq"].append([now().isoformat(timespec="minutes"), round(eq, 2)]); S["eq"] = S["eq"][-3000:]
    S.update(eq_now=round(eq, 2), px=px, made=now().isoformat(timespec="minutes"), n_trades=sum(1 for j in S["journal"] if j.get("exit")))
    OUT.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    print("오더블록 계좌", round(eq, 2), "보유", list(S["pos"]), "대기", {k: len(v) for k, v in S["pend"].items()}, "일지", len(S["journal"]))


def equity(S, px):
    e = S["cash"]
    for sym, p in S["pos"].items():
        if sym in px:
            e += p["qty"] * (px[sym] - p["fill"]) * p["side"]
    return e


def open_pos(S, sym, q, fill, tk, Z):
    s = q["side"]; eq = equity(S, {}); dist = abs(fill - q["stop"]) / fill
    qty = min(eq * CFG["risk"] / (dist * fill), eq * CFG["maxE"] / fill)
    fee = qty * fill * CFG["fee"]; S["cash"] -= fee
    lo, hi = sorted([q["entry"], q["stop"]]); ts = pd.Timestamp(tk)
    mtf = bool(any(z[2] == s and z[0] <= ts <= z[1] and z[3] <= hi and lo <= z[4] for z in Z))
    side = "롱" if s > 0 else "숏"
    why = [f"{'음봉→양봉' if s > 0 else '양봉→음봉'} 2캔들 오더블록 ({q['t'][5:16].replace('T', ' ')} UTC)",
           f"갭: 마지막 캔들 몸통이 앞 캔들의 {q['ratio']}배 (기준 {CFG['K']}배)",
           f"유동성 흡수: 오더블록 {'저점' if s > 0 else '고점'} {fmt(q['stop'])}이 직전 {CFG['L']}봉 {'저점' if s > 0 else '고점'} {fmt(q['prev'])}을 {'깸' if s > 0 else '넘음'} — 개인 손절 물량 흡수",
           f"구조물: 직후 FVG(빈 구간) {fmt(abs(q['fvg_sz']))}",
           f"상위 시간봉: 4시간 오더블록 구간과 {'겹침 ✔ (신뢰도 높음)' if mtf else '안 겹침'}"]
    p = dict(side=s, qty=qty, fill=fill, entry=q["entry"], stop=q["stop"], stop0=q["stop"], wave=q["wave"], be=False, bars=0, at=tk, fee=fee,
             realized=0.0, mfe=0.0, mae=0.0, mtf=mtf, risk_pct=dist, notional=qty * fill, jid=len(S["journal"]))
    S["pos"][sym] = p
    S["journal"].append({"id": p["jid"], "sym": sym, "side": side, "in_at": tk, "fill": round(fill, 4), "stop": round(q["stop"], 4), "target": round(q["wave"], 4),
                         "risk_pct": round(dist * 100, 3), "size": round(qty * fill, 2), "why_in": why, "mtf": mtf, "ob": {k: q[k] for k in ("t", "ratio", "prev", "fvg_sz", "atr")}})
    say(S, f"{sym[:3]} {side} 진입 {fmt(fill)} — 오더블록 구간 터치 · 손절 {fmt(q['stop'])}({dist * 100:.2f}%) · 목표(파동 {'고점' if s > 0 else '저점'}) {fmt(q['wave'])} · ${qty * fill:,.0f}어치 · 4시간 OB {'겹침' if mtf else '안 겹침'}")


def part(S, sym, frac, price, tk):
    p = S["pos"][sym]; q = p["qty"] * frac
    pnl = q * (price - p["fill"]) * p["side"] - q * price * CFG["fee"]
    S["cash"] += pnl; p["realized"] += pnl; p["qty"] -= q
    S["journal"][p["jid"]].setdefault("partial", []).append({"at": tk, "px": round(price, 4), "frac": frac, "why": f"파동 {'고점' if p['side'] > 0 else '저점'} 갱신 — 절반 익절 (익절 기준 1)", "pnl": round(pnl, 2)})


def close_pos(S, sym, price, why, tk):
    p = S["pos"].pop(sym); q = p["qty"]
    pnl = q * (price - p["fill"]) * p["side"] - q * price * CFG["fee"]
    S["cash"] += pnl; tot = p["realized"] + pnl - p["fee"]
    risk_usd = p["risk_pct"] * p["notional"]; R = tot / risk_usd if risk_usd else 0
    J = S["journal"][p["jid"]]
    J.update(exit=round(price, 4), out_at=tk, why_out=why, pnl=round(tot, 2), R=round(R, 2), bars=p["bars"], mfe=round(p["mfe"] * 100, 3), mae=round(p["mae"] * 100, 3))
    J["feedback"] = feedback(p, R, why)
    say(S, f"{sym[:3]} 정리 {fmt(price)} — {why} · {tot:+,.0f}$ ({R:+.2f}R)")


def feedback(p, R, why):
    """자동 피드백 — 다음 매매를 위해 무엇을 볼지 (Claude가 매일 보고서에서 더 붙임)"""
    out = []
    rp = p["risk_pct"] * 100; mfe = p["mfe"] * 100
    if "손절" in why and not p["be"]:
        if p["bars"] <= 2:
            out.append(f"진입 {p['bars']}봉 만에 손절 — 구간이 방어되지 않음. 비슷한 자리(4시간 OB {'겹침' if p['mtf'] else '안 겹침'})의 다음 결과와 비교")
        if mfe >= rp:
            out.append(f"한때 +{mfe:.2f}%(1R 이상)까지 갔다가 손절 — 1R에서 일부 익절했다면 손실을 줄였을 것. 기록 누적 뒤 '1R 부분 익절' 시험")
        if rp < 0.25:
            out.append(f"손절 폭 {rp:.2f}%로 좁음 — 작은 흔들림에 걸렸을 가능성. 손절 폭이 좁은 거래끼리 성적 비교 필요")
        if not out:
            out.append("규칙대로 손절 — 오더블록이 뚫림 = 방어 의지 없음. 손실은 계획한 1R 안에서 끝남")
    elif "본전" in why:
        out.append("절반 익절 뒤 본전 정리 — 손실 없이 끝난 거래. 나머지를 더 길게 가져갈 근거(반대 구조물)가 있었는지 차트로 확인")
    elif "반대" in why:
        out.append(f"반대 오더블록에서 정리 ({R:+.2f}R) — 상승 근거 소멸 규칙대로. 정리 뒤 추가 움직임은 다음 기록에서 비교")
    else:
        out.append(f"{why} ({R:+.2f}R)")
    if p["mtf"]:
        out.append("4시간 오더블록과 겹친 자리 — '겹침' 거래 성적을 따로 모아 신뢰도 검증 중")
    return out


def log_skip(S, sym, q, why):
    S.setdefault("skips", []).append({"at": now().isoformat(timespec="minutes"), "sym": sym, "side": "롱" if q["side"] > 0 else "숏", "t": q["t"], "entry": round(q["entry"], 4), "why": why})
    S["skips"] = S["skips"][-200:]


if __name__ == "__main__":
    run()
