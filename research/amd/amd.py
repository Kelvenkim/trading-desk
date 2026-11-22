"""매집(A) → 조작(M) → 분산(D) 시험 (11/22 형 아이디어, formulas/amd.png)
매집: 최근 N봉 박스(고가~저가) 폭 ≤ m × ATR(14) → 박스 안 볼륨 프로파일로 POC
조작: 박스 아래(위)를 깨는 봉 → 3봉 안에 박스 안으로 다시 마감 (가짜 이탈 = 손절 물량 쓸기)
진입: a = 복귀 봉 마감 다음 봉 시가 / b = POC 지정가(닿거나 더 좋은 가격, 12봉 안)
손절: 조작 극단 ± 0.1 ATR · 목표: rr2 / rr3 / box(박스 반대쪽, 손익비 1 미만이면 건너뜀) · 최대 48봉 · 수수료 한쪽 0.05%"""
import itertools, sys
import numpy as np, pandas as pd
sys.path.insert(0, "../orderblock")
from ob import load, atr

def poc_of(h, l, v, rows=24):
    lo, hi = l.min(), h.max(); st = (hi - lo) / rows; prof = np.zeros(rows)
    for hh, ll, vv in zip(h, l, v):
        if vv <= 0 or hh <= ll: continue
        r0 = min(rows - 1, int((ll - lo) / st)); r1 = min(rows - 1, int((hh - lo) / st))
        for r in range(r0, r1 + 1):
            bl = lo + r * st; prof[r] += vv * (min(bl + st, hh) - max(bl, ll)) / (hh - ll)
    return lo + (prof.argmax() + .5) * st

def run(d, P, cost=0.0005):
    o, h, l, c, v = (d[k].values for k in ("open", "high", "low", "close", "volume")); A = atr(d); N = len(c)
    n, m = P["N"], P["m"]; out = []; i = n + 20
    while i < N - 2:
        blo, bhi = l[i - n:i].min(), h[i - n:i].max()
        if bhi - blo > m * A[i - 1]:
            i += 1; continue
        side = 1 if l[i] < blo else -1 if h[i] > bhi else 0
        if not side:
            i += 1; continue
        # 조작: i부터 3봉 안에 박스 안으로 마감
        ext = l[i] if side > 0 else h[i]; k = None
        for j in range(i, min(N - 1, i + 3)):
            ext = min(ext, l[j]) if side > 0 else max(ext, h[j])
            if (side > 0 and c[j] > blo) or (side < 0 and c[j] < bhi):
                k = j; break
        if k is None:
            i += 3; continue
        poc = poc_of(h[i - n:i], l[i - n:i], v[i - n:i]); stop = ext - side * 0.1 * A[k]
        # 진입
        if P["entry"] == "a":
            e, j0 = o[k + 1], k + 1
        else:
            j0 = None
            for j in range(k + 1, min(N, k + 13)):
                if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop): break
                if (side > 0 and l[j] <= poc) or (side < 0 and h[j] >= poc):
                    j0 = j; e = min(o[j], poc) if side > 0 else max(o[j], poc); break
            if j0 is None:
                i = k + 1; continue
        risk = (e - stop) * side
        if risk <= 0.05 * A[k]:
            i = k + 1; continue
        tgt = {"rr2": e + side * 2 * risk, "rr3": e + side * 3 * risk, "box": bhi if side > 0 else blo}[P["tgt"]]
        if (tgt - e) * side < risk:
            i = k + 1; continue
        x = None; j = j0
        while j < min(N, j0 + 48):
            if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
                x = (min(o[j], stop) if side > 0 else max(o[j], stop)) if j > j0 else stop; break
            if (side > 0 and h[j] >= tgt) or (side < 0 and l[j] <= tgt):
                x = tgt; break
            j += 1
        if x is None: j = min(N - 1, j); x = c[j]
        net = side * (x / e - 1) - 2 * cost
        out.append((d.index[i], net / (risk / e), net, risk / e, d.index[j0], d.index[min(j, N - 1)], side, i, k)); i = j + 1
    return pd.DataFrame(out, columns=["t", "r", "pct", "risk", "te", "tx", "side", "i", "k"])

if __name__ == "__main__":
    iv = sys.argv[1] if len(sys.argv) > 1 else "1h"
    D = {t: load(t, iv) for t in ["BTC-USD", "ETH-USD", "SOL-USD"]}
    rows = []
    for N, m, en, tg in itertools.product([12, 24, 48], [3, 4, 6], ["a", "b"], ["rr2", "rr3", "box"]):
        P = dict(N=N, m=m, entry=en, tgt=tg); rec = dict(**P); qs = []; allr = []
        for t, d in D.items():
            T = run(d, P); q = [d.index[0] + (d.index[-1] - d.index[0]) * f for f in (0, .25, .5, .75, 1.01)]
            rec[t[:3]] = T.r.mean() if len(T) else np.nan; rec[t[:3] + "_n"] = len(T); allr += list(T.r)
            qs += [T[(T.t >= q[k]) & (T.t < q[k + 1])].r.mean() for k in range(4)]
        rec["n"] = len(allr); rec["avgR"] = np.mean(allr) if allr else np.nan; rec["win"] = np.mean(np.array(allr) > 0) if allr else np.nan
        rec["pos_q"] = int(np.nansum(np.array(qs) > 0)); rec["coins+"] = int(sum(rec[k] > 0 for k in ("BTC", "ETH", "SOL")))
        rows.append(rec)
    R = pd.DataFrame(rows); R.to_csv(f"amd_{iv}.csv", index=False); pd.set_option("display.width", 250)
    print(R.sort_values("avgR", ascending=False).head(15).round(3).to_string(index=False))
    print("\n진입별", R.groupby("entry").avgR.mean().round(3).to_dict(), "목표별", R.groupby("tgt").avgR.mean().round(3).to_dict(), "N별", R.groupby("N").avgR.mean().round(3).to_dict(), "m별", R.groupby("m").avgR.mean().round(3).to_dict())
