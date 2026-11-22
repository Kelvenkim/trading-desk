"""오더블록 + AMD 2년 백테스트 (11/22 형 요청) — 1시간봉 BTC·ETH·SOL, 수수료 한쪽 0.05%
① 각각 따로 ② 둘 다 같이 굴린 계좌(같은 $10,000) ③ 겹친 자리(AMD 조작 구간에서 같은 방향 오더블록이 생긴 경우)"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "orderblock"); sys.path.insert(0, "amd")
from ob import load, find_obs, simulate
from amd import run as amd_run
OBP = dict(W=48, hold=72, K=2.0, need=("gap", "sweep", "fvg"), stop_rule=1, tp="half", cost=.0005)
AMDP = dict(N=24, m=6, entry="b", tgt="rr2")
rows_ob, rows_amd = [], []
for tk in ["BTC-USD", "ETH-USD", "SOL-USD"]:
    d = load(tk, "1h"); obs = [o for o in find_obs(d, {"K": 2.0}) if o["k"] == 2]
    T = simulate(d, obs, OBP); T["sym"] = tk[:3]; T["kind"] = "OB"; rows_ob.append(T)
    A = amd_run(d, AMDP); A["sym"] = tk[:3]; A["kind"] = "AMD"
    # 겹침: 조작 구간(i-1 ~ k+1)에서 같은 방향 OB(갭+유동성 흡수)가 생겼나
    ob_i = {1: [o["i"] for o in obs if o["side"] > 0 and o["gap"] and o["sweep"]], -1: [o["i"] for o in obs if o["side"] < 0 and o["gap"] and o["sweep"]]}
    A["ob_conf"] = [any(i - 1 <= x <= k + 1 for x in ob_i[s]) for s, i, k in zip(A.side, A.i, A.k)]
    rows_amd.append(A)
OB = pd.concat(rows_ob); AM = pd.concat(rows_amd)

def acct(T, risk):
    """진입 때 확정 자산 기준 크기, 정리 때 반영 (동시 보유 허용)"""
    ev = sorted([(r.te, 0, k) for k, r in T.iterrows()] + [(r.tx, 1, k) for k, r in T.iterrows()], key=lambda x: (x[0], -x[1]))
    eq = 1e4; sz = {}; C = []
    for tm, typ, k in ev:
        rk = risk[T.loc[k, "kind"]] if isinstance(risk, dict) else risk
        sz.setdefault(k, eq * rk)
        if typ: eq += sz[k] * T.loc[k, "r"]; C.append((tm, eq))
    s = pd.Series([e for _, e in C], index=[t for t, _ in C])
    m = s.resample("ME").last().ffill(); mr = m.pct_change().fillna(m.iloc[0] / 1e4 - 1)
    return dict(ret=s.iloc[-1] / 1e4 - 1, mdd=(s / s.cummax() - 1).min(), up_m=int((mr > 0).sum()), dn_m=int((mr <= 0).sum()), worst_m=mr.min())

def line(nm, T, risk):
    T = T.reset_index(drop=True); h = T.te.min() + (T.te.max() - T.te.min()) / 2; a = acct(T, risk)
    co = " ".join(f"{c} {T[T.sym == c].r.mean():+.2f}" for c in ["BTC", "ETH", "SOL"])
    print(f"{nm:<26} {len(T):>5}번 승률 {(T.r > 0).mean():>4.0%} 평균 {T.r.mean():+.3f}R | {co} | 앞1년 {T[T.te < h].r.mean():+.2f} 뒤1년 {T[T.te >= h].r.mean():+.2f} | 계좌 {a['ret']:+.0%} 최대낙폭 {a['mdd']:.0%} 월 +{a['up_m']}/−{a['dn_m']} 최악달 {a['worst_m']:+.1%}")

print(f"기간 {OB.te.min():%Y-%m-%d} ~ {OB.tx.max():%Y-%m-%d} · 1시간봉 · 수수료 한쪽 0.05%\n")
print("── 지금 모의 계좌 설정 (오더블록 1회 1%, AMD 1회 0.5%)")
line("① 오더블록만 (1%)", OB, 0.01)
line("② AMD만 (0.5%)", AM, 0.005)
line("③ 둘 다 같이 (1% + 0.5%)", pd.concat([OB, AM]), {"OB": 0.01, "AMD": 0.005})
print("\n── 같은 크기로 비교 (둘 다 1회 0.5%)")
line("① 오더블록만", OB, 0.005)
line("② AMD만", AM, 0.005)
line("③ 둘 다 같이", pd.concat([OB, AM]), 0.005)
print("\n── 겹친 자리: AMD 조작 구간에서 같은 방향 오더블록(갭+유동성 흡수)이 생긴 경우")
line("AMD + 오더블록 겹침", AM[AM.ob_conf], 0.005)
line("AMD 단독(겹침 없음)", AM[~AM.ob_conf], 0.005)
# 비관: 비용 0.1%
OB2 = pd.concat([simulate(load(t, "1h"), [o for o in find_obs(load(t, "1h"), {"K": 2.0}) if o["k"] == 2], {**OBP, "cost": .001}).assign(sym=t[:3], kind="OB") for t in ["BTC-USD", "ETH-USD", "SOL-USD"]])
AM2 = pd.concat([amd_run(load(t, "1h"), AMDP, .001).assign(sym=t[:3], kind="AMD") for t in ["BTC-USD", "ETH-USD", "SOL-USD"]])
print(f"\n── 비관(비용 한쪽 0.1%): 오더블록 평균 {OB2.r.mean():+.3f}R · AMD 평균 {AM2.r.mean():+.3f}R")
# 같은 시간 겹치는 포지션 수
ev = pd.concat([pd.DataFrame({"t": T.te, "d": 1}) for T in [OB, AM]] + [pd.DataFrame({"t": T.tx, "d": -1}) for T in [OB, AM]]).sort_values(["t", "d"])
print(f"동시 보유 최대 {ev.d.cumsum().max()}개")
