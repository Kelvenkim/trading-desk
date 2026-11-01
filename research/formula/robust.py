"""
최종 후보(자산별 추세필터 + 목표변동성) 점검
 1) 엉터리 신호 점검: 무작위 신호는 우위가 없어야 하고, 미래를 미리 보면 비정상적으로 좋아야 함 (계산 방향 확인)
 2) 설정을 바꿔도 결과가 유지되는지 (이동평균 기간, 목표 변동성, 레버리지 한도)
 3) 기간을 나눠도 유지되는지 (2006~2015 / 2016~2026)
"""
import numpy as np
import pandas as pd

import lab as L

OOS = slice("2006-01-01", "2026-12-31")
U3, U4 = ["KS200", "SPX", "NDX"], ["KS200", "KQ", "SPX", "NDX"]


def met(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    return f"연 {(eq.iloc[-1] ** (252 / len(r)) - 1) * 100:5.1f}% · MDD {(eq / eq.cummax() - 1).min() * 100:6.1f}% · 샤프 {r.mean() / r.std() * np.sqrt(252):.2f}"


def gtaa(univ, n, target, cap=2.0):
    on = pd.DataFrame({a: (L.PX[a] > L.sma(L.PX[a], n)) & L.PX[a].notna() for a in univ}).astype(float)
    W = L.monthly(on / len(univ))
    return L.vol_scale(W, target, cap) if target else W


print("① 계산 방향 점검 (3지수, 150일선)")
rng = np.random.default_rng(0)
rand = pd.DataFrame({a: (rng.random(L.N) > 0.5).astype(float) / 3 for a in U3}, index=L.DATES)
rand = L.monthly(rand)
print("  무작위 켜고 끄기     ", met(L.run_weights(rand)[OOS]))
real = gtaa(U3, 150, 0)
print("  실제 규칙(지연 있음)  ", met(L.run_weights(real)[OOS]))
cheat = real.shift(-21).fillna(0)   # 한 달 뒤 신호를 미리 씀 (일부러 틀리게)
print("  미래 한 달 미리 보기  ", met(L.run_weights(cheat)[OOS]), " ← 이게 압도적이면 계산 방향이 맞음")

print("\n② 설정 바꿔보기 (2006~2026, 3지수)")
for n in [100, 150, 200, 250]:
    print(f"  {n}일선 · 변동성 맞춤 없음      ", met(L.run_weights(gtaa(U3, n, 0))[OOS]))
for n in [150, 200]:
    for t in [0.12, 0.15, 0.20, 0.25, 0.30]:
        for cap in [1.0, 2.0]:
            print(f"  {n}일선 · 목표 {int(t*100)}% · 최대 {cap:.0f}배      ", met(L.run_weights(gtaa(U3, n, t, cap))[OOS]))
print("  (참고) 4지수 150일선 목표 20%    ", met(L.run_weights(gtaa(U4, 150, 0.20))[OOS]))

print("\n③ 기간 나눠보기")
cands = {"3지수 150일선 목표20% 최대2배": gtaa(U3, 150, 0.20), "3지수 150일선 (맞춤 없음)": gtaa(U3, 150, 0),
         "보유 NDX": pd.DataFrame({"NDX": pd.Series(1.0, index=L.DATES)}), "보유 3지수 균등": pd.DataFrame({a: pd.Series(1 / 3, index=L.DATES) for a in U3})}
for name, W in cands.items():
    r = L.run_weights(W)
    print(f"  {name:28s} 2006~2015: {met(r['2006':'2015'])} | 2016~2026: {met(r['2016':'2026'])}")

print("\n④ 평균 노출과 매매 빈도 (3지수 150일선 목표 20%)")
W = gtaa(U3, 150, 0.20)[OOS]
tot = W.sum(axis=1)
chg = (W.diff().abs().sum(axis=1) > 0.05).groupby(W.index.year).sum()
print(f"  평균 총 노출 {tot.mean():.2f}배 · 1배 넘는 날 {(tot > 1.001).mean() * 100:.0f}% · 현금 100%인 날 {(tot < 0.001).mean() * 100:.0f}% · 연평균 비중 변경 {chg.mean():.1f}회")
print("  자산별 평균 비중:", {a: round(W[a].mean(), 2) for a in U3})
