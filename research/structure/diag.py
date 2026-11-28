"""BOS/CHoCH 전략 — 어디가 문제인지 떼어 보기 (11/28 형: '진입이 문제인지 청산이 문제인지 정확히')
1시간봉 13코인 2년. 진입 4종 × 청산 여러 종 표 + 진입 직후 움직임 + 손절 뒤 되돌림.

진입
  S2  CHoCH→BOS 확인          S3  BOS 추세 따라가기        S4  S2+디스플레이스먼트
  RND 무작위 시점·무작위 방향   TRD 무작위 시점·그때 추세 방향  (손절 규칙은 모두 같은 '직전 확정 스윙')
청산 (모두 손절 우선, 최대 200봉)
  R1/R2/R3  1R·2R·3R 고정 익절    T12/T48  12봉·48봉 뒤 종가
  CH  반대 CHoCH 종가    TRL  ATR×3 따라가는 손절(샹들리에)
"""
import numpy as np, pandas as pd
import bos_test as B

rng = np.random.default_rng(1)
MAXH = 200


def entries(S, kind):
    n = len(S["c"])
    if kind in ("S2", "S3", "S4"):
        return [(i, s) for i, s, _ in B.signals(S, kind)]
    m = int(n * 0.03)                                       # 신호 수와 비슷하게
    idx = np.sort(rng.choice(np.arange(60, n - 2), m, replace=False))
    if kind == "RND":
        return [(i, int(rng.choice([1, -1]))) for i in idx]
    # TRD: 그 시점 추세(마지막 BOS/CHoCH 방향)
    tr = pd.Series(np.sign(S["ev"]).astype(float)).replace(0, np.nan).ffill().fillna(0).values
    return [(i, int(tr[i])) for i in idx if tr[i] != 0]


def trade(S, i, s, ex):
    o, h, l, c, atr, ev = S["o"], S["h"], S["l"], S["c"], S["atr"], S["ev"]
    n = len(c); k = i + 1
    if k >= n:
        return None
    e = o[k]; st = S["lastL"][i] if s == 1 else S["lastH"][i]
    if np.isnan(st):
        return None
    risk = (e - st) * s
    if risk < 0.3 * atr[i]:
        return None
    tgt = {"R1": 1, "R2": 2, "R3": 3}.get(ex)
    trail = st; x = None; j = k
    mfe = mae = 0.0
    for j in range(k, min(n, k + MAXH)):
        fav = ((h[j] if s == 1 else l[j]) - e) * s / risk
        adv = ((l[j] if s == 1 else h[j]) - e) * s / risk
        mae = min(mae, adv)
        if (s == 1 and l[j] <= trail) or (s == -1 and h[j] >= trail):
            x = trail; break
        mfe = max(mfe, fav)
        if tgt and fav >= tgt:
            x = e + s * tgt * risk; break
        if ex in ("T12", "T48") and j - k + 1 >= int(ex[1:]):
            x = c[j]; break
        if ex == "CH" and j > k and ev[j] == -2 * s:
            x = c[j]; break
        if ex == "TRL":
            cand = (h[j] - 3 * atr[j]) if s == 1 else (l[j] + 3 * atr[j])
            trail = max(trail, cand) if s == 1 else min(trail, cand)
    if x is None:
        x = c[j]
    r = (x - e) * s / risk - 2 * B.COST * e / risk
    stopped = (x == st)
    return dict(r=r, mfe=mfe, stopped=stopped, j=j, k=k, e=e, st=st, risk=risk, s=s)


def after_stop(S, t, look=48):
    """손절당한 뒤 look봉 안에 원래 방향으로 +1R/+2R 자리까지 갔는지 (손절이 너무 가까웠는지)"""
    h, l = S["h"], S["l"]
    j = t["j"]; seg = slice(j + 1, min(len(h), j + 1 + look))
    best = (h[seg].max() - t["e"]) * t["s"] / t["risk"] if t["s"] == 1 else (t["e"] - l[seg].min()) / t["risk"]
    return best


SS = {s: B.structure(B.load(s, "1h")) for s in B.H1}
EX = ["R1", "R2", "R3", "T12", "T48", "CH", "TRL"]
rows, diag = [], []
for kind in ["S2", "S3", "S4", "TRD", "RND"]:
    E = {s: entries(S, kind) for s, S in SS.items()}
    for ex in EX:
        R = []
        for sym, S in SS.items():
            busy = -1
            for i, s in E[sym]:
                if i < busy:
                    continue
                t = trade(S, i, s, ex)
                if t:
                    t["sym"] = sym; R.append(t); busy = t["j"] + 1
        T = pd.DataFrame(R)
        top = T.r.nlargest(int(len(T) * .05)).index
        rows.append(dict(entry=kind, exit=ex, n=len(T), win=round((T.r > 0).mean(), 3), avgR=round(T.r.mean(), 3),
                         avgR_no_top5=round(T.drop(top).r.mean(), 3), coins_pos=sum(g.r.mean() > 0 for _, g in T.groupby("sym"))))
        if ex == "R3":
            st = T[T.stopped]
            back = [after_stop(SS[r.sym], r) for _, r in st.iterrows()] if len(st) else []
            diag.append(dict(entry=kind, n=len(T),
                             reach_1R=round((T.mfe >= 1).mean(), 3), reach_2R=round((T.mfe >= 2).mean(), 3), reach_3R=round((T.mfe >= 3).mean(), 3),
                             stopped=round(T.stopped.mean(), 3),
                             stop_then_1R=round(np.mean([b >= 1 for b in back]), 3), stop_then_2R=round(np.mean([b >= 2 for b in back]), 3),
                             stop_risk_pct=round((T.risk / T.e).median() * 100, 2)))
R = pd.DataFrame(rows); D = pd.DataFrame(diag)
pd.set_option("display.width", 220)
print("=== 진입 × 청산: 거래당 평균 R (수수료 뺌) ===")
print(R.pivot(index="entry", columns="exit", values="avgR")[EX].to_string())
print("\n=== 같은 표, 상위 5% 대박 빼고 ===")
print(R.pivot(index="entry", columns="exit", values="avgR_no_top5")[EX].to_string())
print("\n=== 플러스 코인 수 /13 ===")
print(R.pivot(index="entry", columns="exit", values="coins_pos")[EX].to_string())
print("\n=== 진입 직후 움직임 (3R 익절 기준) · 손절 뒤 48봉 안 되돌림 ===")
print(D.to_string(index=False))
R.to_csv("diag_exit.csv", index=False); D.to_csv("diag_entry.csv", index=False)
