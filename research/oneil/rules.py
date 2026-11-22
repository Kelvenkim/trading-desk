"""
형이 준 주식 규칙 6가지 시험 (11/22) — 미국 S&P500+나스닥100 562종목 일봉 2014~2026 (지금 구성 종목 = 생존 편향 있음)
기본 매매: 종가가 52주 신고점 돌파(직전 20일 안 첫 돌파) → 다음 날 시가 매수
청산: 손절 −7%(형 규칙) · 종가가 50일선 아래로 마감하면(추세 꺾임) 다음 날 시가 매도 · 최대 250일
규칙:
 ① 신고점 돌파일 거래량 ≥ 평균 × 1.5  (평균 = 직전 50일 / 직전 250일 두 가지)
 ② 다우 vs 등락주선 불일치: 다우가 6개월 고점 근처(−2% 안)인데 등락주선은 6개월 고점에서 크게 밀림 → 이후 시장 성적
 ③ 상대강도(RS, IBD 방식: 3개월 40% + 6·9·12개월 각 20%) 80 이상 · 업종 RS 상위 절반 · RS 70 아래로 꺾이면 매도
 ⑤ 기관 보유 1~20% → 과거 보유 비율 기록이 없어 시험 불가 (지금 값만 있음)
 ⑥ 바닥(2년 최저가) 대비 2~3배 오른 상태
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
J = json.loads((ROOT / "research/us/data/prices.json").read_text())
U = {s["t"]: s["sector"] for s in json.loads((ROOT / "data/us/universe.json").read_text())["stocks"]}
tick = sorted(t for t in J if t in U)
def wide(k):
    return pd.DataFrame({t: pd.Series({r[0]: r[k] for r in J[t]}) for t in tick}).sort_index()
O, H, L, C, V = (wide(k) for k in (1, 2, 3, 4, 5))
for X in (O, H, L, C, V):
    X.index = pd.to_datetime(X.index)
spx = pd.Series({r[0]: r[4] for r in J["^GSPC"]}); spx.index = pd.to_datetime(spx.index); spx = spx.reindex(C.index).ffill()
dji = pd.read_csv(Path(__file__).parent / "data/dji.csv", index_col=0, parse_dates=True)["Close"].reindex(C.index).ffill()

hi252 = H.rolling(252, min_periods=200).max().shift(1)
brk = (C > hi252) & ~((C > hi252).rolling(20, min_periods=1).max().shift(1).fillna(0).astype(bool))
v50 = V.rolling(50).mean().shift(1); v250 = V.rolling(250).mean().shift(1)
rsraw = 0.4 * C / C.shift(63) + 0.2 * C / C.shift(126) + 0.2 * C / C.shift(189) + 0.2 * C / C.shift(252)
RS = rsraw.rank(axis=1, pct=True) * 99
sec = pd.Series(U)[tick]
secRS = RS.T.groupby(sec).mean().T.rank(axis=1, pct=True)          # 업종 평균 RS의 업종 간 순위 (0~1)
secTop = pd.DataFrame({t: secRS[sec[t]] for t in tick}) >= 0.5
ma50 = C.rolling(50).mean()
base = C / L.rolling(504, min_periods=300).min()                      # 2년 최저가 대비 몇 배

# 등락주선: 종목 중 오른 수 − 내린 수 누적
chg = np.sign(C.diff()); ad = (chg > 0).sum(axis=1) - (chg < 0).sum(axis=1); AD = ad.cumsum()
dj_hi = dji.rolling(126).max(); ad_hi = AD.rolling(126).max(); ad_rg = AD.rolling(126).max() - AD.rolling(126).min()
div = (dji >= 0.98 * dj_hi) & (AD <= ad_hi - 0.25 * ad_rg)            # 다우는 고점 근처, 등락주선은 6개월 폭의 25% 넘게 밀림

idx = {d: i for i, d in enumerate(C.index)}
Cv, Ov, Mv, RSv = C.values, O.values, ma50.values, RS.values

def trades(mask, rs_exit=None):
    out = []
    ii, jj = np.where(mask.values)
    for i, j in zip(ii, jj):
        if i + 1 >= len(C) or np.isnan(Ov[i + 1, j]):
            continue
        e = Ov[i + 1, j]; stop = e * 0.93; x = None; k = i + 1
        while k < min(len(C) - 1, i + 251):
            if L.values[k, j] <= stop:
                x = min(Ov[k, j], stop) if k > i + 1 else stop; why = "손절"; break
            if Cv[k, j] < Mv[k, j] or (rs_exit and RSv[k, j] < rs_exit):
                x = Ov[k + 1, j]; k += 1; why = "추세"; break
            k += 1
        if x is None or np.isnan(x):
            x = Cv[min(k, len(C) - 1), j]; why = "기간"
        out.append((C.index[i], tick[j], x / e - 1 - 0.001, k - i, why))
    return pd.DataFrame(out, columns=["d", "t", "r", "days", "why"])

def show(nm, T):
    if not len(T):
        print(f"{nm:<38} 거래 없음"); return
    h = pd.Timestamp("2020-07-01")
    a, b = T[T.d < h].r, T[T.d >= h].r
    print(f"{nm:<38} {len(T):>5}번 승률 {(T.r > 0).mean():>4.0%} 평균 {T.r.mean():+6.2%} 중앙 {T.r.median():+6.2%} 큰승(+50%↑) {(T.r > .5).mean():>4.1%} | 앞 {a.mean():+6.2%} 뒤 {b.mean():+6.2%} | 보유 {T.days.mean():.0f}일")

if __name__ == "__main__":
    valid = brk & hi252.notna() & RS.notna()
    print(f"기간 {C.index[260]:%Y-%m-%d} ~ {C.index[-1]:%Y-%m-%d} · {len(tick)}종목 · 매수 다음 날 시가, 비용 0.1% 포함\n")
    print("── ① 신고점 돌파 거래량")
    show("신고점 돌파 전체", trades(valid))
    show("  거래량 < 50일 평균 ×1.5", trades(valid & (V < 1.5 * v50)))
    show("  거래량 ≥ 50일 평균 ×1.5", trades(valid & (V >= 1.5 * v50)))
    show("  거래량 ≥ 250일 평균 ×1.5", trades(valid & (V >= 1.5 * v250)))
    print("\n── ③ 상대강도")
    for lo, hi in [(0, 50), (50, 80), (80, 90), (90, 100)]:
        show(f"  RS {lo}~{hi}", trades(valid & (RS >= lo) & (RS < hi)))
    show("  RS 80+ & 업종 RS 상위 절반", trades(valid & (RS >= 80) & secTop))
    show("  RS 80+ & 업종 RS 하위 절반", trades(valid & (RS >= 80) & ~secTop))
    show("  RS 80+ (청산: 50일선 OR RS<70)", trades(valid & (RS >= 80), rs_exit=70))
    print("\n── ⑥ 바닥(2년 최저가) 대비")
    for lo, hi in [(0, 1.5), (1.5, 2), (2, 3), (3, 99)]:
        show(f"  {lo}~{hi}배", trades(valid & (base >= lo) & (base < hi)))
    print("\n── 합치기")
    allr = valid & (V >= 1.5 * v50) & (RS >= 80)
    show("거래량 1.5배 + RS 80+", trades(allr))
    show("거래량 1.5배 + RS 80+ + 업종 상위", trades(allr & secTop))
    show("거래량 1.5배 + RS 80+ + 바닥 2~3배", trades(allr & (base >= 2) & (base < 3)))
    # 지금 AI 데스크 필터('50일선 +8%↑ & RSI 65↑ 제외')와 충돌 확인
    d_ = C.diff(); up = d_.clip(lower=0).rolling(14).mean(); dn = (-d_.clip(upper=0)).rolling(14).mean(); rsi = 100 - 100 / (1 + up / dn)
    ext = (C / ma50 - 1 > 0.08) & (rsi > 65)
    show("거래량+RS80 중 '이미 많이 오름'에 걸리는 것", trades(allr & ext))
    show("거래량+RS80 중 안 걸리는 것", trades(allr & ~ext))
    print(f"  → 거래량+RS80 돌파의 {(allr & ext).values.sum() / max(1, allr.values.sum()):.0%}가 지금 필터에 걸려 제외됨")
    print("\n── ② 다우 vs 등락주선 불일치 (그날 이후 S&P500)")
    f20 = spx.shift(-20) / spx - 1; f60 = spx.shift(-60) / spx - 1
    mdd60 = pd.Series([spx.iloc[i:i + 61].min() / spx.iloc[i] - 1 if i + 61 <= len(spx) else np.nan for i in range(len(spx))], index=spx.index)
    ok = AD.index >= C.index[260]
    for nm, m in [("불일치 날", div & ok), ("그 외 날", ~div & ok)]:
        print(f"  {nm:<10} {int(m.sum()):>4}일 · 20일 뒤 {f20[m].mean():+.2%} · 60일 뒤 {f60[m].mean():+.2%} · 60일 안 최대 하락 {mdd60[m].mean():+.2%} · 60일 안 −10% 이상 하락 확률 {(mdd60[m] <= -0.10).mean():.0%}")
    ev = div & ~div.shift(1, fill_value=False) & ok
    print("  불일치 시작일:", ", ".join(f"{d:%Y-%m-%d}" for d in ev[ev].index[-12:]))
    T = trades(allr)
    dv = T.d.map(lambda d: bool(div.get(d, False)))
    show("  거래량+RS80 돌파 — 불일치 때 산 것", T[dv]); show("  거래량+RS80 돌파 — 그 외", T[~dv])
