"""
터틀 트레이딩 과거 검증 — S&P500+나스닥100 (지금 구성 종목, 생존 편향 있음), 2015~2026, 롱 전용, 빚 없이(현금 한도)
  1유닛 = 계좌 1% ÷ N, 종목당 최대 4유닛, 전체 최대 MAXU유닛, 체결은 돌파·손절 가격(갭이면 시가), 한 번 매매할 때마다 0.05% 비용
  결과 → data/us/turtle_backtest.json
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "scripts"))
import turtle_lib as TL

J = json.loads((ROOT / "research/us/data/prices.json").read_text())
U = {s["t"] for s in json.loads((ROOT / "data/us/universe.json").read_text())["stocks"]}
uni = sorted(U & set(J))
cal = [r[0] for r in J["^GSPC"]]
idx = {d: i for i, d in enumerate(cal)}
T, M = len(cal), len(uni)
O, H, L, C = (np.full((T, M), np.nan) for _ in range(4))
for j, t in enumerate(uni):
    for d, o, h, l, c, v in J[t]:
        i = idx.get(d)
        if i is not None:
            O[i, j], H[i, j], L[i, j], C[i, j] = o, h, l, c
print("지표 계산…", flush=True)
N = TL.wilder_n(H, L, C, 20)
HI20, LO10, HI55, LO20 = TL.roll_max_prev(H, 20), TL.roll_min_prev(L, 10), TL.roll_max_prev(H, 55), TL.roll_min_prev(L, 20)
spy = np.array([r[4] for r in J["^GSPC"]]); ma200 = pd.Series(spy).rolling(200).mean().values
mom = np.vstack([np.full((126, M), np.nan), C[126:] / C[:-126] - 1])

# 시스템1 걸러내기: 그날 20일 돌파가 '새 신호'이고 직전 가상 거래가 손실이었는지
print("걸러내기 계산…", flush=True)
ALLOW1 = np.zeros((T, M), bool)
for j in range(M):
    hyp, last_win = None, False
    for i in range(56, T):
        if not (np.isfinite(N[i - 1, j]) and np.isfinite(HI20[i, j]) and np.isfinite(C[i, j])):
            continue
        if hyp:
            stop = hyp[0] - 2 * hyp[1]; ex = None
            if L[i, j] <= stop: ex = min(O[i, j], stop)
            elif L[i, j] <= LO10[i, j]: ex = min(O[i, j], LO10[i, j])
            if ex is not None: last_win = ex > hyp[0]; hyp = None
        if not hyp and H[i, j] > HI20[i, j]:
            ALLOW1[i, j] = not last_win
            hyp = (max(O[i, j], HI20[i, j]), N[i - 1, j])

COST = 0.0005
START = idx[next(d for d in cal if d >= "2015-03-01")]


def sim(mode="both", mkt=False, risk=0.01, maxu=20, ucap=1.0):
    cash, pos, eq_hist, trades = 1.0, {}, [], []
    eq_prev = 1.0
    for i in range(START, T):
        # 1) 청산·손절
        for j in list(pos):
            p = pos[j]
            if not np.isfinite(L[i, j]):
                continue
            lo_ex = LO10[i, j] if p["sys"] == 1 else LO20[i, j]
            ex = why = None
            if L[i, j] <= p["stop"]: ex, why = min(O[i, j], p["stop"]), "stop"
            elif np.isfinite(lo_ex) and L[i, j] <= lo_ex: ex, why = min(O[i, j], lo_ex), "exit"
            if ex is not None:
                cash += p["sh"] * ex * (1 - COST)
                trades.append({"t": uni[j], "in": cal[p["i"]], "out": cal[i], "sys": p["sys"], "units": p["units"],
                               "pnl": p["sh"] * ex * (1 - COST) - p["cost"], "R": (p["sh"] * ex * (1 - COST) - p["cost"]) / p["risk0"], "why": why})
                del pos[j]
        # 2) 추가 매수
        units = sum(p["units"] for p in pos.values())
        for j, p in pos.items():
            while p["units"] < 4 and units < maxu and np.isfinite(H[i, j]) and H[i, j] >= p["next"]:
                px = max(O[i, j], p["next"]) * (1 + COST)
                sh = min(p["ush"], cash / px)
                if sh <= 0: break
                cash -= sh * px; p["sh"] += sh; p["cost"] += sh * px; p["units"] += 1; units += 1
                p["stop"] = px - 2 * p["n"]; p["next"] = px + 0.5 * p["n"]
        # 3) 신규 진입 (6개월 수익률 높은 순)
        if not (mkt and not (spy[i - 1] > ma200[i - 1])):
            cand = []
            for j in range(M):
                if j in pos or not np.isfinite(N[i - 1, j]) or not np.isfinite(H[i, j]) or N[i - 1, j] <= 0:
                    continue
                s1 = mode in ("s1", "both") and H[i, j] > HI20[i, j] and ALLOW1[i, j]
                s2 = mode in ("s2", "both") and np.isfinite(HI55[i, j]) and H[i, j] > HI55[i, j]
                if s1 or s2:
                    cand.append((-(mom[i - 1, j] if np.isfinite(mom[i - 1, j]) else -9), j, 1 if s1 else 2))
            for _, j, sy in sorted(cand):
                if units >= maxu: break
                n_ = N[i - 1, j]; lvl = HI20[i, j] if sy == 1 else HI55[i, j]
                px = max(O[i, j], lvl) * (1 + COST)
                ush = min(risk * eq_prev / n_, ucap * eq_prev / px)     # 한 유닛이 계좌의 ucap 넘지 않게
                sh = min(ush, cash / px)
                if sh * px < 0.2 * ush * px: continue                      # 현금이 모자라 유닛의 20%도 못 사면 건너뜀
                cash -= sh * px; units += 1
                p = pos[j] = {"i": i, "sys": sy, "n": n_, "ush": ush, "sh": sh, "cost": sh * px, "units": 1,
                              "stop": px - 2 * n_, "next": px + 0.5 * n_, "risk0": ush * 2 * n_}
                while p["units"] < 4 and units < maxu and H[i, j] >= p["next"]:
                    px2 = max(O[i, j], p["next"]) * (1 + COST); sh2 = min(ush, cash / px2)
                    if sh2 <= 0: break
                    cash -= sh2 * px2; p["sh"] += sh2; p["cost"] += sh2 * px2; p["units"] += 1; units += 1
                    p["stop"] = px2 - 2 * n_; p["next"] = px2 + 0.5 * n_
        eq = cash + sum(p["sh"] * (C[i, j] if np.isfinite(C[i, j]) else p["cost"] / p["sh"]) for j, p in pos.items())
        inv = 1 - cash / eq if eq > 0 else 0
        eq_hist.append((cal[i], eq, inv)); eq_prev = eq
    return eq_hist, trades


def stats(eh, trades=None):
    s = pd.Series([e for _, e, _ in eh], index=pd.to_datetime([d for d, _, _ in eh]))
    r = s.pct_change().dropna(); yrs = (s.index[-1] - s.index[0]).days / 365.25
    dd = s / s.cummax() - 1
    yr = s.resample("YE").last(); yr = yr / yr.shift(1).fillna(s.iloc[0]) - 1
    out = {"cagr": float(s.iloc[-1] ** (1 / yrs) - 1), "total": float(s.iloc[-1] - 1), "mdd": float(dd.min()),
           "sharpe": float(r.mean() / r.std() * np.sqrt(252)), "vol": float(r.std() * np.sqrt(252)),
           "years": {str(k.year): float(v) for k, v in yr.items()}}
    if eh and len(eh[0]) > 2:
        out["exposure"] = float(np.mean([x[2] for x in eh]))
    if trades is not None:
        R = np.array([t["R"] for t in trades]); w = R[R > 0]; lo = R[R <= 0]
        out.update(n=len(R), win=float((R > 0).mean()), avg_win_R=float(w.mean()) if len(w) else 0, avg_loss_R=float(lo.mean()) if len(lo) else 0,
                   best=sorted(trades, key=lambda t: -t["R"])[:5], hold=float(np.mean([(pd.Timestamp(t["out"]) - pd.Timestamp(t["in"])).days for t in trades])))
        for t in out["best"]:
            t["R"] = round(t["R"], 1); t.pop("pnl", None)
    return out


# 설정에 따라 얼마나 흔들리는지 (같은 원래 규칙 + 시장 필터, 유닛 한도만 바꿈)
SENS = []
for mu, uc in [(8, 0.12), (12, 0.08), (20, 0.05), (40, 0.025)]:
    eh, tr = sim(mode="both", mkt=True, maxu=mu, ucap=uc); x = stats(eh, tr)
    SENS.append({"maxu": mu, "ucap": uc, "cagr": x["cagr"], "mdd": x["mdd"], "sharpe": x["sharpe"]})
    print("민감도", mu, uc, round(x["cagr"] * 100, 1), round(x["mdd"] * 100), round(x["sharpe"], 2), flush=True)

spy_eh = [(cal[i], spy[i] / spy[START], 1) for i in range(START, T)]
res = {"S&P500 그냥 보유": stats(spy_eh)}
curves = {"S&P500 그냥 보유": spy_eh}
VARS = [("원래 규칙", {"mode": "both"}), ("원래 규칙 + 시장 필터", {"mode": "both", "mkt": True}),
        ("시스템1만 + 시장 필터", {"mode": "s1", "mkt": True}), ("시스템2만 + 시장 필터", {"mode": "s2", "mkt": True}),
        ("분산형 (0.5%·40유닛) + 시장 필터", {"mode": "both", "mkt": True, "risk": 0.005, "maxu": 40, "ucap": 0.025})]
for name, kw in VARS:
    kw = {"maxu": 12, "ucap": 0.08, **kw}
    eh, tr = sim(**kw)
    res[name] = stats(eh, tr); curves[name] = eh
    x = res[name]
    print(f"{name:<18} 연 {x['cagr']*100:+.1f}%  최대낙폭 {x['mdd']*100:.0f}%  샤프 {x['sharpe']:.2f}  거래 {x['n']}  승률 {x['win']*100:.0f}%  "
          f"평균 이익 {x['avg_win_R']:+.1f}R 손실 {x['avg_loss_R']:+.1f}R  투자비중 {x['exposure']*100:.0f}%", flush=True)
x = res["S&P500 그냥 보유"]; print(f"S&P500 그냥 보유     연 {x['cagr']*100:+.1f}%  최대낙폭 {x['mdd']*100:.0f}%  샤프 {x['sharpe']:.2f}")

# 월말 곡선만 저장
mon = {}
for k, eh in curves.items():
    s = pd.Series([e for _, e, _ in eh], index=pd.to_datetime([d for d, _, _ in eh])).resample("ME").last()
    mon[k] = [[d.strftime("%Y-%m"), round(float(v), 4)] for d, v in s.items()]
(ROOT / "data/us/turtle_backtest.json").write_text(json.dumps({
    "made": pd.Timestamp.now().strftime("%Y-%m-%d"), "period": f"{cal[START]} ~ {cal[-1]}", "universe": f"S&P500+나스닥100 지금 구성 {M}종목",
    "rules": "롱 전용 · 1유닛 = 계좌 1% ÷ N (단, 한 유닛이 계좌의 8%를 넘지 않게) · 종목당 4유닛, 전체 12유닛(원래 규칙의 한 방향 한도) · 빚 없음(현금 한도) · 시장 필터 = S&P500이 200일선 위일 때만 새로 진입 · 체결은 돌파·손절 가격(갭이면 시가) · 매매마다 0.05% 비용 · 같은 날 신호가 많으면 6개월 수익률 높은 순",
    "sensitivity": SENS,
    "results": res, "curves": mon}, ensure_ascii=False))
