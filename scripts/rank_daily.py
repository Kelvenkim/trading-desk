"""
매일 장 마감 후 실행: 시총 상위 300 종목 점수 → 순위 → 기록 → 지난 순위 채점 → 가중치 갱신

출력 (사이트가 읽음)
  data/rank/latest.json        오늘 순위
  data/rank/report.json        신뢰도 성적표 (과거 검증 + 실제 운영 채점)
  data/rank/snap/날짜.json      그날 순위 기록 (나중에 채점용, 지우지 않음)
  data/rank/live.json          실제 운영 채점 결과 누적

실행: python scripts/rank_daily.py [--force]
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rank_lib as L
import rank_dart as D

OUT = ROOT / "data/rank"
SNAP = OUT / "snap"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
N_UNIVERSE = 300


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        o = float(o)
        return None if not np.isfinite(o) else round(o, 4)
    if isinstance(o, np.integer):
        return int(o)
    return o


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":")))


def universe():
    import FinanceDataReader as fdr
    U = fdr.StockListing("KRX")
    U = U[~U["Name"].str.contains(r"(우|우B|우C|\(전환\))$|스팩", regex=True)]
    U = U[U["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"])].sort_values("Marcap", ascending=False).head(N_UNIVERSE)
    return U


def fetch_prices(codes, start):
    import FinanceDataReader as fdr

    def one(c):
        for k in range(3):
            try:
                df = fdr.DataReader(c, start)
                df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
                return c, [[d.strftime("%Y-%m-%d"), float(r.Open), float(r.High), float(r.Low), float(r.Close), float(r.Volume)]
                           for d, r in df.iterrows()]
            except Exception:
                time.sleep(1 + k * 2)
        return c, []

    with ThreadPoolExecutor(8) as ex:
        return dict(ex.map(one, codes))


def short_name(name):
    for suf in ("홀딩스", "지주", "(주)"):
        if name.endswith(suf) and len(name) > len(suf) + 1:
            return name[: -len(suf)]
    return name


def fetch_news(code, name="", days=3):
    """네이버 증권 종목 뉴스 최근 제목 → (점수 평균, 건수, 대표 제목들)"""
    url = f"https://m.stock.naver.com/api/news/stock/{code}?pageSize=30&page=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"})
        with urllib.request.urlopen(req, timeout=20) as r:
            groups = json.loads(r.read())
    except Exception:
        return None
    cut = (NOW - timedelta(days=days)).strftime("%Y%m%d%H%M")
    seen, items = set(), []
    for g in groups or []:
        for it in g.get("items", [])[:1]:          # 같은 사건 묶음은 대표 1건만
            t = it.get("title", "").replace("&quot;", '"').replace("&amp;", "&")
            if it.get("datetime", "") < cut or t in seen:
                continue
            if name and short_name(name) not in t:      # 다른 회사 얘기가 섞인 기사 제외
                continue
            seen.add(t)
            items.append({"t": t, "d": it.get("datetime"), "s": L.headline_score(t), "o": it.get("officeName"),
                          "u": f"https://n.news.naver.com/mnews/article/{it.get('officeId')}/{it.get('articleId')}"})
    if not items:
        return {"tone": 0.0, "n": 0, "items": []}
    tone = float(np.mean([x["s"] for x in items]))
    # 단어가 하나도 안 걸린 제목만 있으면 중립
    items.sort(key=lambda x: -abs(x["s"]))
    return {"tone": tone, "n": len(items), "items": items[:4]}


def fetch_macro():
    import yfinance as yf
    x = yf.download(["^TNX", "KRW=X"], period="2y", progress=False, auto_adjust=False)["Close"]
    return x["^TNX"].dropna(), x["KRW=X"].dropna()


def earnings_now(codes):
    if not D.key():
        return None, "DART 키 없음 (GitHub Secrets 에 DART_API_KEY 를 넣으면 실적 항목이 켜져요)"
    cmap = D.corp_codes(codes, OUT / "corpcode.json")
    best = {}
    for y, rp in D.report_list(NOW):
        recs = D.fetch_reports(cmap, codes, y, rp)
        for c, r in recs.items():
            if c not in best or r["rcept_date"] > best[c]["rcept_date"]:
                best[c] = r
    today = NOW.strftime("%Y-%m-%d")
    lim = (NOW - timedelta(days=200)).strftime("%Y-%m-%d")
    best = {c: r for c, r in best.items() if lim <= r["rcept_date"] <= today}
    return best, f"DART {len(best)}개 회사 실적"


def grade(C, live):
    """지난 기록 중 5일·20일이 지난 것 채점"""
    done = {(r["date"], r["h"]) for r in live}
    pos = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(C.index)}
    added = 0
    for p in sorted(SNAP.glob("*.json")):
        day = p.stem
        if day not in pos:
            continue
        i = pos[day]
        S = None
        for h in L.HORIZONS:
            if (day, h) in done or i + h >= len(C.index):
                continue
            S = S or json.loads(p.read_text())
            codes = [c for c in S["stocks"] if c in C.columns]
            c0 = pd.Series({c: S["stocks"][c]["c"] for c in codes})
            c1 = C.iloc[i + h][codes]
            fr = c1 / c0 - 1
            ic = {}
            for f in L.FACTORS:
                raw = pd.Series({c: S["stocks"][c]["raw"].get(f) for c in codes}, dtype=float)
                if raw.notna().sum() >= 20 and raw.nunique() > 3:
                    ic[f] = L.spearman(raw, fr)
            sc = pd.Series({c: S["stocks"][c]["s"] for c in codes}, dtype=float)
            active = any(S.get("weights", {}).values())
            top = sc.sort_values(ascending=False).index[:20]
            rec = {"date": day, "h": h, "src": "live", "step": 1, "ic": ic, "all": float(fr.mean()), "active": active}
            if active:
                rec.update({"combo_ic": L.spearman(sc, fr), "top": float(fr[top].mean()), "hit": float((fr[top] > fr.median()).mean())})
            if all("o" in S["stocks"][c] for c in codes):
                o = pd.Series({c: S["stocks"][c]["o"] for c in codes}, dtype=float)
                ot = o.sort_values(ascending=False, kind="stable").index[:20]
                g = o.map(L.grade_of)
                rec.update({"o_ic": L.spearman(o, fr), "o_top": float(fr[ot].mean()),
                            "o_grade": {k: float(fr[g == k].mean()) for k in "SABCD" if (g == k).sum() >= 3},
                            "o_best": [[c, S["stocks"][c].get("n", c), float(fr[c])] for c in ot[:5]]})
            live.append(rec)
            added += 1
    return added


def nmean(xs):
    xs = [x for x in xs if x is not None and np.isfinite(x)]
    return float(np.mean(xs)) if xs else None


def summarize(bf, live):
    """성적표: 과거 검증(연도별) + 실제 운영"""
    rep = {"made": NOW.strftime("%Y-%m-%d %H:%M"), "backfill": None, "live": {}}
    if bf:
        cb = pd.DataFrame(bf["combo"])
        cb["year"] = cb["date"].str[:4]
        g = cb.dropna(subset=["o_top20"])
        ex = g["o_top20"] - g["all20"]
        # 겹치지 않게 20거래일(=4칸)마다 하나씩 뽑아 누적
        nonover = g.iloc[::4]
        cum = (1 + nonover["o_top20"]).cumprod(), (1 + nonover["all20"]).cumprod()
        yrs = []
        for y, gy in g.groupby("year"):
            e = gy["o_top20"] - gy["all20"]
            yrs.append({"year": y, "n": len(gy), "ic": gy["o_ic20"].mean(), "ex20": e.mean(), "beat": (e > 0).mean()})
        grades = {k: nmean([r["o_grade20"].get(k, np.nan) - r["all20"] for r in bf["combo"] if r.get("o_grade20")]) for k in "SABCD"}
        parts = {k: nmean([r["o_part_ic"].get(k) for r in bf["combo"] if r.get("o_part_ic")]) for k in L.OURS}
        va = cb[(cb["active"] == True)].dropna(subset=["top20"]) if {"active", "top20"} <= set(cb.columns) else cb.iloc[0:0]
        rep["backfill"] = {
            "from": g["date"].iloc[0], "to": g["date"].iloc[-1], "n": len(g), "has_earn": bf.get("has_earn"),
            "ic": g["o_ic20"].mean(), "ex20": ex.mean(), "beat": (ex > 0).mean(), "grades": grades, "parts": parts,
            "verified_days": int(len(va)), "verified_ex20": float((va["top20"] - va["all20"]).mean()) if len(va) else None,
            "years": yrs, "curve": [[d, a, b] for d, a, b in zip(nonover["date"], cum[0], cum[1])], "note": bf.get("note"),
            "factor_ic": {f: {"ic20": nmean([r["ic"].get(f) for r in bf["records"]]),
                              "ic5": nmean([r.get("ic5", {}).get(f) for r in bf["records"]])}
                          for f in L.FACTORS if any(f in r["ic"] for r in bf["records"])},
        }
    for h in L.HORIZONS:
        R = [r for r in live if r["h"] == h]
        if not R:
            rep["live"][str(h)] = {"n": 0}
            continue
        RO = [r for r in R if "o_top" in r]
        ex = [r["o_top"] - r["all"] for r in RO]
        RV = [r for r in R if r.get("active")]
        rep["live"][str(h)] = {"n": len(RO), "n_eff": round(len(RO) / h, 1), "ic": nmean([r["o_ic"] for r in RO]),
                               "ex": nmean(ex), "beat": nmean([float(e > 0) for e in ex]),
                               "verified_n": len(RV), "verified_ex": nmean([r["top"] - r["all"] for r in RV]),
                               "recent": [{"date": r["date"], "top": r["o_top"], "all": r["all"], "best": r.get("o_best")} for r in RO[-30:]]}
    n20 = rep["live"].get("20", {}).get("n", 0)
    rep["stage"] = ("쌓는 중" if n20 < 20 else "초기" if n20 < 120 else "참고 가능" if n20 < 250 else "1년 이상 검증")
    return rep


def main(force=False):
    t0 = time.time()
    U = universe()
    codes = list(U["Code"])
    names = dict(zip(U.Code, U.Name)); mkts = dict(zip(U.Code, U.Market))
    start = (NOW - timedelta(days=760)).strftime("%Y-%m-%d")
    import FinanceDataReader as fdr
    ks = fdr.DataReader("KS200", start)["Close"]
    cal = [d.strftime("%Y-%m-%d") for d in ks.index]
    last = cal[-1]
    if (SNAP / f"{last}.json").exists() and last != NOW.strftime("%Y-%m-%d") and not force:
        print("오늘은 장이 열리지 않았어요 (마지막 거래일", last, "기록 있음)")
        return
    # 지난 기록에 있었지만 지금 300위 밖인 종목도 채점하려면 가격이 필요
    old = set()
    for p in sorted(SNAP.glob("*.json"))[-30:]:
        old |= set(json.loads(p.read_text())["stocks"].keys())
    P = fetch_prices(sorted(set(codes) | old), start)
    print(f"시세 {sum(1 for v in P.values() if v)}종목 {time.time() - t0:.0f}s", flush=True)
    C, H, V = L.wide(P, cal)
    tnx, krw = fetch_macro()
    F = L.price_factors(C, H, V, L.macro_aligned(tnx, C.index), L.macro_aligned(krw, C.index))
    d = C.index[-1]
    cols = [c for c in codes if c in C.columns and pd.notna(C.loc[d, c])]
    raw = {f: F[f].loc[d, cols] for f in L.PRICE_FACTORS}

    with ThreadPoolExecutor(8) as ex:
        news = dict(zip(cols, ex.map(lambda c: fetch_news(c, names.get(c, "")), cols)))
    ok_news = sum(1 for v in news.values() if v is not None)
    raw["news"] = pd.Series({c: (news[c]["tone"] if news[c] and news[c]["n"] else np.nan) for c in cols}, dtype=float)
    print(f"뉴스 {ok_news}종목 {time.time() - t0:.0f}s", flush=True)

    earn, earn_msg = earnings_now(cols)
    raw["earn"] = pd.Series({c: D.earn_raw(earn.get(c)) if earn else np.nan for c in cols}, dtype=float)
    print(earn_msg, flush=True)

    # 채점 → 가중치
    live = json.loads((OUT / "live.json").read_text()) if (OUT / "live.json").exists() else []
    added = grade(C, live)
    bf = json.loads((OUT / "backfill.json").read_text()) if (OUT / "backfill.json").exists() else None
    recs = (bf["records"] if bf else []) + [r for r in live if r["h"] == 20]
    W = L.learn_weights(recs, asof=d)

    Z = {f: L.xrank(raw[f]) for f in L.FACTORS}
    score = L.combine(Z, W)
    pct = score.rank(pct=True) * 100
    order = score.sort_values(ascending=False).index

    OI = L.ours_inputs(C, H, V)
    O = L.our_score(**{k: v.loc[d, cols] for k, v in OI.items()}, earn=raw["earn"] if earn else None, news=raw["news"])
    O["grade"] = O["total"].map(L.grade_of)
    verified = any(v["weight"] for v in W.values())
    order = O["total"].sort_values(ascending=False, kind="stable").index

    day = d.strftime("%Y-%m-%d")
    dump(SNAP / f"{day}.json", {"date": day, "weights": {f: v["weight"] for f, v in W.items()},
                                "stocks": {c: {"c": float(C.loc[d, c]), "s": float(score[c]), "o": float(O.loc[c, "total"]), "n": names.get(c, c),
                                               "raw": {f: (None if pd.isna(raw[f].get(c)) else float(raw[f][c])) for f in L.FACTORS}}
                                           for c in cols}})
    dump(OUT / "live.json", live)

    # 시장 분위기 (순위와 별개로 '지금 날씨' 표시)
    ks_c = ks.iloc[-1]; ks200ma = ks.rolling(200).mean().iloc[-1]
    m60 = C.rolling(60).mean().iloc[-1]
    breadth = float((C.iloc[-1][cols] > m60[cols]).mean())
    market = {"ks200": float(ks_c), "ks_vs200": float(ks_c / ks200ma - 1), "ks_20d": float(ks_c / ks.iloc[-21] - 1),
              "tnx": float(tnx.iloc[-1]), "tnx_20d_bp": float((tnx.iloc[-1] - tnx.iloc[-21]) * 100),
              "krw": float(krw.iloc[-1]), "krw_20d": float(krw.iloc[-1] / krw.iloc[-21] - 1), "breadth60": breadth}
    up = (market["ks_vs200"] > 0) + (market["ks_20d"] > 0) + (breadth > 0.5)
    market["mood"] = ["약세장 — 순위가 높아도 전체가 빠질 수 있어요", "혼조", "보통", "강세장"][up]

    rows = []
    prev = C.iloc[-2]
    for rank, c in enumerate(order, 1):
        e = earn.get(c) if earn else None
        rows.append({
            "rank": rank, "code": c, "name": names.get(c, c), "mkt": mkts.get(c), "close": float(C.loc[d, c]),
            "chg": float(C.loc[d, c] / prev[c] - 1) if pd.notna(prev[c]) else None,
            "ours": float(O.loc[c, "total"]), "grade": O.loc[c, "grade"], "parts": {k: float(O.loc[c, k]) for k in L.OURS},
            "spark": [float(x) for x in C[c].iloc[-60:].ffill().tolist()],
            "score": float(pct[c]) if verified else None, "z": {f: float(Z[f][c]) for f in L.FACTORS},
            "v": {"mom": raw["mom"].get(c), "hi52": raw["hi52"].get(c), "trend": raw["trend"].get(c), "volx": raw["volx"].get(c),
                  "rev": raw["rev"].get(c), "lowvol": raw["lowvol"].get(c), "rate": raw["rate"].get(c), "fx": raw["fx"].get(c),
                  "news": raw["news"].get(c), "earn": raw["earn"].get(c)},
            "news": (news[c]["items"][:3] if rank <= 60 and news.get(c) else None), "news_n": news[c]["n"] if news.get(c) else None,
            "earn": ({"rep": f"{e['year']} {D.REPRT[e['reprt']]}", "date": e["rcept_date"], "op": e.get("op"), "op_prev": e.get("op_prev"),
                      "rev": e.get("rev"), "rev_prev": e.get("rev_prev")} if e else None),
        })
    dump(OUT / "latest.json", {"date": day, "made": NOW.strftime("%Y-%m-%d %H:%M"), "market": market, "weights": W, "verified": verified,
                               "ours_def": {k: {"name": n, "max": m, "desc": ds} for k, (n, m, ds) in L.OURS.items()},
                               "t_min": L.T_MIN, "sources": {"news": ok_news, "earn": earn_msg, "universe": len(cols)}, "rows": rows})
    dump(OUT / "report.json", summarize(bf, live))
    # 종목 클릭 시 바로 보는 차트용: 최근 130거래일 일봉
    days = cal[-130:]
    bars = {}
    for c in cols:
        m = {r[0]: r for r in P.get(c, [])}
        bars[c] = [([int(round(x)) for x in m[t][1:6]] if t in m else 0) for t in days]
    (OUT / "bars.json").write_text(json.dumps({"days": days, "bars": bars}, separators=(",", ":")))
    print(f"완료 {day} · 채점 추가 {added} · {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
