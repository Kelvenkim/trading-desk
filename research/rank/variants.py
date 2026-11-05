"""우리 점수 개선 후보를 11년치(2015~2026)로 비교 — 순위 다음 날 시가에 사서 5·20일 뒤 종가까지
현재 시총 상위 300·현재 테마 구성 사용(생존·사후 선택 편향 있음). 결과는 '상위 20 - 300평균'"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "scripts"))
import rank_lib as L, narrative_lib as NL
from narrative_def import NARRATIVES
J = json.loads((ROOT / "research/rank/data/prices300.json").read_text())
cal = sorted(J["ks200"]); C, H, V = L.wide(J["stocks"], cal)
O_ = {}
for c, rows in J["stocks"].items():
    s = pd.Series({r[0]: r[1] for r in rows}); s.index = pd.to_datetime(s.index); O_[c] = s
Op = pd.DataFrame(O_).reindex(C.index)
ks = pd.Series(J["ks200"]); ks.index = pd.to_datetime(ks.index); ks = ks.reindex(C.index).ffill()
I = L.ours_inputs(C, H, V)
M, P = NL.members(list(J["stocks"]))
D = pd.DataFrame({n["key"]: NL.theme_index(C, M[n["key"]]) for n in NARRATIVES})
lr = np.log(D).sub(np.log(ks), axis=0); ttrend = ((lr - lr.shift(63)) + (lr - lr.shift(126))) / 2
F = L.price_factors(C, H, V)
res = {}
pos = {d: i for i, d in enumerate(C.index)}
for d in C.index[400:-21:5]:
    i = pos[d]; cols = C.columns[C.loc[d].notna() & Op.iloc[i + 1].notna()]
    O = L.our_score(**{k: v.loc[d, cols] for k, v in I.items()})
    tr = ttrend.loc[d].dropna()
    if len(tr) < 8: continue
    top3 = set(tr.sort_values(ascending=False).index[:3]); bot3 = set(tr.sort_values().index[:3])
    th = pd.Series({c: (1.0 if P.get(c) in top3 else -1.0 if P.get(c) in bot3 else 0.0) for c in cols})
    thr = pd.Series({c: tr.rank(pct=True).get(P.get(c), 0.5) if P.get(c) in tr.index else 0.5 for c in cols})
    z = lambda s: L.xrank(s)
    V_ = {
        "V0 우리 점수(현재)": O["total"],
        "V1 강한 테마 소속": thr,
        "V2 우리 점수 + 테마 15점": O["total"] + 15 * thr,
        "V3 강한 테마 + 단기 눌림": z(thr) + 0.5 * z(F["rev"].loc[d, cols]),
        "V4 강한 테마 + 낮은 변동성": z(thr) + 0.5 * z(F["lowvol"].loc[d, cols]),
        "V5 낮은 변동성 + 단기 눌림": z(F["lowvol"].loc[d, cols]) + z(F["rev"].loc[d, cols]),
    }
    for h in (5, 20):
        fr = C.iloc[i + h][cols] / Op.iloc[i + 1][cols] - 1      # 다음 날 시가 → h일 뒤 종가
        for k, s in V_.items():
            top = s.sort_values(ascending=False, kind="stable").index[:20]
            res.setdefault((k, h), []).append((d.year, float(fr[top].mean() - fr.mean()), L.spearman(s, fr)))
print("상위 20 − 300 평균 (다음 날 시가 매수, 비용 전)")
for (k, h), v in sorted(res.items(), key=lambda x: (x[0][1], x[0][0])):
    a = np.array([x[1] for x in v]); ic = np.nanmean([x[2] for x in v])
    yrs = pd.DataFrame(v, columns=["y", "e", "ic"]).groupby("y").e.mean()
    print(f"{h:>2}일 {k:<22} 평균 {a.mean()*100:+.2f}% 이긴 비율 {(a>0).mean()*100:.0f}% IC {ic:+.3f} t {a.mean()/a.std()*np.sqrt(len(a)/(h/5)):+.1f} | 플러스 연도 {(yrs>0).sum()}/{len(yrs)}")

out = {}
for (k, h), v in res.items():
    a = np.array([x[1] for x in v]); yrs = pd.DataFrame(v, columns=["y", "e", "ic"]).groupby("y").e.mean()
    out.setdefault(k, {})[str(h)] = {"ex": float(a.mean()), "beat": float((a > 0).mean()), "t": float(a.mean() / a.std() * np.sqrt(len(a) / (h / 5))),
                                     "years_pos": int((yrs > 0).sum()), "years": int(len(yrs)), "by_year": {str(y): float(e) for y, e in yrs.items()}}
(ROOT / "data/rank/variants_backfill.json").write_text(json.dumps({"made": str(pd.Timestamp.today().date()), "method": "순위 다음 날 시가 매수 → 5·20일 뒤 종가, 상위 20 − 300 평균, 비용 전", "robust": "테마 눌림: 눌림 비중 0.3~1.0 · 기간 3~10일 · 상위 10~30 의 27개 설정 모두 플러스, 2015~2020·2021~2026 두 기간 모두 플러스", "variants": out}, ensure_ascii=False))
