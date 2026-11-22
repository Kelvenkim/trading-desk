"""
오더블록(OB) 매매 시험 — 형이 정한 규칙(2026-11-21)을 그대로 코드로 옮김
진입: OB 구간까지 되돌아와 닿을 때만(지정가). 안 닿으면 진입 안 함.
  OB 모양: 음→양(상승 2캔들) / 양→음→양(상승 3캔들), 반대는 하락 OB
  필터: ① 유동성 흡수(OB 저점이 직전 L봉 저점을 깸) ② 구조물(OB 직후 FVG) ③ 갭(마지막 캔들 몸통 ≥ 앞 캔들 몸통 × K, 앞 캔들 도지 제외)
  상위 시간봉 일치: 5분 OB 구간이 살아 있는 1시간 OB 구간과 겹치면 '일치'
손절: 기준1 = OB 만든 모든 캔들의 꼬리 끝을 건드리면 / 기준2 = 꼬리 끝 밖에서 봉 마감하면
익절: ① OB 이후 파동 고점 갱신 → 절반 익절, 나머지는 진입가 손절 ② (근사) 반대 OB 출현 → 나머지 정리 ③ 최대 보유 시간
비용: 한쪽 수수료+체결 차이 (기본 0.05%, 지정가 0.02% 참고)
"""
import itertools, sys
import numpy as np, pandas as pd
from pathlib import Path

H = Path(__file__).parent / "data"


def load(t, iv):
    return pd.read_parquet(H / f"{t}_{iv}.parquet")


def atr(d, n=14):
    pc = d.close.shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().values


def find_obs(d, P):
    """모든 OB 후보: (형성 끝 봉 i, 방향 +1/−1, 진입가, 손절가, 형성 캔들 수, 필터 통과 dict)"""
    o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values
    A = atr(d); body = np.abs(c - o); rng = h - l
    bull = c > o; bear = c < o
    out = []
    L = P.get("L", 20)
    for i in range(L + 3, len(c) - 2):
        for side in (1, -1):
            up, dn = (bull, bear) if side > 0 else (bear, bull)
            if not (up[i] and dn[i - 1]):
                continue
            k = 3 if up[i - 2] else 2                           # 양→음→양(3) 또는 음→양(2)
            idx = list(range(i - k + 1, i + 1))
            first = i - 1                                       # 반대 색 캔들(기관 물량 캔들)
            if body[first] < P.get("dmin", 0.15) * A[i] or body[first] < 0.2 * rng[first]:
                gap_ok = False                                  # 도지 같은 기형 캔들은 제외
            else:
                gap_ok = body[i] >= P.get("K", 2.0) * body[first]
            disp = c[i] > h[first] if side > 0 else c[i] < l[first]   # 강한 돌파(반대 캔들 꼬리 넘김)
            if side > 0:
                stop = min(l[j] for j in idx)
                entry = h[first] if P.get("entry", "top") == "top" else (h[first] + stop) / 2
                sweep = stop < l[i - k + 1 - L:i - k + 1].min()
                fvg = l[i + 1] > h[i - 1]                        # 다음 봉 저가가 반대 캔들 고가보다 위 = 빈 구간
            else:
                stop = max(h[j] for j in idx)
                entry = l[first] if P.get("entry", "top") == "top" else (l[first] + stop) / 2
                sweep = stop > h[i - k + 1 - L:i - k + 1].max()
                fvg = h[i + 1] < l[i - 1]
            if abs(entry - stop) < 0.05 * A[i]:
                continue
            out.append(dict(i=i, side=side, entry=entry, stop=stop, k=k, gap=gap_ok, disp=disp, sweep=sweep, fvg=fvg))
    return out


def htf_zones(dh, P):
    """상위 시간봉 OB 구간 목록: (시작 시각, 끝 시각(무효화 또는 48봉 뒤), 방향, 아래, 위)"""
    obs = find_obs(dh, {**P, "K": 1.5})
    c = dh.close.values; t = dh.index; Z = []
    for ob in obs:
        if not ob["disp"]:
            continue
        lo, hi = sorted([ob["entry"], ob["stop"]])
        end = min(len(c) - 1, ob["i"] + 48)
        for j in range(ob["i"] + 1, end + 1):
            if (ob["side"] > 0 and c[j] < ob["stop"]) or (ob["side"] < 0 and c[j] > ob["stop"]):
                end = j; break
        Z.append((t[ob["i"] + 1], t[end], ob["side"], lo, hi))
    return Z


