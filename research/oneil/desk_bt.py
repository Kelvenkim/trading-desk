"""
AI 데스크 계좌 백테스트 (11/22 형 요청) — 2016~2026 S&P500+나스닥100 518종목 일봉 (지금 구성 종목 = 생존 편향)
가상 $10,000 · 최대 8종목 · 1종목 20% · 현금 20% 유지 · 1회 손실 계좌 2% · 하루 신규 2개(S&P 200일선 아래면 1개·크기 절반)
비용 한쪽 0.05% + 체결 차이 0.05%
A 지금 AI 데스크(근사): Analyst 점수(추세·RSI·MACD·거래량·S&P 대비 강도) 0.6↑, 필터(거래대금·$5·과열·이미 많이 오름),
   종가 −¼N 지정가, 손절 2N(5~7%), +1R 본전 손절, 목표 2.5R, 5일째 −0.5R 이하 조기 정리
B 형 규칙(주도주): 52주 신고점 첫 돌파 + 거래량 ≥ 50일 평균×1.5 + RS 80↑ (바닥 2~3배 우선) → 다음 날 시가,
   손절 −7%, RS 70↓ + 50일선 아래 마감이면 매도
C A + 형 규칙 필터(RS 80↑, 신고점이면 거래량 1.5배, 그런 돌파는 '이미 많이 오름' 예외, RS 70↓+50일선 이탈 매도)
※ A는 애널리스트 목표가·사이트 신호(추천 바구니)를 빼고 가격만으로 근사했어요.
"""
import numpy as np, pandas as pd
from rules import O, H, L, C, V, spx, RS, ma50, base, v50, hi252, tick

N = len(C); cv, ov, hv, lv, vv = C.values, O.values, H.values, L.values, V.values
rs, m50, bs, v50v = RS.values, ma50.values, base.values, v50.values
pc = np.vstack([cv[:1], cv[:-1]])
tr = np.maximum(hv - lv, np.maximum(abs(hv - pc), abs(lv - pc)))
ATR = pd.DataFrame(tr).rolling(20).mean().values
ma20 = C.rolling(20).mean().values; ma200 = C.rolling(200).mean().values
d = C.diff(); up = d.clip(lower=0).rolling(14).mean(); dn = (-d.clip(upper=0)).rolling(14).mean(); RSI = (100 - 100 / (1 + up / dn)).values
macd = (C.ewm(span=12).mean() - C.ewm(span=26).mean()); MACDH = (macd - macd.ewm(span=9).mean()).values
vr = (V.rolling(5).mean() / V.rolling(20).mean()).values
r20 = (C / C.shift(20) - 1).values; s20 = (spx / spx.shift(20) - 1).values
dv = (C * V).rolling(20).mean().values
rng = ((H - L) / C.shift(1)).values
brk = ((C > hi252) & ~((C > hi252).rolling(20, min_periods=1).max().shift(1).fillna(0).astype(bool))).values
spx200 = spx.rolling(200).mean().values; spv = spx.values

def score(i):
    sc = 0.1 * (cv[i] > ma20[i]) + 0.1 * (cv[i] > m50[i]) + 0.1 * (m50[i] > ma200[i])
    r = RSI[i]; sc = sc + np.where((r >= 45) & (r <= 70), 0.2, np.where(((r > 70) & (r <= 80)) | ((r >= 35) & (r < 45)), 0.1, 0.03))
    sc = sc + 0.1 * (MACDH[i] > 0) + np.where((vr[i] > 1.2) & (cv[i] > pc[i]), 0.1, np.where(vr[i] > 1, 0.05, 0))
    sc = sc + np.clip((r20[i] - s20[i]) / 0.10 * 0.15, 0, 0.15)
    return sc

