"""② 다우 vs 등락주선 불일치 — 정의를 바꿔가며 + 큰 하락 전에 등락주선이 먼저 꺾였나"""
from rules import *
f60 = spx.shift(-60) / spx - 1
mdd60 = pd.Series([spx.iloc[i:i + 61].min() / spx.iloc[i] - 1 if i + 61 <= len(spx) else np.nan for i in range(len(spx))], index=spx.index)
ok = AD.index >= C.index[260]
print("정의별 (다우 고점 근처 −2% 안 + 등락주선이 자기 고점에서 기간 폭의 x% 넘게 밀림)")
for win in (63, 126, 252):
    for th in (0.1, 0.25, 0.4):
        dh = dji.rolling(win).max(); ah = AD.rolling(win).max(); ar = ah - AD.rolling(win).min()
        m = (dji >= 0.98 * dh) & (AD <= ah - th * ar) & ok
        print(f"  {win:>3}일·{th:.0%}: {int(m.sum()):>4}일 · 60일 뒤 {f60[m].mean():+.2%} (그 외 {f60[~m & ok].mean():+.2%}) · 60일 안 −10% 하락 {(mdd60[m] <= -.1).mean():.0%} (그 외 {(mdd60[~m & ok] <= -.1).mean():.0%})")
# 큰 하락(−15% 이상) 직전 고점에서 등락주선 고점은 며칠 먼저였나
print("\nS&P500 −15% 이상 하락 직전 고점과 등락주선 고점")
pk = spx.cummax(); dd = spx / pk - 1; i = 260; seen = []
while i < len(spx):
    if dd.iloc[i] <= -0.15:
        top = spx.iloc[:i].idxmax() if not seen else spx.loc[seen[-1][1]:spx.index[i]].idxmax()
        top = spx.loc[:spx.index[i]].loc[spx.index[max(0, i - 260)]:].idxmax()
        a_top = AD.loc[top - pd.Timedelta(days=365):top].idxmax()
        seen.append((top, spx.index[i])); print(f"  지수 고점 {top:%Y-%m-%d} · 등락주선 고점 {a_top:%Y-%m-%d} ({(top - a_top).days}일 먼저)")
        while i < len(spx) and dd.iloc[i] < -0.05: i += 1
    i += 1
