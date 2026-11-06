"""미국 테마 과거 검증 + 테마 지수 기록(10년) 만들기 — 매달 주가 추세 상위 3개 테마의 3·6·12개월 뒤 (현재 구성 사용: 사후 선택 편향)"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "scripts"))
import rank_lib as L
from us_narr_def import NARR
J = json.loads((ROOT / "research/us/data/prices.json").read_text())
cal = [r[0] for r in J["^GSPC"]]
ks = pd.Series({r[0]: r[4] for r in J["^GSPC"]}); ks.index = pd.to_datetime(ks.index)
D = {}
for n in NARR:
    cs = [t for t in n["tickers"] if t in J]
    C, _, _ = L.wide({t: J[t] for t in cs}, cal)
    r = C.pct_change(fill_method=None).clip(-0.3, 0.3).mean(axis=1).fillna(0)
    D[n["key"]] = 100 * (1 + r).cumprod()
D = pd.DataFrame(D); ks = ks.reindex(D.index).ffill()
(ROOT / "data/us/theme_history.json").write_text(json.dumps({"dates": [d.strftime("%Y-%m-%d") for d in D.index], "ks": ks.round(2).tolist(),
                                                              "idx": {k: D[k].round(3).tolist() for k in D}}))
lr = np.log(D).sub(np.log(ks), axis=0); tr = ((lr - lr.shift(63)) + (lr - lr.shift(126))) / 2
res = []
for i in range(260, len(D) - 21, 21):
    t = tr.iloc[i].dropna()
    if len(t) < 10: continue
    top = t.sort_values(ascending=False).index[:3]; bot = t.sort_values().index[:3]
    row = {"date": D.index[i].strftime("%Y-%m-%d")}
    for h in (63, 126, 252):
        if i + h < len(D):
            fr = D.iloc[i + h] / D.iloc[i] - 1
            row[f"top{h}"] = fr[top].mean(); row[f"bot{h}"] = fr[bot].mean(); row[f"all{h}"] = fr[t.index].mean(); row[f"ks{h}"] = ks.iloc[i + h] / ks.iloc[i] - 1
    res.append(row)
R = pd.DataFrame(res)
summ = {"from": R.date.iloc[0], "to": R.date.iloc[-1], "n": len(R), "note": "지금의 테마 구성·종목으로 과거를 계산해서, 지금 잘나가는 이야기를 미리 알고 고른 효과가 섞여 있어요. '주가 추세' 신호만 검증 가능."}
for h in (63, 126, 252):
    g = R.dropna(subset=[f"top{h}"]); e = g[f"top{h}"] - g[f"all{h}"]
    summ[str(h)] = {"n": len(g), "top_vs_all": float(e.mean()), "beat": float((e > 0).mean()), "bot_vs_all": float((g[f"bot{h}"] - g[f"all{h}"]).mean()),
                    "top_vs_ks": float((g[f"top{h}"] - g[f"ks{h}"]).mean())}
(ROOT / "data/us/theme_backfill.json").write_text(json.dumps({"summary": summ}, ensure_ascii=False))
print(json.dumps(summ, ensure_ascii=False, indent=1))