def run(kind, start=260):
    cash, pos, eq_hist, trades = 10000.0, {}, [], []
    pend = []                                                     # (종목, 지정가 or None(시가), 손절%, 계획)
    for i in range(start, N - 1):
        # 1) 오늘 시가·장중: 대기 주문 체결
        up_mkt = spv[i - 1] > spx200[i - 1]
        new = []
        for j, lim, sp, how in pend:
            if j in pos or len(pos) >= 8 or np.isnan(ov[i, j]):
                continue
            px = ov[i, j] if lim is None else (min(ov[i, j], lim) if lv[i, j] <= lim else None)
            if px is None:
                continue
            eq = cash + sum(p["sh"] * cv[i - 1, k] for k, p in pos.items())
            usd = min(eq * 0.02 / sp * (1 if up_mkt else 0.5), eq * 0.20, cash - eq * 0.20)
            if usd < 200:
                continue
            px *= 1.0005; sh = usd / px; cash -= usd * 1.0005
            pos[j] = dict(sh=sh, e=px, stop=px * (1 - sp), sp=sp, d0=i, be=False, hi=px, how=how)
            new.append(j)
        pend = []
        # 2) 보유: 손절·목표·규칙 매도 (장중 손절 먼저, 나머지는 종가 판단 → 다음 날 시가)
        for j in list(pos):
            p = pos[j]; o_, h_, l_, c_ = ov[i, j], hv[i, j], lv[i, j], cv[i, j]
            if np.isnan(c_):
                continue
            x = why = None
            if l_ <= p["stop"]:
                x = min(o_, p["stop"]) if i > p["d0"] else p["stop"]; why = "손절" if not p["be"] else "본전"
            elif kind in ("A", "C") and h_ >= p["e"] * (1 + 2.5 * p["sp"]):
                x = max(o_, p["e"] * (1 + 2.5 * p["sp"])); why = "목표"
            if x is None and p.get("sell_next"):
                x = o_; why = p["sell_next"]
            if x is not None:
                x *= 0.9995; cash += p["sh"] * x * 0.9995; trades.append((p["d0"], i, x / p["e"] - 1, why, p["how"])); del pos[j]; continue
            if kind in ("A", "C"):
                if not p["be"] and c_ >= p["e"] * (1 + p["sp"]):
                    p["be"] = True; p["stop"] = max(p["stop"], p["e"])
                if i - p["d0"] == 5 and c_ <= p["e"] * (1 - 0.5 * p["sp"]):
                    p["sell_next"] = "5일째 −0.5R"
            if kind in ("B", "B2", "C") and rs[i, j] < 70 and c_ < m50[i, j]:
                p["sell_next"] = "RS·추세 꺾임"
        eq = cash + sum(p["sh"] * cv[i, k] for k, p in pos.items() if not np.isnan(cv[i, k]))
        eq_hist.append((C.index[i], eq))
        # 3) 장 마감: 내일 주문
        if len(pos) >= 8:
            continue
        ok = (dv[i] >= 2e7) & (cv[i] >= 5) & ~np.isnan(rs[i])
        held = np.zeros(len(tick), bool); held[list(pos)] = True
        nmax = 2 if spv[i] > spx200[i] else 1
        if kind in ("B", "B2"):
            if kind == "B2" and spv[i] < spx200[i]:
                continue                                          # B2: S&P500이 200일선 아래면 신규 매수 안 함 (오닐 M: 시장 방향)
            m = ok & brk[i] & (vv[i] >= 1.5 * v50v[i]) & (rs[i] >= 80) & ~held
            js = np.where(m)[0]
            js = sorted(js, key=lambda j: (-int(2 <= bs[i, j] < 3), -rs[i, j]))[:nmax]
            pend = [(j, None, 0.07, "주도주") for j in js]
        else:
            sc = score(i)
            ext = (cv[i] / m50[i] - 1 > 0.08) & (RSI[i] > 65)
            filt = ok & (rng[i] <= 0.10) & ~held
            if kind == "C":
                vbrk = brk[i] & (vv[i] >= 1.5 * v50v[i]) & (rs[i] >= 80)
                filt &= (rs[i] >= 80) & ~(brk[i] & (vv[i] < 1.5 * v50v[i])) & ~(ext & ~vbrk)
                sc = sc + 0.05 * (brk[i] & (vv[i] >= 1.5 * v50v[i])) + 0.05 * ((bs[i] >= 2) & (bs[i] < 3))
            else:
                filt &= ~ext
            m = filt & (sc >= 0.6)
            js = np.where(m)[0]; js = js[np.argsort(-sc[js])][:nmax]
            pend = [(j, cv[i, j] - 0.25 * ATR[i, j], float(np.clip(2 * ATR[i, j] / cv[i, j], 0.05, 0.07)), "점수") for j in js]
    E = pd.Series(dict(eq_hist)); T = pd.DataFrame(trades, columns=["i0", "i1", "r", "why", "how"])
    return E, T

def summary(nm, E, T):
    yrs = (E.index[-1] - E.index[0]).days / 365.25; cagr = (E.iloc[-1] / E.iloc[0]) ** (1 / yrs) - 1
    mdd = (E / E.cummax() - 1).min(); h = E.index[0] + (E.index[-1] - E.index[0]) / 2
    a = E[E.index < h]; b = E[E.index >= h]
    ya = (a.iloc[-1] / a.iloc[0]) ** (365.25 / (a.index[-1] - a.index[0]).days) - 1; yb = (b.iloc[-1] / b.iloc[0]) ** (365.25 / (b.index[-1] - b.index[0]).days) - 1
    yr = E.resample("YE").last().pct_change().dropna()
    print(f"{nm:<26} $10,000 → ${E.iloc[-1]:>9,.0f} · 연 {cagr:+.1%} · 최대 낙폭 {mdd:.1%} · 거래 {len(T)}번 승률 {(T.r > 0).mean():.0%} 평균 {T.r.mean():+.2%} · 보유 {(T.i1 - T.i0).mean():.0f}일 · 앞 5년 연 {ya:+.1%} 뒤 5년 연 {yb:+.1%} · 마이너스 해 {int((yr < 0).sum())}/{len(yr)}")
    return yr

if __name__ == "__main__":
    s = spx.iloc[260:]; yrs = (s.index[-1] - s.index[0]).days / 365.25
    print(f"기간 {C.index[260]:%Y-%m-%d} ~ {C.index[-1]:%Y-%m-%d}\n")
    print(f"{'S&P500 그냥 보유':<26} 연 {(s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1:+.1%} · 최대 낙폭 {(s / s.cummax() - 1).min():.1%}")
    Y = {}
    for k, nm in [("A", "A 지금 AI 데스크(근사)"), ("C", "C A + 형 규칙 필터"), ("B", "B 형 규칙만 (주도주)"), ("B2", "B2 주도주 + 시장 200일선 위만")]:
        E, T = run(k); Y[nm] = summary(nm, E, T)
        if k in ("B", "B2"):
            print("   B 매도 이유:", T.why.value_counts().to_dict())
    print("\n연도별 수익률")
    sy = spx.resample("YE").last().pct_change().dropna()
    df = pd.DataFrame(Y); df["S&P500"] = sy.reindex(df.index)
    print((df * 100).round(1).to_string())
