"""역사적 대박주 연구 (11/22 형 요청) — 우리 데이터(2015~2026, 518종목)에서 1년 안에 2배 이상 오른 '대박 구간'의
출발점(크게 오르기 시작한 첫 신고점 돌파 날) 상태를 전체 돌파와 비교. 생존 편향 있음(지금 남은 종목만)."""
from rules import *
fwd = C.shift(-252).rolling(1).max()                                   # 1년 뒤 종가
peak1y = C[::-1].rolling(252, min_periods=60).max()[::-1].shift(-1)    # 다음 1년 최고 종가
gain = peak1y / O.shift(-1) - 1                                        # 다음 날 시가에 사서 1년 안 최고점까지
valid = brk & hi252.notna() & RS.notna() & gain.notna()
big = valid & (gain >= 1.0)                                            # 1년 안 2배 이상
rest = valid & (gain < 1.0)
d_ = C.diff(); up = d_.clip(lower=0).rolling(14).mean(); dn = (-d_.clip(upper=0)).rolling(14).mean(); rsi = 100 - 100 / (1 + up / dn)
feat = {"상대강도 RS": RS, "돌파일 거래량(50일 평균 대비, 배)": V / v50, "바닥(2년 최저) 대비 배수": base, "50일선 위 %": (C / ma50 - 1) * 100,
        "RSI(14)": rsi, "업종 RS 상위 절반 비율": secTop.astype(float), "직전 3개월 수익률 %": (C / C.shift(63) - 1) * 100}
print(f"신고점 돌파 {int(valid.values.sum())}번 중 1년 안 2배 이상 간 것 {int(big.values.sum())}번 ({big.values.sum() / valid.values.sum():.1%}) · 종목 {int(big.any().sum())}개\n")
print(f"{'특징':<30}{'대박 출발점 (중앙값)':>16}{'나머지 돌파 (중앙값)':>16}")
for k, X in feat.items():
    a, b = X[big].stack().median(), X[rest].stack().median()
    print(f"{k:<30}{a:>16.2f}{b:>16.2f}")
print("\n구간별 '1년 안 2배' 확률")
for nm, X, bins in [("RS", RS, [0, 50, 80, 90, 95, 100]), ("거래량 배수", V / v50, [0, 1, 1.5, 2, 3, 99]), ("바닥 대비", base, [0, 1.5, 2, 3, 99])]:
    row = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = valid & (X >= lo) & (X < hi); n = m.values.sum()
        row.append(f"{lo}~{hi}: {(big & m).values.sum() / max(1, n):.1%} ({n}번)")
    print(f"  {nm}: " + " · ".join(row))
first = big & ~big.shift(1, fill_value=False).rolling(120, min_periods=1).max().astype(bool)
top = sorted(((C.index[i], tick[j], gain.values[i, j]) for i, j in zip(*np.where(first.values))), key=lambda x: -x[2])[:15]
print("\n가장 크게 간 출발점 15개 (다음 날 시가 → 1년 안 최고 종가)")
for d, t, g in top:
    print(f"  {d:%Y-%m-%d} {t:<6} +{g:.0%} · RS {RS.at[d, t]:.0f} · 거래량 {V.at[d, t] / v50.at[d, t]:.1f}배 · 바닥 대비 {base.at[d, t]:.1f}배 · 업종 {sec[t]}")