def simulate(d, obs, P, Z=None):
    o, h, l, c = d.open.values, d.high.values, d.low.values, d.close.values
    t = d.index; N = len(c); cost = P.get("cost", 0.0005)
    W, HOLD = P.get("W", 48), P.get("hold", 96)
    opp = {}                                                     # 반대 OB 형성 봉 (나머지 정리 근거)
    for ob in obs:
        if ob["disp"]:
            opp.setdefault(ob["i"], set()).add(ob["side"])
    trades = []; busy_until = -1
    for ob in obs:
        i, s, e, st = ob["i"], ob["side"], ob["entry"], ob["stop"]
        if i <= busy_until:
            continue
        need = P.get("need", ())
        if any(not ob[f] for f in need):
            continue
        mtf = False
        if Z is not None:
            lo, hi = sorted([e, st])
            mtf = any(z[2] == s and z[0] <= t[i] <= z[1] and z[3] <= hi and lo <= z[4] for z in Z)
            if P.get("mtf") and not mtf:
                continue
        # 진입 대기: W봉 안에 구간에 닿아야 함. 닿기 전에 손절가를 넘어 마감하면 취소
        j = None; wave = h[i] if s > 0 else l[i]
        for k in range(i + 1, min(N, i + 1 + W)):
            if (s > 0 and l[k] <= e) or (s < 0 and h[k] >= e):
                j = k; break
            wave = max(wave, h[k]) if s > 0 else min(wave, l[k])
            if (s > 0 and c[k] < st) or (s < 0 and c[k] > st):
                break
        if j is None:
            continue
        risk = abs(e - st)
        if abs(wave - e) < P.get("minrr", 1.0) * risk:            # 파동 고점까지 거리가 손절 거리보다 짧으면 안 들어감
            continue
        fill = min(o[j], e) if s > 0 else max(o[j], e)           # 갭으로 더 좋은 가격에 열리면 그 가격
        r_unit = risk / e
        legs = []; rem = 1.0; be = False; stop = st; x_why = "보유 시간 끝"
        for k in range(j, min(N, j + HOLD)):
            # 손절
            hit = (l[k] <= stop) if s > 0 else (h[k] >= stop)
            if P.get("stop_rule", 1) == 2 and not be:
                hit = (c[k] < stop) if s > 0 else (c[k] > stop)
            if hit:
                px = c[k] if (P.get("stop_rule", 1) == 2 and not be) else (min(o[k], stop) if s > 0 else max(o[k], stop)) if k > j else stop
                legs.append((rem, px)); rem = 0; x_why = "본전 손절" if be else "손절"; break
            # 익절 1: 파동 고점 갱신
            if not be and ((s > 0 and h[k] >= wave) or (s < 0 and l[k] <= wave)):
                part = 1.0 if P.get("tp", "half") == "all" else 0.5
                legs.append((part, wave)); rem -= part; be = True; stop = fill
                if rem <= 1e-9:
                    x_why = "파동 고점 익절"; break
                continue
            # 익절 3: 반대 OB 출현
            if k > j and (-s) in opp.get(k, ()):
                if be or P.get("opp_exit_early", False):
                    legs.append((rem, c[k])); rem = 0; x_why = "반대 오더블록"; break
        if rem > 0:
            k = min(N - 1, j + HOLD - 1); legs.append((rem, c[k]))
        gross = sum(w * s * (px / fill - 1) for w, px in legs)
        net = gross - cost - sum(w for w, _ in legs) * cost
        trades.append(dict(t=t[i], te=t[j], tx=t[min(k, N - 1)], side=s, r=net / r_unit, pct=net, why=x_why, mtf=mtf, k=ob["k"],
                           sweep=ob["sweep"], fvg=ob["fvg"], gap=ob["gap"], risk=r_unit))
        busy_until = k
    return pd.DataFrame(trades)


def stats(T):
    if T is None or len(T) < 5:
        return dict(n=0 if T is None else len(T))
    r = T.r; eq = (1 + T.pct).cumprod()
    return dict(n=len(T), win=(r > 0).mean(), avgR=r.mean(), pf=r[r > 0].sum() / max(1e-9, -r[r < 0].sum()),
                tot=eq.iloc[-1] - 1, mdd=(eq / eq.cummax() - 1).min(), risk=T.risk.mean())


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    ivs = sys.argv[1:] or ["1h", "15m", "5m"]
    rows = []
    for iv in ivs:
        for tk in ["BTC-USD", "ETH-USD", "SOL-USD"]:
            d = load(tk, iv)
            Z = htf_zones(load(tk, "1h"), {}) if iv in ("5m", "15m") else None
            base = dict(W=48, hold=96 if iv != "1h" else 72)
            grid = {
                "need": [(), ("gap",), ("gap", "disp"), ("sweep",), ("fvg",), ("gap", "fvg"), ("gap", "sweep"), ("gap", "sweep", "fvg")],
                "stop_rule": [1, 2], "tp": ["half", "all"], "mtf": [False, True] if Z is not None else [False],
            }
            for K in (1.5, 2.0, 3.0):
                obs = find_obs(d, {"K": K})
                for need, sr, tp, mtf in itertools.product(*grid.values()):
                    if K != 2.0 and need not in [("gap",), ("gap", "sweep", "fvg")]:
                        continue
                    P = {**base, "K": K, "need": need, "stop_rule": sr, "tp": tp, "mtf": mtf}
                    T = simulate(d, obs, P, Z)
                    half = d.index[0] + (d.index[-1] - d.index[0]) / 2
                    a, b = (T[T.t < half], T[T.t >= half]) if len(T) else (T, T)
                    S = stats(T)
                    rows.append(dict(iv=iv, tk=tk[:3], K=K, need="+".join(need) or "없음", stop=sr, tp=tp, mtf=mtf, **S,
                                     a=a.r.mean() if len(a) else np.nan, b=b.r.mean() if len(b) else np.nan))
    R = pd.DataFrame(rows)
    R.to_csv(Path(__file__).parent / "grid.csv", index=False)
    g = R.groupby(["iv", "K", "need", "stop", "tp", "mtf"]).agg(n=("n", "sum"), avgR=("avgR", "mean"), win=("win", "mean"), pf=("pf", "mean"),
                                                             pos_coins=("avgR", lambda x: (x > 0).sum()), a=("a", "mean"), b=("b", "mean")).reset_index()
    for iv in ivs:
        X = g[g.iv == iv].sort_values("avgR", ascending=False)
        print(f"\n===== {iv} (코인 3개 평균, 수수료 한쪽 0.05%) — 상위 12 / 전체 {len(X)}")
        print(X.head(12).round(3).to_string(index=False))
        print("하위 3:"); print(X.tail(3).round(3).to_string(index=False))
