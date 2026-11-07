"""
터틀 신호 (매일) → data/us/turtle.json
  각 종목에 터틀 규칙을 2년치 일봉으로 그대로 돌려서 '지금 상태'를 구함:
    오늘 진입 / 내일 돌파 가능(1N 이내) / 보유 중(손절·추가·청산 가격) / 오늘 청산
  수량은 화면에서 계좌 크기를 넣으면 계산 (1유닛 = 계좌 1% ÷ N, 한 유닛이 계좌의 8% 넘지 않게)
us_daily.py 안에서 build(P, ...)로 불러요. 따로 실행: python scripts/us_turtle.py
"""
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import turtle_lib as TL

OUT = ROOT / "data/us/turtle.json"


def r2(x, d=2):
    return None if x is None or not np.isfinite(x) else round(float(x), d)


def one(rows):
    a = np.array([r[1:5] for r in rows], float)
    o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    if len(c) < 80:
        return None
    N = TL.wilder_n(h[:, None], l[:, None], c[:, None], 20)[:, 0]
    hi20, lo10 = TL.roll_max_prev(h, 20), TL.roll_min_prev(l, 10)
    hi55, lo20 = TL.roll_max_prev(h, 55), TL.roll_min_prev(l, 20)
    trades, pos, st = TL.stock_trades(o, h, l, c, N, hi20, lo10, hi55, lo20, mode="both")
    i = len(c) - 1
    n = N[i]
    # 내일 기준 가격 (오늘까지 포함한 창)
    t20, t55 = float(np.max(h[-20:])), float(np.max(h[-55:]))
    x10, x20 = float(np.min(l[-10:])), float(np.min(l[-20:]))
    s1_ok = not st["last_s1_win"] and not st["hyp_open"]
    row = {"close": r2(c[i]), "chg": r2(c[i] / c[i - 1] - 1, 4), "N": r2(n, 3), "Npct": r2(n / c[i], 4),
           "t20": r2(t20), "t55": r2(t55), "x10": r2(x10), "x20": r2(x20), "s1_ok": bool(s1_ok),
           "r55": r2(c[i] / c[-56] - 1, 4), "day": rows[-1][0]}
    st_ = None
    if pos:
        avg = float(np.mean(pos["fills"]))
        ex = x10 if pos["sys"] == 1 else x20
        stop_eff = max(pos["stop"], ex)
        st_ = {"kind": "new" if pos["entry_i"] == i else "hold", "sys": pos["sys"], "since": rows[pos["entry_i"]][0], "days": i - pos["entry_i"],
               "units": pos["units"], "fills": [r2(f) for f in pos["fills"]], "avg": r2(avg), "stop": r2(pos["stop"]), "exit": r2(ex),
               "stop_eff": r2(stop_eff), "next_add": r2(pos["next_add"]) if pos["units"] < 4 else None, "n0": r2(pos["n"], 3),
               "pl": r2(c[i] / avg - 1, 4), "R": r2((c[i] - avg) / (2 * pos["n"]), 2)}
    elif trades and trades[-1]["exit_i"] == i:
        t = trades[-1]; avg = float(np.mean(t["fills"]))
        st_ = {"kind": "exit", "sys": t["sys"], "since": rows[t["entry_i"]][0], "units": t["units"], "avg": r2(avg), "exit_px": r2(t["exit"]),
               "why": t["why"], "pl": r2(t["exit"] / avg - 1, 4)}
    else:
        trig = t20 if s1_ok else t55
        dist = (trig - c[i]) / n if n > 0 else 9
        if dist <= 1.0:
            st_ = {"kind": "near", "sys": 1 if s1_ok else 2, "trigger": r2(trig), "distN": r2(dist, 2), "stop_if": r2(trig - 2 * n)}
    if not st_:
        return None
    row["st"] = st_
    # 지난 2년 이 종목 터틀 성적 (참고)
    done = [t for t in trades]
    if done:
        R = [(t["exit"] - np.mean(t["fills"])) / (2 * t["n"]) for t in done]
        row["hist"] = {"n": len(R), "win": r2(np.mean([x > 0 for x in R]), 2), "sumR": r2(sum(R), 1)}
    return row


def build(P, uni, names, ko, regime, prim=None, tnames=None):
    rows = []
    for t in uni:
        if t not in P:
            continue
        try:
            r = one(P[t][-520:])
        except Exception:
            r = None
        if r:
            r.update(code=t, name=names.get(t, t), ko=ko.get(t), theme=(tnames or {}).get((prim or {}).get(t)))
            rows.append(r)
    cnt = {}
    for r in rows:
        cnt[r["st"]["kind"]] = cnt.get(r["st"]["kind"], 0) + 1
    bt = {}
    try:
        B = json.loads((ROOT / "data/us/turtle_backtest.json").read_text())
        bt = {"period": B["period"], "res": {k: {kk: v[kk] for kk in ("cagr", "mdd", "sharpe") if kk in v} for k, v in B["results"].items()}}
    except Exception:
        pass
    day = max((r["day"] for r in rows), default="")
    out = {"date": day, "regime": regime, "count": cnt, "n_uni": len(uni), "rows": rows, "bt": bt}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("터틀 신호:", cnt, flush=True)
    return out


if __name__ == "__main__":
    import us_prices as UP
    from us_narr_def import NARR, EXTRA_KO
    U = json.loads((ROOT / "data/us/universe.json").read_text())
    uni = [s["t"] for s in U["stocks"]]
    P = UP.download(uni + ["^GSPC"], period="2y")
    sp = [r[4] for r in P["^GSPC"]]
    ma = float(np.mean(sp[-200:]))
    prim = {}
    for n in NARR:
        for t in n["tickers"]:
            prim.setdefault(t, n["key"])
    build(P, uni, {s["t"]: s["name"] for s in U["stocks"]}, {**U.get("ko", {}), **EXTRA_KO},
          {"up": sp[-1] > ma, "sp_vs200": sp[-1] / ma - 1}, prim, {n["key"]: n["name"] for n in NARR})
