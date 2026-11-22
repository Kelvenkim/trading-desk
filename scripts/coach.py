"""
공식 피드백방 (11/22 형 요청) — 계좌마다 '공식을 고쳐 볼 거리'를 내는 코치 봇들
코치 = 이름난 차트 트레이더들의 '공개된 매매 원칙'을 하나씩 맡은 봇 (실제 인물이 아니고, 그 사람들의 말을 지어내지도 않음)
하는 일: 우리 공식을 2년치 1시간봉(코인 3개)으로 다시 돌려서, 각 코치가 맡은 원칙대로 거래를 둘로 나눠 비교 →
        '이 조건을 붙이면 좋아지나?'를 숫자로 확인. 통과 기준(형 원칙: 효과 없으면 안 넣음)을 다 넘어야 '제안'.
        제안은 자동으로 반영하지 않음 → 형이 확인해야 공식에 들어감.
통과 기준: 남는 거래 60번↑ · 평균 +0.05R 이상 좋아짐 · 앞 1년·뒤 1년 둘 다 좋아짐 · 코인 3개 중 2개↑ 좋아짐
         · 계좌 기준(R 합계 ÷ 최대 낙폭)도 좋아짐 = 같은 낙폭으로 크기를 맞췄을 때 더 벌어야 함
         (오더블록은 하루 3번↑ 거래 목표도 지켜야 함)
매일 1번 GitHub Actions(.github/workflows/coach.yml) → data/us/coach.json
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us/coach.json"
SYMS = ["BTC-USD", "ETH-USD", "SOL-USD"]
NM = {"BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL"}
FEE = 0.0005

COACH = {   # 키: (이름, 맡은 원칙 — 공개적으로 알려진 매매 철학을 요약한 것)
    "wyckoff": ("와이코프식 코치", "매집·분산은 거래량으로 확인한다 — 가짜 이탈(스프링)에 거래량이 실려야 진짜"),
    "ict": ("ICT식 코치", "오더블록·FVG·시간대(런던·뉴욕 장 시작 '킬존')를 본다"),
    "livermore": ("리버모어식 코치", "큰 흐름(상위 추세) 쪽으로만 매매한다"),
    "minervini": ("미너비니식 코치", "손절 폭이 좁은 자리만 고른다 — 위험이 작은 곳에서 크게"),
    "seykota": ("시코타식 코치", "손실은 짧게, 수익은 길게 — 청산 규칙을 바꿔 본다"),
    "ptj": ("튜더 존스식 코치", "방어가 먼저 — 변동성이 너무 클 때·주말 같은 얇은 장은 피한다"),
    "judge": ("Claude (정리)", "코치들 제안을 형 원칙(효과 없으면 안 넣음·손실 최소화)으로 걸러서 정리"),
}


def now():
    return datetime.now(timezone.utc)


def bars(sym):
    d = yf.Ticker(sym).history(period="730d", interval="1h").dropna()
    d.index = d.index.tz_convert("UTC"); d.columns = [c.lower() for c in d.columns]
    return d[["open", "high", "low", "close", "volume"]]


def atr(d, n=14):
    pc = d.close.shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().values


def common(d):
    """모든 공식에 쓰는 공통 특징: 상위 추세(1시간 EMA 1200 ≈ 50일선), 변동성 수준, 시간대"""
    c = d.close
    A = atr(d)
    atrp = pd.Series(A / c.values, index=d.index)
    return dict(htf=np.sign(c - c.ewm(span=1200, adjust=False).mean()).values,
                volhi=(atrp > atrp.rolling(24 * 90, min_periods=24 * 20).median()).values,
                A=A)


# ---------------- 공식 1: AMD (scripts/amd_paper.py 와 같은 규칙) ----------------
def poc_of(h, l, v, rows=24):
    lo, hi = l.min(), h.max(); st = (hi - lo) / rows; prof = np.zeros(rows)
    if st <= 0:
        return (hi + lo) / 2
    for hh, ll, vv in zip(h, l, v):
        if vv <= 0 or hh <= ll:
            continue
        r0 = min(rows - 1, int((ll - lo) / st)); r1 = min(rows - 1, int((hh - lo) / st))
        for r in range(r0, r1 + 1):
            bl = lo + r * st; prof[r] += vv * (min(bl + st, hh) - max(bl, ll)) / (hh - ll)
    return lo + (prof.argmax() + .5) * st


def amd(d, F, rr=2.0, n=24, m=6.0, hold=48):
    o, h, l, c, v = (d[k].values for k in ("open", "high", "low", "close", "volume")); A = F["A"]; N = len(c); out = []; i = n + 20
    while i < N - 2:
        blo, bhi = l[i - n:i].min(), h[i - n:i].max()
        if bhi - blo > m * A[i - 1]:
            i += 1; continue
        side = 1 if l[i] < blo else -1 if h[i] > bhi else 0
        if not side:
            i += 1; continue
        ext = l[i] if side > 0 else h[i]; k = None
        for j in range(i, min(N - 1, i + 3)):
            ext = min(ext, l[j]) if side > 0 else max(ext, h[j])
            if (side > 0 and c[j] > blo) or (side < 0 and c[j] < bhi):
                k = j; break
        if k is None:
            i += 3; continue
        poc = poc_of(h[i - n:i], l[i - n:i], v[i - n:i]); stop = ext - side * 0.1 * A[k]; j0 = None
        for j in range(k + 1, min(N, k + 13)):
            if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
                break
            if (side > 0 and l[j] <= poc) or (side < 0 and h[j] >= poc):
                j0 = j; e = min(o[j], poc) if side > 0 else max(o[j], poc); break
        if j0 is None:
            i = k + 1; continue
        risk = (e - stop) * side
        if risk <= 0.05 * A[k]:
            i = k + 1; continue
        tgt = e + side * rr * risk; x = None; j = j0
        while j < min(N, j0 + hold):
            if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
                x = (min(o[j], stop) if side > 0 else max(o[j], stop)) if j > j0 else stop; break
            if (side > 0 and h[j] >= tgt) or (side < 0 and l[j] <= tgt):
                x = tgt; break
            j += 1
        if x is None:
            j = min(N - 1, j); x = c[j]
        net = side * (x / e - 1) - 2 * FEE
        vb = v[i - n:i].mean()
        out.append(dict(t=d.index[j0], r=net / (risk / e), side=side, risk=risk / e, htf=F["htf"][k] == side, volhi=bool(F["volhi"][k]),
                        mvol=(v[i:k + 1].max() / vb) if vb > 0 else np.nan, boxw=(bhi - blo) / A[i - 1]))
        i = j + 1
    return pd.DataFrame(out)


# ---------------- 공식 2: 오더블록 완화판 (scripts/ob_paper.py CFG) ----------------
def ob(d, F, minrr=0.0, need=("sweep",), stop_rule=1, hold=72, W=48, K=2.0, L=20):
    o, h, l, c, v = (d[k].values for k in ("open", "high", "low", "close", "volume")); A = F["A"]
    body = np.abs(c - o); rng = h - l; bull = c > o; bear = c < o; N = len(c)
    obs = []
    for i in range(L + 3, N - 2):
        for side in (1, -1):
            up, dn = (bull, bear) if side > 0 else (bear, bull)
            if not (up[i] and dn[i - 1]):
                continue
            k = 3 if up[i - 2] else 2; idx = range(i - k + 1, i + 1); first = i - 1
            gap = not (body[first] < 0.15 * A[i] or body[first] < 0.2 * rng[first]) and body[i] >= K * body[first]
            disp = c[i] > h[first] if side > 0 else c[i] < l[first]
            if side > 0:
                st = min(l[j] for j in idx); e = h[first]; sweep = st < l[i - k + 1 - L:i - k + 1].min(); fvg = l[i + 1] > h[i - 1]
            else:
                st = max(h[j] for j in idx); e = l[first]; sweep = st > h[i - k + 1 - L:i - k + 1].max(); fvg = h[i + 1] < l[i - 1]
            if abs(e - st) < 0.05 * A[i]:
                continue
            obs.append(dict(i=i, side=side, e=e, st=st, gap=gap, disp=disp, sweep=sweep, fvg=fvg, k=k,
                            vhi=v[i] > 1.5 * v[max(0, i - 20):i].mean()))
    opp = {}
    for b in obs:
        if b["disp"]:
            opp.setdefault(b["i"], set()).add(b["side"])
    out = []; busy = -1
    for b in obs:
        i, s, e, st = b["i"], b["side"], b["e"], b["st"]
        if i <= busy or any(not b[f] for f in need):
            continue
        j = None; wave = h[i] if s > 0 else l[i]
        for k in range(i + 1, min(N, i + 1 + W)):
            if (s > 0 and l[k] <= e) or (s < 0 and h[k] >= e):
                j = k; break
            wave = max(wave, h[k]) if s > 0 else min(wave, l[k])
            if (s > 0 and c[k] < st) or (s < 0 and c[k] > st):
                break
        if j is None:
            continue
        risk = abs(e - st)
        if abs(wave - e) < minrr * risk:
            continue
        fill = min(o[j], e) if s > 0 else max(o[j], e); legs = []; rem = 1.0; be = False; stop = st
        for k in range(j, min(N, j + hold)):
            hit = (l[k] <= stop) if s > 0 else (h[k] >= stop)
            if stop_rule == 2 and not be:
                hit = (c[k] < stop) if s > 0 else (c[k] > stop)
            if hit:
                px = c[k] if (stop_rule == 2 and not be) else ((min(o[k], stop) if s > 0 else max(o[k], stop)) if k > j else stop)
                legs.append((rem, px)); rem = 0; break
            if not be and ((s > 0 and h[k] >= wave) or (s < 0 and l[k] <= wave)):
                legs.append((0.5, wave)); rem = 0.5; be = True; stop = fill; continue
            if k > j and be and (-s) in opp.get(k, ()):
                legs.append((rem, c[k])); rem = 0; break
        if rem > 0:
            k = min(N - 1, j + hold - 1); legs.append((rem, c[k]))
        net = sum(w * s * (px / fill - 1) for w, px in legs) - 2 * FEE
        out.append(dict(t=d.index[j], r=net / (risk / e), side=s, risk=risk / e, htf=F["htf"][i] == s, volhi=bool(F["volhi"][i]),
                        fvg=b["fvg"], gap=b["gap"], disp=b["disp"], vhi=b["vhi"]))
        busy = k
    return pd.DataFrame(out)


# ---------------- 공식 3: 추세 눌림 (scripts/trend_paper.py CFG) ----------------
def trend(d, F, sm=1.5, tr=5.0, mx=96, rsi_lim=50):
    o, h, l, c = (d[k].values for k in ("open", "high", "low", "close")); A = F["A"]; N = len(c)
    e = lambda n: d.close.ewm(span=n, adjust=False).mean().values
    e20, e50, e200 = e(20), e(50), e(200)
    dl = d.close.diff(); u = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); w = (-dl.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    R = (100 - 100 / (1 + u / w)).values
    out = []; k = 210
    while k < N - 1:
        j = k - 1
        up = e50[j] > e200[j] and c[j] > e200[j]; dn = e50[j] < e200[j] and c[j] < e200[j]; s = 0
        if up and l[j] <= e20[j] and c[j] > o[j] and R[j - 1] < rsi_lim:
            s = 1
        elif dn and h[j] >= e20[j] and c[j] < o[j] and R[j - 1] > 100 - rsi_lim:
            s = -1
        if not s:
            k += 1; continue
        en = o[k]; risk = sm * A[j]; stop = en - s * risk; best = en; x = None; q = k
        while q < min(N, k + mx):
            if (s > 0 and l[q] <= stop) or (s < 0 and h[q] >= stop):
                x = min(o[q], stop) if s > 0 else max(o[q], stop); break
            best = max(best, h[q]) if s > 0 else min(best, l[q]); t_ = best - s * tr * A[q]
            if (s > 0 and t_ > stop) or (s < 0 and t_ < stop):
                stop = t_
            q += 1
        if x is None:
            q = min(N - 1, q); x = c[q]
        net = s * (x / en - 1) - 2 * FEE
        out.append(dict(t=d.index[k], r=net / (risk / en), side=s, risk=risk / en, htf=F["htf"][j] == s, volhi=bool(F["volhi"][j])))
        k = q + 1
    return pd.DataFrame(out)


# ---------------- 평가 ----------------
def acct(T):
    """계좌 기준: 시간순으로 R을 더한 곡선의 합계 / 최대 낙폭 (같은 낙폭에 맞춰 크기를 키우면 얼마나 버나)"""
    r = T.sort_values("t").r.cumsum(); dd = (r - r.cummax().clip(lower=0)).min()
    return float(r.iloc[-1]), float(dd), float(r.iloc[-1] / max(1.0, -dd))


def add_time(T):
    if len(T):
        hr = T.t.dt.hour; T["kill"] = hr.between(7, 10) | hr.between(12, 16)      # 런던·뉴욕 장 시작 (UTC)
        T["wkend"] = T.t.dt.weekday >= 5
    return T


def judge_split(D, keep, days, perday_min=None):
    """D: {코인: 거래표}, keep: 거래표 → bool 시리즈. 통과 기준 검사"""
    allT = pd.concat(D.values()); base = allT.r.mean()
    kept = pd.concat([T[keep(T)] for T in D.values()])
    if len(kept) < 5:
        return dict(ok=False, n=len(kept), why="남는 거래가 거의 없음")
    mid = allT.t.min() + (allT.t.max() - allT.t.min()) / 2
    halves = [(kept[kept.t < mid].r.mean() - allT[allT.t < mid].r.mean()), (kept[kept.t >= mid].r.mean() - allT[allT.t >= mid].r.mean())]
    coins = sum((T[keep(T)].r.mean() - T.r.mean()) > 0 for T in D.values() if keep(T).sum() >= 5)
    dR = kept.r.mean() - base
    pdays = len(pd.concat([T[keep(T)] for k, T in D.items() if k in ("BTC-USD", "ETH-USD")])) / days
    res = dict(n=int(len(kept)), n0=int(len(allT)), R=round(float(kept.r.mean()), 3), R0=round(float(base), 3), dR=round(float(dR), 3),
               h1=round(float(halves[0]), 3), h2=round(float(halves[1]), 3), coins=int(coins), win=round(float((kept.r > 0).mean()), 3), perday=round(pdays, 2),
               kind="filter", ac0=acct(allT), ac=acct(kept))
    fails = []
    if res["ac"][2] <= res["ac0"][2]: fails.append("계좌 기준(수익÷낙폭)은 안 좋아짐")
    if len(kept) < 60: fails.append("거래 60번 미만")
    if dR < 0.05: fails.append("좋아진 폭 0.05R 미만")
    if min(halves) <= 0: fails.append("앞·뒤 1년 중 한쪽은 나빠짐")
    if coins < 2: fails.append("코인 2개 이상에서 안 통함")
    if perday_min and pdays < perday_min: fails.append(f"BTC·ETH 하루 {pdays:.1f}번 — 하루 {perday_min}번 목표 못 지킴")
    res["ok"] = not fails; res["why"] = " · ".join(fails) if fails else "기준 모두 통과"
    return res


def judge_variant(D0, D1, days, perday_min=None):
    a, b = pd.concat(D0.values()), pd.concat(D1.values())
    mid = a.t.min() + (a.t.max() - a.t.min()) / 2
    h = [b[b.t < mid].r.mean() - a[a.t < mid].r.mean(), b[b.t >= mid].r.mean() - a[a.t >= mid].r.mean()]
    # 청산 규칙이 바뀌면 R 단위가 같으니 평균 R로 비교
    coins = sum(D1[k].r.mean() > D0[k].r.mean() for k in D0 if len(D1.get(k, [])) >= 5)
    pdays = sum(len(D1[k]) for k in ("BTC-USD", "ETH-USD") if k in D1) / days
    dR = b.r.mean() - a.r.mean()
    res = dict(n=int(len(b)), n0=int(len(a)), R=round(float(b.r.mean()), 3), R0=round(float(a.r.mean()), 3), dR=round(float(dR), 3),
               h1=round(float(h[0]), 3), h2=round(float(h[1]), 3), coins=int(coins), win=round(float((b.r > 0).mean()), 3), perday=round(pdays, 2),
               kind="variant", ac0=acct(a), ac=acct(b))
    fails = []
    if res["ac"][2] <= res["ac0"][2]: fails.append("계좌 기준(수익÷낙폭)은 안 좋아짐")
    if len(b) < 60: fails.append("거래 60번 미만")
    if dR < 0.05: fails.append("좋아진 폭 0.05R 미만")
    if min(h) <= 0: fails.append("앞·뒤 1년 중 한쪽은 나빠짐")
    if coins < 2: fails.append("코인 2개 이상에서 안 통함")
    if perday_min and pdays < perday_min: fails.append(f"하루 {pdays:.1f}번 — 하루 {perday_min}번 목표 못 지킴")
    res["ok"] = not fails; res["why"] = " · ".join(fails) if fails else "기준 모두 통과"
    return res


def line(who, idea, res):
    if res.get("n0") is None:
        return dict(who=who, idea=idea, ok=False, text=f"{idea} → {res.get('why')}", res=res)
    cnt = f"시험 {res['n0']}번 중 {res['n']}번 남음" if res.get("kind") == "filter" else f"거래 {res['n0']}번 → {res['n']}번"
    a0, a1 = res["ac0"], res["ac"]
    tx = (f"{idea} → {cnt} · 평균 {res['R0']:+.2f}R → {res['R']:+.2f}R ({res['dR']:+.2f}R) · "
          f"앞 1년 {res['h1']:+.2f} / 뒤 1년 {res['h2']:+.2f} · 코인 {res['coins']}/3개 좋아짐 · "
          f"계좌 기준 합계 {a0[0]:+.0f}R(낙폭 {a0[1]:.0f}R) → {a1[0]:+.0f}R(낙폭 {a1[1]:.0f}R), 수익÷낙폭 {a0[2]:.1f} → {a1[2]:.1f} · BTC·ETH 하루 {res['perday']:.1f}번 · "
          + ("✅ 제안 — 형 확인 필요" if res["ok"] else f"✗ 보류 ({res['why']})"))
    return dict(who=who, idea=idea, ok=res["ok"], text=tx, res=res)


def live_check(name, files, bt_R):
    """실제 계좌 매매일지 vs 시험 평균"""
    rs = []
    for f in files:
        try:
            S = json.loads((ROOT / f).read_text())
        except Exception:
            continue
        rs += [j["R"] for j in S.get("journal", []) if j.get("exit") is not None and j.get("R") is not None]
        rs += [t["R"] for t in S.get("trades", []) if t.get("R") is not None]
    n = len(rs)
    if n < 10:
        return f"{name} 실제 매매 {n}번 — 10번 쌓이기 전엔 시험 결과({bt_R:+.2f}R)와 비교 안 해요" + (f" (지금까지 평균 {np.mean(rs):+.2f}R)" if n else "")
    m, se = float(np.mean(rs)), float(np.std(rs, ddof=1) / np.sqrt(n))
    flag = "⚠️ 시험보다 확실히 나쁨 — 규칙대로 돌고 있는지 점검" if m < bt_R - 2 * se else "시험 결과 범위 안"
    return f"{name} 실제 {n}번 평균 {m:+.2f}R (시험 {bt_R:+.2f}R, 오차 ±{2 * se:.2f}) → {flag}"


def run():
    B = {}
    for s in SYMS:
        try:
            B[s] = bars(s)
        except Exception as e:
            print(s, "시세 실패", e)
    if len(B) < 2:
        print("시세 부족 — 건너뜀"); return
    F = {s: common(d) for s, d in B.items()}
    days = (B["BTC-USD"].index[-1] - B["BTC-USD"].index[0]).days
    S = json.loads(OUT.read_text()) if OUT.exists() else {"runs": []}
    rooms = {}

    # ===== AMD =====
    D = {s: add_time(amd(d, F[s])) for s, d in B.items()}
    base = pd.concat(D.values())
    L = [dict(who="judge", ok=None, text=f"AMD 지금 규칙 2년 시험: {len(base)}번 · 승률 {(base.r > 0).mean():.0%} · 평균 {base.r.mean():+.2f}R · BTC·ETH 하루 {(len(D['BTC-USD']) + len(D.get('ETH-USD', []))) / days:.1f}번")]
    L.append(line("wyckoff", "조작(가짜 이탈) 봉 거래량이 박스 평균 1.5배↑일 때만", judge_split(D, lambda T: T.mvol >= 1.5, days)))
    L.append(line("wyckoff", "조작 봉 거래량이 약할 때(1.5배 미만)만", judge_split(D, lambda T: T.mvol < 1.5, days)))
    L.append(line("ict", "런던·뉴욕 장 시작 시간대(킬존)에 들어간 것만", judge_split(D, lambda T: T.kill, days)))
    L.append(line("livermore", "상위 추세(≈50일선) 쪽 방향만", judge_split(D, lambda T: T.htf, days)))
    L.append(line("minervini", "손절 폭이 좁은 쪽 2/3만 (넓은 1/3 버림)", judge_split(D, lambda T: T.risk <= base.risk.quantile(2 / 3), days)))
    L.append(line("minervini", "박스가 좁은 것(폭 ATR×4 이하)만", judge_split(D, lambda T: T.boxw <= 4, days)))
    for rr in (1.5, 3.0):
        D1 = {s: add_time(amd(d, F[s], rr=rr)) for s, d in B.items()}
        L.append(line("seykota", f"목표 손익비 2 → {rr:g}", judge_variant(D, D1, days)))
    L.append(line("ptj", "변동성이 평소보다 낮을 때만", judge_split(D, lambda T: ~T.volhi, days)))
    L.append(line("ptj", "주말 빼기", judge_split(D, lambda T: ~T.wkend, days)))
    rooms["amd"] = dict(name="AMD (매집→조작→분산)", base=round(float(base.r.mean()), 3), msgs=L,
                        live=[live_check("코인 AMD 계좌", ["data/us/amd_paper.json"], base.r.mean()),
                              live_check("코인·코인 10배의 AMD 칸", ["data/us/coin_amd.json", "data/us/lev10.json"], base.r.mean())])

    # ===== 오더블록 완화판 =====
    D = {s: add_time(ob(d, F[s])) for s, d in B.items()}
    base = pd.concat(D.values())
    L = [dict(who="judge", ok=None, text=f"오더블록(완화판) 2년 시험: {len(base)}번 · 승률 {(base.r > 0).mean():.0%} · 평균 {base.r.mean():+.2f}R · BTC·ETH 하루 {(len(D['BTC-USD']) + len(D.get('ETH-USD', []))) / days:.1f}번 (목표 3번↑)")]
    L.append(line("ict", "OB 다음 봉에 FVG(빈 구간) 있는 것만", judge_split(D, lambda T: T.fvg, days, 3)))
    L.append(line("ict", "갭(강한 마지막 캔들) 있는 것만", judge_split(D, lambda T: T.gap, days, 3)))
    L.append(line("ict", "킬존 시간대(런던·뉴욕 장 시작)만", judge_split(D, lambda T: T.kill, days, 3)))
    L.append(line("wyckoff", "OB 마지막 캔들 거래량 1.5배↑만", judge_split(D, lambda T: T.vhi, days, 3)))
    L.append(line("livermore", "상위 추세(≈50일선) 쪽 방향만", judge_split(D, lambda T: T.htf, days, 3)))
    L.append(line("minervini", "손절 폭이 좁은 쪽 2/3만", judge_split(D, lambda T: T.risk <= base.risk.quantile(2 / 3), days, 3)))
    D1 = {s: add_time(ob(d, F[s], stop_rule=2)) for s, d in B.items()}
    L.append(line("seykota", "손절을 '꼬리 닿으면' → '꼬리 밖에서 봉 마감하면'", judge_variant(D, D1, days, 3)))
    D1 = {s: add_time(ob(d, F[s], minrr=1.0)) for s, d in B.items()}
    L.append(line("seykota", "파동 고점까지 손익비 1↑인 자리만 (예전 조건 다시)", judge_variant(D, D1, days, 3)))
    L.append(line("ptj", "변동성이 평소보다 낮을 때만", judge_split(D, lambda T: ~T.volhi, days, 3)))
    L.append(line("ptj", "주말 빼기", judge_split(D, lambda T: ~T.wkend, days, 3)))
    rooms["ob"] = dict(name="오더블록 (완화판)", base=round(float(base.r.mean()), 3), msgs=L,
                       live=[live_check("코인 오더블록 계좌", ["data/us/ob_paper.json"], base.r.mean()),
                             live_check("코인·코인 10배의 오더블록 칸", ["data/us/coin_ob.json", "data/us/lev10_ob.json"], base.r.mean())])

    # ===== 추세 눌림 (코인 10배 단타) =====
    D = {s: add_time(trend(d, F[s])) for s, d in B.items()}
    base = pd.concat(D.values())
    L = [dict(who="judge", ok=None, text=f"추세 눌림 2년 시험: {len(base)}번 · 승률 {(base.r > 0).mean():.0%} · 평균 {base.r.mean():+.2f}R")]
    L.append(line("livermore", "상위 추세(≈50일선)도 같은 방향일 때만", judge_split(D, lambda T: T.htf, days)))
    L.append(line("ict", "킬존 시간대만", judge_split(D, lambda T: T.kill, days)))
    L.append(line("minervini", "손절 폭이 좁은 쪽 2/3만", judge_split(D, lambda T: T.risk <= base.risk.quantile(2 / 3), days)))
    for tr in (3.0, 8.0):
        D1 = {s: add_time(trend(d, F[s], tr=tr)) for s, d in B.items()}
        L.append(line("seykota", f"추적 손절 ATR×5 → ×{tr:g}", judge_variant(D, D1, days)))
    L.append(line("ptj", "변동성이 평소보다 낮을 때만", judge_split(D, lambda T: ~T.volhi, days)))
    L.append(line("ptj", "주말 빼기", judge_split(D, lambda T: ~T.wkend, days)))
    rooms["tr10"] = dict(name="추세 눌림 (코인 10배 단타)", base=round(float(base.r.mean()), 3), msgs=L,
                         live=[live_check("코인 10배 단타 계좌", ["data/us/trend10.json"], base.r.mean())])

    # 정리
    for k, R in rooms.items():
        ok = [m for m in R["msgs"] if m.get("ok")]
        R["msgs"].append(dict(who="judge", ok=None, text=(f"오늘 기준 통과 {len(ok)}개: " + " / ".join(f"{COACH[m['who']][0]} '{m['idea']}' ({m['res']['dR']:+.2f}R)" for m in ok)
                                                       + " → 형이 OK하면 공식에 넣고 그림도 다시 그려요. 여러 개를 한 번에 넣진 않아요(한 번에 하나씩).")
                              if ok else "오늘은 기준을 다 넘은 제안 없음 → 지금 공식 그대로 (효과 없는 규칙은 안 넣어요)"))
    made = now().isoformat(timespec="minutes")
    S["runs"] = (S.get("runs", []) + [dict(at=made, passed={k: [m["idea"] for m in R["msgs"] if m.get("ok")] for k, R in rooms.items()})])[-30:]
    S.update(made=made, coach={k: list(v) for k, v in COACH.items()}, rooms=rooms, days=days,
             rule="코치 = 공개된 매매 원칙을 맡은 봇(실제 인물 아님). 2년 1시간봉 BTC·ETH·SOL 시험. 통과: 거래 60번↑ · +0.05R↑ · 앞·뒤 1년 둘 다 · 코인 2/3↑ · 계좌 기준(수익÷낙폭)도 좋아짐 (오더블록은 하루 3번↑도). 자동 반영 안 함 — 형 확인 뒤 반영")
    OUT.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    for k, R in rooms.items():
        print(f"\n== {R['name']} ==")
        for m in R["msgs"]:
            print(f"[{COACH[m['who']][0]}] {m['text']}")
        for x in R["live"]:
            print("  ·", x)


if __name__ == "__main__":
    run()
