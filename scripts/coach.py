"""
공식 피드백방 (11/22 형 요청) — 계좌마다 '공식을 고쳐 볼 거리'를 내는 코치 봇들
코치 = 이름난 차트 트레이더들의 '공개된 매매 원칙'을 하나씩 맡은 봇 (실제 인물이 아니고, 그 사람들의 말을 지어내지도 않음)
하는 일: 우리 공식을 2년치 1시간봉(코인 3개)으로 다시 돌려서, 각 코치가 맡은 원칙대로 거래를 둘로 나눠 비교 →
        '이 조건을 붙이면 좋아지나?'를 숫자로 확인. 통과 기준(형 원칙: 효과 없으면 안 넣음)을 다 넘어야 '제안'.
        (11/22 형: "보고할 필요 없이 해보면서 계속 수정해") 통과한 것 중 가장 좋은 하나를 스스로 반영 → data/us/formula_cfg.json
        (scripts/formula_rules.py). 모의 계좌들이 다음 실행부터 그 조건으로 매매. 효과가 없어지면 스스로 뺌. 바뀐 건 아침 보고서·사이트에 기록.
통과 기준: 남는 거래 60번↑ · 평균 +0.05R 이상 좋아짐 · 앞 1년·뒤 1년 둘 다 좋아짐 · 코인 3개 중 2개↑ 좋아짐
         · 계좌 기준(R 합계 ÷ 최대 낙폭)도 좋아짐 = 같은 낙폭으로 크기를 맞췄을 때 더 벌어야 함
         (오더블록은 하루 3번↑ 거래 목표도 지켜야 함)
매일 1번 GitHub Actions(.github/workflows/coach.yml) → data/us/coach.json
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import formula_rules as FR

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us/coach.json"
SYMS = ["BTC-USD", "ETH-USD", "SOL-USD"]
NM = {"BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL"}
FEE = 0.0005

COACH = {   # 시험 분야 (11/22 형: 캐릭터 이름 빼고 보기 쉽게 — 무엇을 시험하는지로)
    "wyckoff": ("거래량", "거래량이 실린 자리 vs 약한 자리"),
    "ict": ("시간대·패턴", "FVG·갭 같은 캔들 모양, 런던·뉴욕 장 시작 시간대"),
    "livermore": ("큰 추세", "50일선 방향과 같은 쪽으로만"),
    "minervini": ("손절 폭", "손절 폭이 좁은 자리만"),
    "seykota": ("청산 방법", "목표·추적 손절 숫자 바꾸기"),
    "ptj": ("변동성·주말", "변동성 큰 때·주말 피하기"),
    "judge": ("결론", "통과 기준으로 걸러서 반영할 것 고르기"),
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
    return dict(**FR.context(d), A=atr(d))


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
        out.append(dict(t=d.index[j0], r=net / (risk / e), side=side, risk=risk / e, htf=F["htf"][j0] == side, volhi=bool(F["volhi"][j0]),
                        mvol=(v[i:k + 1].max() / vb) if vb > 0 else np.nan, boxw=(bhi - blo) / A[i - 1]))
        i = j + 1
    return pd.DataFrame(out)


# ---------------- 공식 2: 오더블록 완화판 (scripts/ob_paper.py CFG) ----------------
def ob(d, F, minrr=0.0, need=("sweep",), stop_rule=1, hold=72, W=48, K=2.0, L=20, exitm=0.0):
    """exitm (11/24 형): 0 = 파동 고점에서 절반 익절 + 나머지 본전 손절(지금) · -1 = 파동 고점에서 전부 익절 · 양수 = 그 R배수 익절 하나로 끝(본전 손절 없음)"""
    o, h, l, c, v = (d[k].values for k in ("open", "high", "low", "close", "volume")); A = F["A"]
    body = np.abs(c - o); rng = h - l; bull = c > o; bear = c < o; N = len(c)
    obs = []
    for i in range(L + 3, N - 2):
        for side in (1, -1):
            up, dn = (bull, bear) if side > 0 else (bear, bull)
            if not (up[i] and dn[i - 1]):
                continue
            k = 3 if up[i - 2] else 2
            idx = range(i - k + 1, i + 1); first = i - 1
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
            tgt = wave if exitm <= 0 else fill + s * exitm * risk
            if not be and ((s > 0 and h[k] >= tgt) or (s < 0 and l[k] <= tgt)):
                if exitm != 0:
                    legs.append((rem, max(o[k], tgt) if (s > 0 and k > j) else (min(o[k], tgt) if k > j else tgt))); rem = 0; break
                legs.append((0.5, wave)); rem = 0.5; be = True; stop = fill; continue
            if k > j and be and (-s) in opp.get(k, ()):
                legs.append((rem, c[k])); rem = 0; break
        if rem > 0:
            k = min(N - 1, j + hold - 1); legs.append((rem, c[k]))
        net = sum(w * s * (px / fill - 1) for w, px in legs) - 2 * FEE
        out.append(dict(t=d.index[j], r=net / (risk / e), side=s, risk=risk / e, htf=F["htf"][j] == s, volhi=bool(F["volhi"][j]),
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
def add_time(T):
    return T                                     # 시간대·주말은 formula_rules.FILTERS가 t(진입 시각)로 직접 판단


def acct(T):
    """계좌 기준: 시간순으로 R을 더한 곡선의 합계 / 최대 낙폭 (같은 낙폭에 맞춰 크기를 키우면 얼마나 버나)"""
    if not len(T):
        return 0.0, 0.0, 0.0
    r = T.sort_values("t").r.cumsum(); dd = float((r - r.cummax().clip(lower=0)).min())
    return float(r.iloc[-1]), dd, float(r.iloc[-1] / max(1.0, -dd))


def keep_mask(T, name, thr):
    fn = FR.FILTERS[name][3]
    return T.apply(lambda row: bool(fn(row, thr)), axis=1) if len(T) else pd.Series([], dtype=bool)


def apply_filters(D, filters):
    out = {}
    for s, T in D.items():
        m = pd.Series(True, index=T.index)
        for n, thr in filters.items():
            if n in FR.FILTERS and len(T):
                m &= keep_mask(T, n, thr)
        out[s] = T[m]
    return out


def compare(D0, D1, days, perday_min=None):
    """D0(지금 규칙) vs D1(바꾼 규칙) — 통과 기준 검사"""
    a, b = pd.concat(D0.values()), pd.concat(D1.values())
    if len(b) < 5:
        return dict(ok=False, n=len(b), n0=len(a), why="남는 거래가 거의 없음")
    mid = a.t.min() + (a.t.max() - a.t.min()) / 2
    h = [b[b.t < mid].r.mean() - a[a.t < mid].r.mean(), b[b.t >= mid].r.mean() - a[a.t >= mid].r.mean()]
    coins = sum(D1[k].r.mean() > D0[k].r.mean() for k in D0 if len(D1.get(k, [])) >= 5)
    pdays = sum(len(D1[k]) for k in ("BTC-USD", "ETH-USD") if k in D1) / days
    dR = b.r.mean() - a.r.mean(); ac0, ac = acct(a), acct(b)
    res = dict(n=int(len(b)), n0=int(len(a)), R=round(float(b.r.mean()), 3), R0=round(float(a.r.mean()), 3), dR=round(float(dR), 3),
               h1=round(float(h[0]), 3), h2=round(float(h[1]), 3), coins=int(coins), perday=round(pdays, 2), ac0=ac0, ac=ac)
    fails = []
    if len(b) < 60: fails.append("거래 60번 미만")
    if dR < 0.05: fails.append("좋아진 폭 0.05R 미만")
    if min(h) <= 0: fails.append("앞·뒤 1년 중 한쪽은 나빠짐")
    if coins < 2: fails.append("코인 2개 이상에서 안 통함")
    if ac[2] <= ac0[2]: fails.append("계좌 기준(수익÷낙폭)은 안 좋아짐")
    if perday_min and pdays < perday_min: fails.append(f"BTC·ETH 하루 {pdays:.1f}번 — 하루 {perday_min}번 목표 못 지킴")
    res["ok"] = not fails; res["why"] = " · ".join(fails) if fails else "기준 모두 통과"
    return res


def line(who, idea, res, kind="add"):
    if res.get("ac0") is None:
        return dict(who=who, idea=idea, ok=False, kind=kind, text=f"{idea} → {res.get('why')}", res=res)
    a0, a1 = res["ac0"], res["ac"]
    tx = (f"{idea} → 거래 {res['n0']}번 → {res['n']}번 · 평균 {res['R0']:+.2f}R → {res['R']:+.2f}R ({res['dR']:+.2f}R) · "
          f"앞 1년 {res['h1']:+.2f} / 뒤 1년 {res['h2']:+.2f} · 코인 {res['coins']}/3개 좋아짐 · "
          f"계좌 기준 합계 {a0[0]:+.0f}R(낙폭 {a0[1]:.0f}R) → {a1[0]:+.0f}R(낙폭 {a1[1]:.0f}R), 수익÷낙폭 {a0[2]:.1f} → {a1[2]:.1f} · BTC·ETH 하루 {res['perday']:.1f}번 · "
          + ("✅ 통과" if res["ok"] else f"✗ 보류 ({res['why']})"))
    return dict(who=who, idea=idea, ok=res["ok"], kind=kind, text=tx, res=res)


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
        return f"{name} 실제 매매 {n}번 — 10번 쌓이기 전엔 시험 결과({bt_R:+.2f}R)와 비교 안 해요" + (f" (지금까지 평균 {np.mean(rs):+.2f}R)" if n else ""), None
    m, se = float(np.mean(rs)), float(np.std(rs, ddof=1) / np.sqrt(n))
    bad = m < bt_R - 2 * se
    return f"{name} 실제 {n}번 평균 {m:+.2f}R (시험 {bt_R:+.2f}R, 오차 ±{2 * se:.2f}) → " + ("⚠️ 시험보다 확실히 나쁨 — 규칙대로 도는지 점검" if bad else "시험 결과 범위 안"), bad


FORM = {   # 공식: (이름, 시뮬레이터, 하루 최소 거래, 실제 계좌 파일들)
    "amd": ("AMD (매집→조작→분산)", lambda d, F, P: amd(d, F, rr=P.get("rr", 2.0)), None,
            [("코인 AMD 계좌", ["data/us/amd_paper.json"]), ("코인·코인 10배의 AMD 칸", ["data/us/coin_amd.json", "data/us/lev10.json"])]),
    "ob": ("오더블록 (완화판)", lambda d, F, P: ob(d, F, minrr=P.get("minrr", 0.0), exitm=P.get("exit", 0.0)), 3,
           [("코인 오더블록 계좌", ["data/us/ob_paper.json"]), ("코인·코인 10배의 오더블록 칸", ["data/us/coin_ob.json", "data/us/lev10_ob.json"])]),
    "tr10": ("추세 눌림 (코인 10배 단타)", lambda d, F, P: trend(d, F, tr=P.get("tr", 5.0), sm=P.get("sm", 1.5)), None,
             [("코인 10배 단타 계좌", ["data/us/trend10.json"])]),
}
COOLDOWN_DAYS = 2      # 한 공식은 이틀에 한 번만 바뀜 (한 번에 하나씩, 효과 확인하며)
MAX_FILTERS = 3        # 같은 2년 데이터에 조건을 너무 많이 쌓으면 과최적화 → 공식당 최대 3개


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
    S = json.loads(OUT.read_text()) if OUT.exists() else {}
    C = FR.load(); today = now().date()
    rooms = {}
    for key, (name, sim, pmin, lives) in FORM.items():
        cur = C[key]; P = dict(cur["params"]); filt = dict(cur["filters"])
        raw = {s: add_time(sim(d, F[s], P)) for s, d in B.items()}
        D0 = apply_filters(raw, filt); base = pd.concat(D0.values())
        act = FR.active_text(key, C)
        L = [dict(who="judge", ok=None, text=f"{name} 지금 규칙{(' (+ ' + act + ')') if act else ''} 2년 시험: {len(base)}번 · 승률 {(base.r > 0).mean():.0%} · 평균 {base.r.mean():+.2f}R · BTC·ETH 하루 {(len(D0['BTC-USD']) + len(D0.get('ETH-USD', []))) / days:.1f}번")]
        # 시기별 점검 (11/22 형: 좋은 해·나쁜 해가 있으니 유연하게) — 분기마다 성적, 최근 3개월이 2년 평균보다 확실히 나쁜지
        qs = base.groupby(pd.DatetimeIndex(base.t).to_period("Q")).r.agg(["mean", "size"])
        rec = base[base.t >= base.t.max() - pd.Timedelta(days=90)].r
        se = float(base.r.std() / np.sqrt(max(1, len(rec))))
        L.append(dict(who="judge", ok=None, text="분기별 거래당: " + " · ".join(f"{p}: {m:+.2f}R({int(n)})" for p, (m, n) in qs.iterrows())
                      + f" → 최근 3개월 {rec.mean():+.2f}R ({len(rec)}번)" + (" ⚠️ 2년 평균보다 확실히 나쁨 — 요즘 시장에 안 맞을 수 있음" if len(rec) >= 20 and rec.mean() < base.r.mean() - 2 * se else " — 2년 평균 범위 안")))
        cands = []
        # ① 붙어 있는 조건 빼보기 (효과가 사라졌으면 뺌)
        for n, thr in filt.items():
            rest = {k: v for k, v in filt.items() if k != n}
            m = line(FR.FILTERS[n][2], f"붙여 둔 '{FR.FILTERS[n][0]}' 빼기", compare(D0, apply_filters(raw, rest), days, pmin), "remove")
            m["name"] = n; L.append(m); cands.append(m)
        # ② 새 조건 붙여보기
        for n, (desc, forms, who, fn) in FR.FILTERS.items():
            if key not in forms or n in filt:
                continue
            thr = float(base.risk.quantile(2 / 3)) if n == "risk_narrow" else True
            m = line(who, desc, compare(D0, apply_filters(raw, {**filt, n: thr}), days, pmin)); m["name"] = n; m["thr"] = thr
            if len(filt) >= MAX_FILTERS:
                m["ok"] = False; m["text"] += f" (조건이 이미 {MAX_FILTERS}개라 더 안 붙임)"
            L.append(m); cands.append(m)
        # ③ 숫자 바꿔보기
        for pk, (desc, fk, who, vals) in FR.VARIANTS.items():
            if fk != key:
                continue
            for v in vals:
                if v == P.get(pk):
                    continue
                P1 = {**P, pk: v}
                D1 = apply_filters({s: add_time(sim(d, F[s], P1)) for s, d in B.items()}, filt)
                m = line(who, f"{desc} {P.get(pk):g} → {v:g}", compare(D0, D1, days, pmin), "param"); m["param"] = (pk, v)
                L.append(m); cands.append(m)
        # ④ 실제 계좌 점검
        live = []; worse = False
        for nm_, files in lives:
            tx, bad = live_check(nm_, files, base.r.mean()); live.append(tx); worse |= bool(bad)
        # ⑤ 스스로 반영 (형 지시 11/22: 보고 없이 해보면서 계속 고치기) — 통과한 것 중 '수익÷낙폭'이 가장 좋아지는 하나만
        ok = [m for m in cands if m.get("ok")]
        last = cur.get("changed"); wait = last and (today - datetime.fromisoformat(last).date()).days < COOLDOWN_DAYS
        if ok and not wait:
            best = max(ok, key=lambda m: m["res"]["ac"][2] - m["res"]["ac0"][2])
            if best["kind"] == "remove":
                cur["filters"].pop(best["name"], None)
            elif best["kind"] == "param":
                cur["params"][best["param"][0]] = best["param"][1]
            else:
                cur["filters"][best["name"]] = best["thr"]
            cur["changed"] = today.isoformat()
            r = best["res"]
            C["log"].append(dict(at=now().isoformat(timespec="minutes"), formula=key, who=best["who"], change=best["idea"], kind=best["kind"],
                                 R=[r["R0"], r["R"]], ratio=[round(r["ac0"][2], 2), round(r["ac"][2], 2)], n=[r["n0"], r["n"]]))
            L.append(dict(who="judge", ok=None, applied=True, text=f"🔧 반영함: {COACH[best['who']][0]} '{best['idea']}' — "
                          f"평균 {r['R0']:+.2f}R → {r['R']:+.2f}R, 수익÷낙폭 {r['ac0'][2]:.1f} → {r['ac'][2]:.1f}. 다음 실행부터 계좌에 적용 · {COOLDOWN_DAYS}일 뒤 다시 점검(효과 없어지면 스스로 뺌)"))
        elif ok:
            L.append(dict(who="judge", ok=None, text=f"통과 {len(ok)}개 있지만 {last}에 바꾼 지 {COOLDOWN_DAYS}일이 안 돼서 대기 (한 번에 하나씩 효과 확인)"))
        else:
            L.append(dict(who="judge", ok=None, text="오늘은 기준을 다 넘은 변경 없음 → 지금 공식 그대로 (효과 없는 규칙은 안 넣어요)"))
        if worse:
            L.append(dict(who="judge", ok=None, text="⚠️ 실제 계좌가 시험보다 확실히 나빠요 — Claude가 아침 보고서 때 원인(체결·규칙 차이)을 확인해요"))
        rooms[key] = dict(name=name, base=round(float(base.r.mean()), 3), n=int(len(base)), win=round(float((base.r > 0).mean()), 3),
                          perday=round((len(D0["BTC-USD"]) + len(D0.get("ETH-USD", []))) / days, 2), msgs=L, live=live, active=FR.active_text(key, C))
    FR.save(C)
    made = now().isoformat(timespec="minutes")
    S["runs"] = (S.get("runs", []) + [dict(at=made, applied=[x for x in C["log"] if x["at"] == made])])[-30:]
    S.update(made=made, coach={k: list(v) for k, v in COACH.items()}, rooms=rooms, days=days, log=C["log"][-30:],
             rule=f"2년 1시간봉 BTC·ETH·SOL 시험. 통과: 거래 60번↑ · +0.05R↑ · 앞·뒤 1년 둘 다 · 코인 2/3↑ · 계좌 기준(수익÷낙폭)도 좋아짐 (오더블록은 하루 3번↑도). "
                  f"통과한 것 중 가장 좋은 하나를 스스로 반영 · 공식마다 {COOLDOWN_DAYS}일에 한 번 · 조건 최대 {MAX_FILTERS}개 · 효과 없어지면 스스로 뺌")
    OUT.write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    for k, R in rooms.items():
        print(f"\n== {R['name']} ==")
        for m in R["msgs"]:
            if m.get("ok") or m["who"] == "judge":
                print(f"[{COACH[m['who']][0]}] {m['text']}")
        for x in R["live"]:
            print("  ·", x)


if __name__ == "__main__":
    run()
