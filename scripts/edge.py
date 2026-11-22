"""
'확실한 자리' 데이터 모으기 (11/22 형 목표)
  ① 비중: 확실한 자리엔 더 큰 금액 → 어떤 특징일 때 결과(R)가 좋은지 알아야 함
  ② 우리만의 그래프: 그것만 보면 판단되는 그래프 → 결과를 가르는 특징을 찾아서 나중에 하나의 '확신 점수'로 그림
지금 하는 일 (매일 coach.yml에서 coach.py 다음에):
  - 2년 시험 거래마다 진입 순간 특징(RSI·200EMA 거리·거래량 배수·변동성·손절 폭·시간대·요일·방향·큰 추세 + 공식별 특징)을 붙임
  - 특징별로 5칸(또는 종류별)으로 나눠 칸마다 평균 R → '어떤 자리가 확실한가' 지도
  - 확신 점수 시험: 앞 1년으로 점수표를 만들고 뒤 1년에 적용 → 점수 상위 1/3이 실제로 더 좋은지, 크기를 0.5·1·1.5배로 나누면 계좌가 나아지는지
  - 실제 계좌 거래(일지의 feat)도 모아 개수를 셈 — 30번↑ 쌓이면 시험 결과와 비교
  결과: data/us/edge.json. 비중 조절은 '뒤 1년에서도 통하고 + 실제 거래 30번↑으로 확인'될 때 반영 (형: 데이터 쌓이면 조절)
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coach as CO
import formula_rules as FR

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us/edge.json"
NUM = {"rsi": "RSI(14)", "trend": "200EMA에서 떨어진 정도(%, 진입 방향 기준)", "vr": "거래량 배수(20봉 평균 대비)", "atrp": "변동성(ATR %)", "risk": "손절 폭(%)",
       "mvol": "조작 봉 거래량 배수", "boxw": "박스 폭(ATR 배수)"}
CAT = {"side": "방향", "htf": "큰 추세(50일선) 쪽", "session": "시간대", "wkend": "주말", "fvg": "FVG 있음", "gap": "갭 있음", "vhi": "OB 봉 거래량 1.5배↑", "k": "OB 캔들 수"}
SESS = lambda h: "아시아(09~16시)" if h < 7 else "런던(16~21시)" if h < 12 else "뉴욕(21~05시)" if h < 20 else "새벽(05~09시)"   # UTC → 한국 시간 표기


def enrich(T, d, X):
    if not len(T):
        return T
    idx = d.index.get_indexer(pd.DatetimeIndex(T.t))
    T = T.copy()
    for k in ("rsi", "trend", "vr", "atrp"):
        v = np.array([X[k][i] if i >= 0 else np.nan for i in idx], dtype=float)
        T[k] = v * (100 if k == "atrp" else 1)
    T["trend"] = T["trend"] * T["side"] * 100
    T["risk"] = T["risk"] * 100
    T["session"] = [SESS(t.hour) for t in pd.DatetimeIndex(T.t)]
    T["wkend"] = [t.weekday() >= 5 for t in pd.DatetimeIndex(T.t)]
    T["side"] = T["side"].map({1: "롱", -1: "숏"})
    return T


def buckets(T, col):
    if col in NUM:
        x = T[col].astype(float)
        if x.notna().sum() < 50:
            return None
        try:
            q = pd.qcut(x, 5, duplicates="drop")
        except ValueError:
            return None
        lab = q.cat.categories
        g = T.groupby(q, observed=True).r
        return [dict(b=f"{iv.left:.2f}~{iv.right:.2f}", n=int(g.size()[iv]), R=round(float(g.mean()[iv]), 3), win=round(float((T.r[q == iv] > 0).mean()), 3)) for iv in lab if iv in g.size().index]
    g = T.groupby(T[col].astype(str)).r
    return [dict(b=str(k), n=int(n), R=round(float(g.mean()[k]), 3), win=round(float((T.r[T[col].astype(str) == k] > 0).mean()), 3)) for k, n in g.size().items()]


def score_table(T, cols):
    """각 특징 칸의 평균 R − 전체 평균 (표본 적으면 0 쪽으로 줄임)"""
    base = T.r.mean(); tab = {}
    for c in cols:
        if c in NUM:
            x = T[c].astype(float)
            if x.notna().sum() < 50:
                continue
            edges = np.unique(np.nanquantile(x, [0, .2, .4, .6, .8, 1]))
            if len(edges) < 3:
                continue
            b = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(edges) - 2)
            tab[c] = ("num", edges, {i: (T.r[b == i].mean() - base) * ((b == i).sum() / ((b == i).sum() + 100)) for i in range(len(edges) - 1) if (b == i).sum()})
        else:
            s = T[c].astype(str)
            tab[c] = ("cat", None, {k: (T.r[s == k].mean() - base) * ((s == k).sum() / ((s == k).sum() + 100)) for k in s.unique()})
    return tab


def apply_score(T, tab):
    sc = np.zeros(len(T))
    for c, (kind, edges, m) in tab.items():
        if kind == "num":
            x = T[c].astype(float).values
            b = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(edges) - 2)
            sc += np.array([m.get(int(i), 0.0) if np.isfinite(v) else 0.0 for i, v in zip(b, x)])
        else:
            sc += T[c].astype(str).map(m).fillna(0.0).values
    return sc


def sizing_test(T, cols):
    """앞 1년으로 점수표 → 뒤 1년에 적용. 점수 1/3씩 크기 0.5·1·1.5배 vs 똑같이"""
    T = T.sort_values("t").reset_index(drop=True)
    mid = T.t.min() + (T.t.max() - T.t.min()) / 2
    A, B = T[T.t < mid], T[T.t >= mid].copy()
    if len(A) < 150 or len(B) < 150:
        return None
    B["score"] = apply_score(B, score_table(A, cols))
    lo, hi = np.quantile(B.score, [1 / 3, 2 / 3])
    B["grp"] = np.where(B.score <= lo, "하위 1/3", np.where(B.score >= hi, "상위 1/3", "가운데"))
    w = B.grp.map({"하위 1/3": 0.5, "가운데": 1.0, "상위 1/3": 1.5}).values
    flat, sized = CO.acct(B[["t", "r"]]), CO.acct(B.assign(r=B.r * w)[["t", "r"]])
    g = B.groupby("grp").r
    return dict(grp={k: dict(n=int(g.size()[k]), R=round(float(g.mean()[k]), 3), win=round(float((B.r[B.grp == k] > 0).mean()), 3)) for k in ("상위 1/3", "가운데", "하위 1/3") if k in g.size()},
                flat=[round(x, 1) for x in flat], sized=[round(x, 1) for x in sized],
                ok=bool(g.mean().get("상위 1/3", 0) > g.mean().get("하위 1/3", 0) + 0.1 and sized[2] > flat[2] + 0.05 * abs(flat[2])))


def live_feats(files):
    rows = []
    for f in files:
        try:
            S = json.loads((ROOT / f).read_text())
        except Exception:
            continue
        for j in S.get("journal", []) + S.get("trades", []):
            if j.get("feat") and j.get("R") is not None and (j.get("exit") is not None):
                rows.append({**j["feat"], "r": j["R"], "src": f.split("/")[-1]})
    return rows


LIVE = {"amd": ["data/us/amd_paper.json", "data/us/coin_amd.json", "data/us/lev10.json"],
        "ob": ["data/us/ob_paper.json", "data/us/coin_ob.json", "data/us/lev10_ob.json"],
        "tr10": ["data/us/trend10.json"]}
EXTRA = {"amd": ["mvol", "boxw"], "ob": ["fvg", "gap", "vhi", "k"], "tr10": []}


def run():
    B = {}
    for s in CO.SYMS:
        try:
            B[s] = CO.bars(s)
        except Exception as e:
            print(s, "시세 실패", e)
    if len(B) < 2:
        return
    F = {s: CO.common(d) for s, d in B.items()}
    X = {s: FR.context(d) for s, d in B.items()}
    C = FR.load(); out = {"made": CO.now().isoformat(timespec="minutes"), "labels": {**NUM, **CAT}, "formulas": {}}
    for key, (name, sim, pmin, lives) in CO.FORM.items():
        P = C[key]["params"]
        raw = {s: sim(d, F[s], P) for s, d in B.items()}
        D0 = CO.apply_filters(raw, C[key]["filters"])
        T = pd.concat([enrich(D0[s], B[s], X[s]) for s in D0 if len(D0[s])], ignore_index=True)
        cols = ["rsi", "trend", "vr", "atrp", "risk", "side", "htf", "session", "wkend"] + EXTRA[key]
        cols = [c for c in cols if c in T]
        mp = {c: buckets(T, c) for c in cols}
        mp = {c: v for c, v in mp.items() if v}
        spread = {c: round(max(x["R"] for x in v if x["n"] >= 30) - min(x["R"] for x in v if x["n"] >= 30), 3) for c, v in mp.items() if sum(x["n"] >= 30 for x in v) >= 2}
        test = sizing_test(T, cols)
        lv = live_feats(LIVE[key])
        out["formulas"][key] = dict(name=name, n=int(len(T)), R=round(float(T.r.mean()), 3), map=mp, spread=dict(sorted(spread.items(), key=lambda x: -x[1])),
                                    test=test, live_n=len(lv), live=lv[-300:])
        print(f"\n== {name} · 시험 {len(T)}번 평균 {T.r.mean():+.2f}R · 실제 기록 {len(lv)}번")
        for c, sp in list(out["formulas"][key]["spread"].items())[:5]:
            print(f"  결과 차이 큰 특징: {({**NUM, **CAT})[c]} — 칸끼리 최대 {sp:.2f}R 차이 · " + " / ".join(f"{x['b']}: {x['R']:+.2f}({x['n']})" for x in mp[c]))
        if test:
            print(f"  확신 점수(앞 1년으로 만들고 뒤 1년에 적용): " + " · ".join(f"{k} {v['R']:+.2f}R({v['n']})" for k, v in test["grp"].items())
                  + f" → 크기 0.5·1·1.5배: 수익÷낙폭 {test['flat'][2]} → {test['sized'][2]} {'✅' if test['ok'] else '✗'}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    run()
