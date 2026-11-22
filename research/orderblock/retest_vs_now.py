"""오더블록: '되돌아와 찍을 때 진입(지금 규칙)' vs 'OB 생기면 바로 진입' — 1분·5분·15분·1시간·일봉 비교 (11/22 형 요청)
OB 찾기·필터는 지금 계좌와 같음: 2·3캔들, 유동성 흡수(sweep)만, 손절 = OB 꼬리 끝
진입: A 되돌림 = OB 위쪽 가격 지정가, 48봉 안에 닿을 때만 / B 바로 = OB 완성 다음 봉 시가
청산(둘 다 같은 두 가지로): ① 파동 고점(A) 또는 1R(B)에서 절반 + 본전 손절 + 반대 OB에서 나머지 ② 2R 고정 익절
비용 한쪽 0.05% (짧은 봉일수록 손절 폭이 좁아 비용 부담이 커짐 — 결과에 그대로 반영)"""
import sys
from datetime import datetime, timedelta, timezone
import numpy as np, pandas as pd, yfinance as yf

FEE = 0.0005; SYMS = ["BTC-USD", "ETH-USD", "SOL-USD"]


def load(sym, iv):
    if iv == "1m":
        out = []; end = datetime.now(timezone.utc)
        for k in range(4):
            e = end - timedelta(days=7 * k); s = e - timedelta(days=7)
            try:
                out.append(yf.Ticker(sym).history(start=s, end=e, interval="1m"))
            except Exception:
                pass
        d = pd.concat(out).sort_index(); d = d[~d.index.duplicated()]
    else:
        d = yf.Ticker(sym).history(period={"5m": "60d", "15m": "60d", "1h": "730d", "1d": "max"}[iv], interval=iv)
        if iv == "1d":
            d = d[d.index >= "2018-01-01"]
    d = d.dropna(); d.columns = [c.lower() for c in d.columns]
    return d[["open", "high", "low", "close"]]


def atr(d, n=14):
    pc = d.close.shift(); tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().values


def find(d, L=20):
    o, h, l, c = (d[k].values for k in ("open", "high", "low", "close")); A = atr(d); out = []
    for i in range(L + 3, len(c) - 2):
        for s in (1, -1):
            up = c[i] > o[i] if s > 0 else c[i] < o[i]; dn = c[i - 1] < o[i - 1] if s > 0 else c[i - 1] > o[i - 1]
            if not (up and dn):
                continue
            k = 3 if ((c[i - 2] > o[i - 2]) if s > 0 else (c[i - 2] < o[i - 2])) else 2
            if s > 0:
                st = l[i - k + 1:i + 1].min(); e = h[i - 1]; sw = st < l[i - k + 1 - L:i - k + 1].min()
            else:
                st = h[i - k + 1:i + 1].max(); e = l[i - 1]; sw = st > h[i - k + 1 - L:i - k + 1].max()
            if sw and abs(e - st) >= 0.05 * A[i]:
                out.append((i, s, e, st, c[i] > h[i - 1] if s > 0 else c[i] < l[i - 1]))
    return out


def sim(d, obs, mode, exitm, W=48, HOLD=72):
    o, h, l, c = (d[k].values for k in ("open", "high", "low", "close")); N = len(c); A = atr(d)
    opp = {}
    for i, s, *_r, disp in obs:
        if disp:
            opp.setdefault(i, set()).add(s)
    R = []; busy = -1
    for i, s, e, st, _ in obs:
        if i <= busy:
            continue
        if mode == "retest":
            j = None; wave = h[i] if s > 0 else l[i]
            for k in range(i + 1, min(N, i + 1 + W)):
                if (s > 0 and l[k] <= e) or (s < 0 and h[k] >= e):
                    j = k; break
                wave = max(wave, h[k]) if s > 0 else min(wave, l[k])
                if (s > 0 and c[k] < st) or (s < 0 and c[k] > st):
                    break
            if j is None:
                continue
            fill = min(o[j], e) if s > 0 else max(o[j], e)
        else:
            j = i + 1; fill = o[j]
            if (fill - st) * s <= 0:
                continue
        risk = abs(fill - st)
        if risk < max(0.0005 * fill, 0.25 * A[j]):                 # 손절 폭이 너무 좁으면(갭으로 손절가 근처 체결) 건너뜀 — 아니면 R이 무한대로 커짐
            continue
        tp1 = wave if mode == "retest" else fill + s * risk
        if exitm == "rr2":
            tp1 = fill + s * 2 * risk
        legs = []; rem = 1.0; be = False; stop = st; k = j
        for k in range(j, min(N, j + HOLD)):
            if (s > 0 and l[k] <= stop) or (s < 0 and h[k] >= stop):
                legs.append((rem, (min(o[k], stop) if s > 0 else max(o[k], stop)) if k > j else stop)); rem = 0; break
            if (s > 0 and h[k] >= tp1) or (s < 0 and l[k] <= tp1):
                if exitm == "rr2":
                    legs.append((rem, tp1)); rem = 0; break
                if not be:
                    legs.append((0.5, tp1)); rem = 0.5; be = True; stop = fill; continue
            if be and k > j and (-s) in opp.get(k, ()):
                legs.append((rem, c[k])); rem = 0; break
        if rem > 0:
            k = min(N - 1, j + HOLD - 1); legs.append((rem, c[k]))
        net = sum(w * s * (px / fill - 1) for w, px in legs) - 2 * FEE
        R.append((d.index[j], net / (risk / fill), risk / fill, (net + 2 * FEE) / (risk / fill))); busy = k
    return pd.DataFrame(R, columns=["t", "r", "risk", "gross"])


def acct(T):
    r = T.sort_values("t").r.cumsum(); dd = (r - r.cummax().clip(lower=0)).min()
    return r.iloc[-1], dd


if __name__ == "__main__":
    ivs = sys.argv[1:] or ["1m", "5m", "15m", "1h", "1d"]
    for iv in ivs:
        D = {}
        for s in SYMS:
            try:
                D[s] = load(s, iv)
            except Exception as ex:
                print(iv, s, "데이터 실패", ex)
        days = np.mean([(d.index[-1] - d.index[0]).days or 1 for d in D.values()])
        O = {s: find(d) for s, d in D.items()}
        print(f"\n===== {iv} · 기간 약 {days:.0f}일 · 코인 3개 · OB {sum(len(x) for x in O.values())}개 =====")
        for mode, mn in (("retest", "A 되돌림 진입(지금)"), ("now", "B 바로 진입")):
            for ex, en in (("half", "절반 익절+본전" if mode == "now" else "파동 고점 절반+본전"), ("rr2", "2R 고정")):
                T = pd.concat([sim(D[s], O[s], mode, ex) for s in D])
                if not len(T):
                    print(f"  {mn:<16} {en:<14} 거래 없음"); continue
                tot, dd = acct(T); mid = T.t.min() + (T.t.max() - T.t.min()) / 2
                print(f"  {mn:<16} {en:<14} {len(T):>5}번(하루 {len(T) / days / 3:.1f}번/코인) 승률 {(T.r > 0).mean():.0%} · 평균 {T.r.mean():+.2f}R · 합계 {tot:+.0f}R · 최대 낙폭 {dd:.0f}R · "
                      f"앞/뒤 {T[T.t < mid].r.mean():+.2f}/{T[T.t >= mid].r.mean():+.2f} · 비용 빼기 전 {T.gross.mean():+.2f}R · 손절 폭 중앙 {T.risk.median() * 100:.2f}% (비용 {0.1 / (T.risk.median() * 100):.2f}R)")
