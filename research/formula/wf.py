"""
워크포워드 검증: 매년 1월, 그 전 해 말까지의 데이터만으로 공식·설정을 골라 그 해에 적용.
선택 규칙(미리 정해둠, 결과 보고 바꾸지 않음)
  R1: 학습 MDD -30% 이내 중 학습 CAGR 1위
  R2: 학습 샤프 1위
  R3: 학습 MDD -40% 이내 중 학습 CAGR 1위
학습 기간: 2004-01-01 ~ 전년 말 (늘어나는 창)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

O = Path(__file__).parent / "results"
R = pd.read_pickle(O / "cand_returns.pkl")
B = pd.read_pickle(O / "bench_returns.pkl")
FAM = json.load(open(O / "cand_family.json"))
START, Y0, Y1 = "2004-01-01", 2006, 2026


def m(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    return {"cagr": eq.iloc[-1] ** (1 / yrs) - 1, "mdd": (eq / eq.cummax() - 1).min(),
            "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0}


def train_table(cols, end):
    tr = R.loc[START:end, cols]
    eq = (1 + tr).cumprod()
    yrs = len(tr) / 252
    return pd.DataFrame({"cagr": eq.iloc[-1] ** (1 / yrs) - 1, "mdd": (eq / eq.cummax() - 1).min(),
                         "sharpe": tr.mean() / tr.std() * np.sqrt(252)})


def pick(tt, rule):
    if rule == "R1":
        ok = tt[tt.mdd >= -0.30]
        return (ok if len(ok) else tt).cagr.idxmax()
    if rule == "R2":
        return tt.sharpe.idxmax()
    ok = tt[tt.mdd >= -0.40]
    return (ok if len(ok) else tt).cagr.idxmax()


def walk(cols, rule):
    parts, chosen = [], {}
    for y in range(Y0, Y1 + 1):
        tt = train_table(cols, f"{y - 1}-12-31")
        c = pick(tt, rule)
        chosen[y] = c
        parts.append(R.loc[f"{y}-01-01":f"{y}-12-31", c])
    return pd.concat(parts), chosen


def yearly(r):
    return (1 + r).groupby(r.index.year).prod() - 1


if __name__ == "__main__":
    oos = slice(f"{Y0}-01-01", f"{Y1}-12-31")
    all_cols = list(R.columns)
    fams = sorted(set(FAM.values()))
    rows, curves, picks = [], {}, {}
    for rule in ["R1", "R2", "R3"]:
        for scope in ["전체"] + fams:
            cols = all_cols if scope == "전체" else [c for c in all_cols if FAM[c] == scope]
            r, ch = walk(cols, rule)
            k = f"워크포워드 {rule} · {scope}"
            curves[k], picks[k] = r, ch
            rows.append({"name": k, **m(r)})
    fixed = {
        "고정 A: 코스피200 200일선 위 2배 / 아래 현금": "A 추세 KS200 200일선 ON 2.0배 OFF 현금",
        "고정 A: 나스닥100 200일선 위 2배 / 아래 현금": "A 추세 NDX 200일선 ON 2.0배 OFF 현금",
        "고정 D: 4지수 12개월 1등 1배 (200일선 필터)": "D 갈아타기 [KS200+KQ+SPX+NDX] 12개월 상위1 1.0배 필터:sma200",
        "고정 D: 4지수 12개월 1등 2배 (200일선 필터)": "D 갈아타기 [KS200+KQ+SPX+NDX] 12개월 상위1 2.0배 필터:sma200",
        "고정 E: 4지수 혼합모멘텀 1등 + 200일선 + 목표변동성 25%": "E 조합 [KS200+KQ+SPX+NDX] mix개월 1등 + 200일선 + 목표변동성 25%",
        "고정 F: Faber 자산별 200일선 [4지수] (2007년 발표 규칙)": "F 자산별 추세필터 [KS200+KQ+SPX+NDX] 200일선",
        "고정 F: Faber [4지수] + 목표변동성 15%": "F 자산별 추세필터 [KS200+KQ+SPX+NDX] 200일선 목표변동성 15%",
        "고정 G: 변동성균형 [4지수]": "G 변동성균형 [KS200+KQ+SPX+NDX]",
        "고정 G: 변동성균형 [4지수] 목표변동성 15%": "G 변동성균형 [KS200+KQ+SPX+NDX] 목표변동성 15%",
        "고정 G: 변동성균형 [4지수] +200일선 목표변동성 15%": "G 변동성균형 [KS200+KQ+SPX+NDX] +200일선 목표변동성 15%",
    }
    for k, c in fixed.items():
        curves[k] = R.loc[oos, c]
        rows.append({"name": k, **m(curves[k])})
    for c in B.columns:
        curves[c] = B.loc[oos, c]
        rows.append({"name": c, **m(curves[c])})
    T = pd.DataFrame(rows).set_index("name")
    pd.set_option("display.width", 200)
    print(f"=== 검증 기간 {Y0}-01 ~ 2026-10 (약 {len(curves['보유 KS200'])/252:.1f}년) ===")
    print((T.sort_values("cagr", ascending=False).assign(cagr=lambda d: (d.cagr * 100).round(1), mdd=lambda d: (d.mdd * 100).round(1), sharpe=lambda d: d.sharpe.round(2))).to_string())
    Yt = pd.DataFrame({k: yearly(v) for k, v in curves.items()})
    Yt.to_csv(O / "wf_yearly.csv")
    T.to_csv(O / "wf_summary.csv")
    json.dump({k: {str(y): c for y, c in v.items()} for k, v in picks.items()}, open(O / "wf_picks.json", "w"), ensure_ascii=False, indent=1)
    pd.to_pickle(curves, O / "wf_curves.pkl")
