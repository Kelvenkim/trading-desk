"""BOS / CHoCH 자동매매 시험 (11/28 형 요청 — '차트를 읽는 눈' 5~7장을 규칙으로)
규칙은 결과 보기 전에 고정. 앞뒤 기간을 나눠 둘 다 확인.

구조 판정 (미래 정보 없음)
  스윙 고점/저점 = 앞뒤 K봉 중 최고/최저. K봉이 지나야 '확정'(그 전엔 모름)
  종가가 마지막 확정 스윙 고점 위 마감 → 추세가 이미 상승이면 BOS↑, 아니면 CHoCH↑ (저점 쪽은 반대)
  디스플레이스먼트 = 깨는 캔들 몸통 ≥ 직전 20봉 평균 몸통 × 1.5 이고 몸통/전체길이 ≥ 0.6

전략 (진입은 신호 다음 봉 시가, 지정가는 FVG 끝)
  S1 CHoCH 바로      : CHoCH 나면 그 방향 진입 (책: 하지 말라)
  S2 CHoCH→BOS 확인  : CHoCH 뒤 같은 방향 첫 BOS에서 진입
  S3 BOS 추세 따라가기: 추세 방향 BOS마다 진입
  S4 S2 + 디스플레이스먼트: CHoCH·BOS 둘 다 디스플레이스먼트일 때만
  S5 CHoCH 뒤 FVG 되돌림: 디스플레이스먼트 CHoCH가 FVG를 남기면 FVG 가운데(50%)에 지정가(20봉 안), 책 3부 방식
손절: 롱=진입 직전 확정 스윙 저점(S5는 임펄스 시작 저점) / 숏 반대. 손절폭이 ATR×0.3 미만이면 건너뜀
청산: A=2R 고정 익절 / B=반대 방향 CHoCH가 나면 종가 청산(구조 추적). 둘 다 손절 우선, 최대 보유 200봉
비용: 한쪽 0.05% (오더블록 시험과 같음) → R로 환산해 뺌
"""
import sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OBD, DD = ROOT / "research/orderblock/data", ROOT / "research/crypto/data"
COST, K, MAXH = 0.0005, 3, 200
H1 = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "LINK", "LTC", "TRX", "AVAX", "DOT", "BCH"]
D1 = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "LINK", "LTC", "TRX"]


def load(sym, tf):
    if tf == "30m":
        d = pd.read_parquet(OBD / f"{sym}-USD_15m.parquet")
    elif tf in ("1h", "4h"):
        d = pd.read_parquet(OBD / f"{sym}-USD_1h.parquet")
    else:
        d = pd.read_parquet(DD / f"d_{sym}-USD.parquet").rename(columns=str.lower).loc["2018-01-01":]
    d = d[["open", "high", "low", "close"]].dropna()
    rule = {"30m": "30min", "4h": "4h"}.get(tf)
    if rule:
        d = d.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return d


def structure(d):
    o, h, l, c = (d[x].values for x in ("open", "high", "low", "close"))
    n = len(c)
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    body = abs(c - o)
    avgb = pd.Series(body).shift(1).rolling(20).mean().values
    disp = (body >= 1.5 * avgb) & (body >= 0.6 * (h - l + 1e-12))
    ev = np.zeros(n, int)          # +1 BOS↑, +2 CHoCH↑, -1 BOS↓, -2 CHoCH↓
    lvl = np.full(n, np.nan)       # 깬 스윙 가격
    lastL = np.full(n, np.nan)     # 그 시점 마지막 확정 스윙 저점
    lastH = np.full(n, np.nan)
    trend, sh, sl = 0, None, None  # 마지막 확정(아직 안 깨진) 스윙
    rec_h, rec_l = np.nan, np.nan  # 깨졌더라도 최근 확정 스윙 (손절용)
    for i in range(n):
        j = i - K                  # i봉 마감 시점에 확정되는 스윙 후보
        if j >= K:
            if h[j] == h[j - K:i + 1].max():
                sh = h[j]; rec_h = h[j]
            if l[j] == l[j - K:i + 1].min():
                sl = l[j]; rec_l = l[j]
        if sh is not None and c[i] > sh:
            ev[i] = 1 if trend == 1 else 2; lvl[i] = sh; trend = 1; sh = None
        elif sl is not None and c[i] < sl:
            ev[i] = -1 if trend == -1 else -2; lvl[i] = sl; trend = -1; sl = None
        lastL[i], lastH[i] = rec_l, rec_h
    return dict(o=o, h=h, l=l, c=c, atr=atr, disp=disp, ev=ev, lvl=lvl, lastL=lastL, lastH=lastH, t=d.index)


