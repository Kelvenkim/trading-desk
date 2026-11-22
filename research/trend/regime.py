"""연도·시기마다 규칙을 바꾸면 나을까? (11/22 형: 좋은 해·나쁜 해가 있으니 유연하게)
① 분기별로 '익절 없음 / 2R 익절 / 절반 익절+본전' 성적 비교 → 해마다 1등이 바뀌나
② 따라가기: 직전 분기에 1등이었던 방식을 다음 분기에 씀 (실제로 할 수 있는 유연한 방식) vs 하나로 고정
③ 국면으로 나누기: 진입 순간 추세 세기(EMA50·200 간격 ÷ ATR)가 강한 때 / 약한 때 각각 1등"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.argv = ["x"]
from tp import trend, B, F, CO   # tp.py 의 시뮬레이터·데이터 재사용 (실행 시 tp.py 표도 같이 출력됨)

MODES = {"익절 없음(지금)": {}, "2R 익절": dict(tp=2), "1R 절반+본전": dict(half=True)}
T = {}
for nm, kw in MODES.items():
    X = []
    for s, d in B.items():
        t = trend(d, F[s], **kw)
        e50 = d.close.ewm(span=50, adjust=False).mean(); e200 = d.close.ewm(span=200, adjust=False).mean()
        gap = ((e50 - e200).abs() / pd.Series(F[s]["A"], index=d.index)).reindex(t.t).values if len(t) else []
        X.append(t.assign(sym=s, gap=gap))
    T[nm] = pd.concat(X).sort_values("t")
print("\n① 분기별 거래당 평균 R (1등 굵게 표시 대신 ★)")
q = {nm: x.groupby(x.t.dt.to_period("Q")).r.mean() for nm, x in T.items()}
Q = pd.DataFrame(q).dropna()
for p, row in Q.iterrows():
    best = row.idxmax()
    print(f"  {p}: " + " · ".join(f"{'★' if k == best else ' '}{k} {v:+.2f}" for k, v in row.items()))
print("  분기마다 1등:", Q.idxmax(axis=1).value_counts().to_dict())
print("\n② 직전 분기 1등을 다음 분기에 쓰기 vs 고정")
sumR = {nm: x.groupby(x.t.dt.to_period("Q")).r.sum() for nm, x in T.items()}
S = pd.DataFrame(sumR).dropna()
follow = [S.iloc[i][Q.iloc[i - 1].idxmax()] for i in range(1, len(S))]
print(f"  따라가기 합계 {sum(follow):+.0f}R")
for nm in MODES:
    print(f"  {nm} 고정 합계 {S[nm].iloc[1:].sum():+.0f}R")
print("\n③ 진입 순간 추세 세기로 나누기 (EMA50·200 간격 ÷ ATR, 중앙값 기준)")
med = T["익절 없음(지금)"].gap.median()
for lab, cond in [("추세 약할 때", lambda x: x.gap < med), ("추세 강할 때", lambda x: x.gap >= med)]:
    print(f"  {lab}: " + " · ".join(f"{nm} {x[cond(x)].r.mean():+.2f}R({cond(x).sum()})" for nm, x in T.items()))
