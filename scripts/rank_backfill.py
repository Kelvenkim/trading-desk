"""
과거 검증(백필): 2015년부터 5거래일마다 '그날 알 수 있던 정보만으로' 순위를 매기고 5일·20일 뒤 결과를 채점.
가중치도 그 시점까지 채점이 끝난 결과만으로 정함(미래 정보 사용 없음).
DART_API_KEY 가 있으면 실적 항목도 과거 공시로 검증.

한계: 종목 목록이 '현재' 시총 상위 300이라, 그 사이 망하거나 빠진 종목이 없음(생존 편향) → 실제보다 좋게 나올 수 있음.
뉴스는 과거 제목을 모을 수 없어 백필 불가 → 매일 실행하면서 쌓임.

실행: python scripts/rank_backfill.py   (가격 데이터: research/rank/data/prices300.json, 없으면 research/rank/fetch.py 먼저)
"""
import json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rank_lib as L
import rank_dart as D

PX = ROOT / "research/rank/data/prices300.json"
OUT = ROOT / "data/rank/backfill.json"
STEP = 5


def load_macro(start="2013-01-01"):
    import yfinance as yf
    x = yf.download(["^TNX", "KRW=X"], start=start, progress=False, auto_adjust=False)["Close"]
    return x["^TNX"].dropna(), x["KRW=X"].dropna()


def earnings_timeline(codes):
    """종목별 [(공시일, 실적 원점수)] — DART 키 있을 때만"""
    if not D.key():
        return None
    cmap = D.corp_codes(codes, ROOT / "data/rank/corpcode.json")
    tl = {c: [] for c in codes}
    this_year = pd.Timestamp.today().year
    for y in range(2014, this_year + 1):
        for rp in ("11013", "11012", "11014", "11011"):
            recs = D.fetch_reports(cmap, codes, y, rp)
            for c, r in recs.items():
                v = D.earn_raw(r)
                if v is not None:
                    tl[c].append((r["rcept_date"], v))
            print("DART", y, D.REPRT[rp], len(recs), flush=True)
    for c in tl:
        tl[c].sort()
    return tl


def earn_on(tl, code, day, max_age=200):
    """day 전날까지 공시된 가장 최근 실적 (200일 넘게 지난 건 버림)"""
    if not tl or not tl.get(code):
        return np.nan
    d = day.strftime("%Y-%m-%d")
    best = None
    for rd, v in tl[code]:
        if rd < d:
            best = (rd, v)
        else:
            break
    if not best or (day - pd.Timestamp(best[0])).days > max_age:
        return np.nan
    return best[1]


def clean(o):
    """NaN → null, 소수 4자리"""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, float):
        return None if not np.isfinite(o) else round(o, 4)
    return o


def main():
    t0 = time.time()
    J = json.loads(PX.read_text())
    cal = sorted(J["ks200"].keys())
    C, H, V = L.wide(J["stocks"], cal)
    tnx, krw = load_macro()
    F = L.price_factors(C, H, V, L.macro_aligned(tnx, C.index), L.macro_aligned(krw, C.index))
    tl = earnings_timeline(list(C.columns))
    fwd = {h: C.shift(-h) / C - 1 for h in L.HORIZONS}
    dates = [d for d in C.index[400::STEP] if d + pd.Timedelta(days=1) <= C.index[-1]]
    pos = {d: i for i, d in enumerate(C.index)}
    records, combo = [], []
    for d in dates:
        i = pos[d]
        cols = C.columns[C.loc[d].notna()]
        Z = {f: L.xrank(F[f].loc[d, cols]) for f in L.PRICE_FACTORS}
        if tl:
            Z["earn"] = L.xrank(pd.Series({c: earn_on(tl, c, d) for c in cols}))
        rec = {"date": d.strftime("%Y-%m-%d"), "src": "backfill", "step": STEP, "ic": {}, "ic5": {}}
        have20 = i + 20 < len(C.index)
        for f, z in Z.items():
            raw = F[f].loc[d, cols] if f in F else z.where(z != 0)
            if have20:
                rec["ic"][f] = L.spearman(raw, fwd[20].loc[d, cols])
            if i + 5 < len(C.index):
                rec["ic5"][f] = L.spearman(raw, fwd[5].loc[d, cols])
        # 그 시점까지 '채점이 끝난' 기록만으로 가중치 (20거래일 지난 것)
        known = [r for r in records if pos[pd.Timestamp(r["date"])] + 20 <= i]
        W = L.learn_weights(known, asof=d)
        s = L.combine(Z, W)
        row = {"date": rec["date"], "n": int(len(cols))}
        for h in L.HORIZONS:
            if i + h < len(C.index):
                fr = fwd[h].loc[d, cols]
                top = s.sort_values(ascending=False).index[:20]
                row[f"ic{h}"] = L.spearman(s, fr)
                row[f"top{h}"] = float(fr[top].mean())
                row[f"all{h}"] = float(fr.mean())
                row[f"hit{h}"] = float((fr[top] > fr.median()).mean())
        combo.append(row)
        if have20:
            records.append(rec)
    Wnow = L.learn_weights(records, asof=C.index[-1])
    out = {"made": pd.Timestamp.today().strftime("%Y-%m-%d"), "universe": len(C.columns), "step": STEP,
           "has_earn": bool(tl), "records": records, "combo": combo, "weights_now": Wnow,
           "note": "현재 시총 상위 300 기준(생존 편향). 종가→종가 수익률. 뉴스는 과거 데이터 없음."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(clean(out), ensure_ascii=False, separators=(",", ":")))
    print(f"done {len(dates)} dates, {time.time() - t0:.0f}s")
    return out


if __name__ == "__main__":
    main()