def signals(S, strat):
    """(신호봉 i, 방향, 진입 방식) 목록. 진입 방식: ('mkt',) 또는 ('lim', 가격, 손절, 유효봉수)"""
    ev, disp, h, l = S["ev"], S["disp"], S["h"], S["l"]
    out, pend = [], 0               # pend: CHoCH 뒤 확인 대기 방향
    pdisp = False
    for i in range(len(ev)):
        e = ev[i]
        if e == 0:
            continue
        s = 1 if e > 0 else -1
        if strat == "S1" and abs(e) == 2:
            out.append((i, s, ("mkt",)))
        elif strat == "S3" and abs(e) == 1:
            out.append((i, s, ("mkt",)))
        elif strat in ("S2", "S4"):
            if abs(e) == 2:
                pend, pdisp = s, disp[i]
            elif abs(e) == 1 and pend == s:
                if strat == "S2" or (pdisp and disp[i]):
                    out.append((i, s, ("mkt",)))
                pend = 0
        elif strat == "S5" and abs(e) == 2 and disp[i] and i >= 2:
            # 임펄스 캔들 i 기준 FVG: 롱이면 h[i-1] < l[i+1] 이 필요하지만 i+1은 미래 → i-2..i 로 판정
            if s == 1 and h[i - 2] < l[i]:
                lo = min(l[i - 2:i + 1]); out.append((i, s, ("lim", (h[i - 2] + l[i]) / 2, lo, 20)))
            elif s == -1 and l[i - 2] > h[i]:
                hi = max(h[i - 2:i + 1]); out.append((i, s, ("lim", (l[i - 2] + h[i]) / 2, hi, 20)))
    return out


def simulate(S, strat, exitm):
    o, h, l, c, atr, ev = S["o"], S["h"], S["l"], S["c"], S["atr"], S["ev"]
    n, T, busy = len(c), [], -1
    for i, s, how in signals(S, strat):
        if i + 1 >= n or i < busy:
            continue
        if how[0] == "mkt":
            k = i + 1; e = o[k]
            st = S["lastL"][i] if s == 1 else S["lastH"][i]
        else:
            _, px, st, W = how; k = None
            for j in range(i + 1, min(n, i + 1 + W)):
                if (s == 1 and l[j] <= px) or (s == -1 and h[j] >= px):
                    k = j; break
                if (s == 1 and c[j] < st) or (s == -1 and c[j] > st):
                    break
            if k is None:
                continue
            e = px if (s == 1 and o[k] > px) or (s == -1 and o[k] < px) else o[k]
        if np.isnan(st):
            continue
        risk = (e - st) * s
        if risk < 0.3 * atr[i]:
            continue
        tp = e + s * 2 * risk
        x, j = None, k
        for j in range(k, min(n, k + MAXH)):
            if (s == 1 and l[j] <= st) or (s == -1 and h[j] >= st):
                x = st if j > k or how[0] == "mkt" else st; break
            if exitm == "A" and ((s == 1 and h[j] >= tp) or (s == -1 and l[j] <= tp)):
                x = tp; break
            if exitm == "B" and j > k and ev[j] == -2 * s:
                x = c[j]; break
        if x is None:
            x = c[j]
        r = (x - e) * s / risk - 2 * COST * e / risk
        T.append(dict(t=S["t"][k], side=s, r=r, bars=j - k + 1))
        busy = j + 1
    return pd.DataFrame(T)


def summary(T):
    if len(T) == 0:
        return dict(n=0)
    r = T.r.values
    eq = np.cumsum(r); dd = (eq - np.maximum.accumulate(eq)).min()
    return dict(n=len(r), win=(r > 0).mean(), avgR=r.mean(), totR=r.sum(), maxDD_R=dd)


if __name__ == "__main__":
    rows = []
    plan = [("30m", ["BTC", "ETH", "SOL"]), ("1h", H1), ("4h", H1), ("1d", D1)]
    for tf, syms in plan:
        SS = {}
        for sym in syms:
            try:
                SS[sym] = structure(load(sym, tf))
            except Exception as ex:
                print("skip", sym, tf, ex)
        for strat in ("S1", "S2", "S3", "S4", "S5"):
            for exitm in ("A", "B"):
                allT = []
                for sym, S in SS.items():
                    T = simulate(S, strat, exitm)
                    if len(T):
                        allT.append(T.assign(sym=sym))
                if not allT:
                    continue
                T = pd.concat(allT).sort_values("t")
                cut = T.t.min() + (T.t.max() - T.t.min()) / 2
                A, B = T[T.t < cut], T[T.t >= cut]
                pos = sum(1 for _, g in T.groupby("sym") if g.r.mean() > 0)
                rows.append(dict(tf=tf, strat=strat, exit=exitm, **summary(T),
                                 first_avgR=A.r.mean() if len(A) else np.nan, second_avgR=B.r.mean() if len(B) else np.nan,
                                 coins_pos=f"{pos}/{T.sym.nunique()}", per_coin_day=len(T) / T.sym.nunique() / max(1, (T.t.max() - T.t.min()).days)))
    R = pd.DataFrame(rows)
    out = Path(__file__).parent / "result.csv"
    R.to_csv(out, index=False)
    pd.set_option("display.width", 200)
    print(R.round(3).to_string(index=False))
