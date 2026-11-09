"""
미국장 마감 후 매일 실행 — 시장 개요 · 순위(테마 눌림) · 장기 테마 · 추천 기업 · 채점/추적
출력 data/us/
  market.json      지수·자산·섹터·많이 오른/내린 종목·시장 폭 (홈 화면)
  rank.json        오늘 순위 / rank_report.json 채점·추적 / rank_snap/날짜.json 기록 / rank_live.json
  bars.json        최근 130일 일봉 (종목 눌렀을 때 바로 차트)
  theme.json       장기 테마·근거·추천 기업·여론·예측시장 / theme_history.json 테마 지수 / theme_snap/날짜.json
실행: python scripts/us_daily.py [--force]
"""
import json, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rank_lib as L
import plan_lib as PLN
import sentiment as SE
import us_prices as UP
from us_narr_def import NARR, EXTRA_KO
from narrative_def import POLICY_WORDS

PLN.set_us()
OUT = ROOT / "data/us"
SNAP = OUT / "rank_snap"; TSNAP = OUT / "theme_snap"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
CAP = 5
ASSETS = [("^GSPC", "S&P500"), ("^IXIC", "나스닥"), ("^DJI", "다우"), ("^RUT", "러셀2000"), ("^VIX", "VIX 공포지수"), ("^TNX", "미 10년 금리"),
          ("DX-Y.NYB", "달러인덱스"), ("KRW=X", "원/달러"), ("CL=F", "WTI 유가"), ("GC=F", "금"), ("BTC-USD", "비트코인")]
SECTORS = [("XLK", "기술"), ("SOXX", "반도체"), ("XLC", "커뮤니케이션"), ("XLY", "경기소비재"), ("XLP", "필수소비재"), ("XLE", "에너지"),
           ("XLF", "금융"), ("XLV", "헬스케어"), ("XLI", "산업재"), ("XLB", "소재"), ("XLRE", "부동산"), ("XLU", "유틸리티")]
VARIANTS = {"td": "추천 바구니 (테마당 5개)", "t": "테마 눌림", "m": "12-1 모멘텀", "o": "우리 점수"}
GRADE_H = (1, 5, 20)
# 예측시장에서 회사 이름으로 찾을 때 (이름이 확실한 회사만 — 엉뚱한 시장이 붙지 않게)
COMPANY_PM = {"NVDA": "Nvidia", "TSLA": "Tesla", "AAPL": "Apple", "MSFT": "Microsoft", "AMZN": "Amazon", "GOOGL": "Google", "META": "Meta",
              "PLTR": "Palantir", "COIN": "Coinbase", "MSTR": "MicroStrategy", "AMD": "AMD", "INTC": "Intel", "BA": "Boeing", "NFLX": "Netflix",
              "LLY": "Eli Lilly", "NVO": "Novo Nordisk", "HOOD": "Robinhood", "ORCL": "Oracle", "AVGO": "Broadcom", "TSM": "TSMC",
              "IONQ": "IonQ", "RKLB": "Rocket Lab", "OKLO": "Oklo", "UBER": "Uber", "JPM": "JPMorgan", "DIS": "Disney"}


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        o = float(o)
        return None if not np.isfinite(o) else round(o, 5)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def dump(p, o):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(o), ensure_ascii=False, separators=(",", ":")))


def chg(s, n):
    s = s.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


# ---------------- 시장 개요 ----------------
def market(P, C, uni, names, ko):
    def series(t):
        rows = P.get(t) or []
        return pd.Series({r[0]: r[4] for r in rows}, dtype=float).sort_index()
    out = {"date": None, "assets": [], "sectors": [], "up": [], "down": []}
    for t, nm in ASSETS:
        s = series(t)
        if s.empty:
            continue
        ytd = s[s.index >= f"{s.index[-1][:4]}-01-01"]
        out["assets"].append({"t": t, "name": nm, "last": s.iloc[-1], "d1": chg(s, 1), "m1": chg(s, 21),
                              "ytd": float(s.iloc[-1] / ytd.iloc[0] - 1) if len(ytd) > 1 else None, "spark": s.iloc[-60:].round(4).tolist(), "date": s.index[-1]})
    for t, nm in SECTORS:
        s = series(t)
        if not s.empty:
            out["sectors"].append({"t": t, "name": nm, "d1": chg(s, 1), "w1": chg(s, 5), "m1": chg(s, 21), "m3": chg(s, 63)})
    d1 = (C.iloc[-1] / C.iloc[-2] - 1)[uni].dropna().sort_values()
    mk = lambda t: {"t": t, "name": names.get(t), "ko": ko.get(t), "d1": float(d1[t]), "px": float(C[t].iloc[-1])}
    out["up"] = [mk(t) for t in d1.index[::-1][:10]]
    out["down"] = [mk(t) for t in d1.index[:10]]
    cu = C[uni]
    out["breadth"] = {"above50": float((cu.iloc[-1] > cu.rolling(50).mean().iloc[-1]).mean()),
                      "above200": float((cu.iloc[-1] > cu.rolling(200).mean().iloc[-1]).mean()),
                      "hi52": int((cu.iloc[-1] >= cu.rolling(250, min_periods=200).max().iloc[-1] * 0.999).sum()),
                      "lo52": int((cu.iloc[-1] <= cu.rolling(250, min_periods=200).min().iloc[-1] * 1.001).sum()),
                      "adv": int((d1 > 0).sum()), "dec": int((d1 < 0).sum())}
    sp = series("^GSPC")
    out["regime"] = {"sp_vs200": float(sp.iloc[-1] / sp.rolling(200).mean().iloc[-1] - 1), "up": bool(sp.iloc[-1] > sp.rolling(200).mean().iloc[-1])}
    out["date"] = C.index[-1].strftime("%Y-%m-%d")
    return out


# ---------------- 채점·추적 ----------------
def top20(S, codes, k):
    key = "t" if k == "td" else k
    sc = pd.Series({c: S["stocks"][c].get(key) for c in codes}, dtype=float)
    if sc.notna().sum() < 50:
        return None, None
    order = sc.sort_values(ascending=False, kind="stable").index
    if k != "td":
        return list(order[:20]), sc
    out, cnt = [], {}
    for c in order:
        th = S["stocks"][c].get("k") or "-"
        if th != "-" and cnt.get(th, 0) >= CAP:
            continue
        out.append(c); cnt[th] = cnt.get(th, 0) + 1
        if len(out) == 20:
            break
    return out, sc


def grade(C, Op, live):
    live[:] = [r for r in live if r.get("all") is not None and r.get("var")]     # 시세가 비어 잘못 채점된 기록은 다시
    done = {(r["date"], r["h"]) for r in live}
    pos = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(C.index)}
    for p in sorted(SNAP.glob("*.json")):
        day = p.stem
        if day not in pos:
            continue
        i = pos[day]; S = None
        for h in GRADE_H:
            if (day, h) in done or i + h >= len(C.index):
                continue
            S = S or json.loads(p.read_text())
            codes = [c for c in S["stocks"] if c in C.columns and pd.notna(Op.iloc[i + 1].get(c)) and pd.notna(C.iloc[i + h].get(c))]
            if len(codes) < 100:
                continue
            fr = C.iloc[i + h][codes] / Op.iloc[i + 1][codes] - 1
            rec = {"date": day, "h": h, "all": float(fr.mean()), "var": {}}
            for k in VARIANTS:
                top, sc = top20(S, codes, k)
                if top:
                    rec["var"][k] = {"top": float(fr[top].mean()), "ic": L.spearman(sc, fr), "best": [[c, float(fr[c])] for c in top[:5]]}
            live.append(rec)


def track(C, Op):
    pos = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(C.index)}
    out = []
    for p in sorted(SNAP.glob("*.json"))[-60:]:
        day = p.stem
        if day not in pos or pos[day] + 1 >= len(C.index):
            continue
        i = pos[day]; S = json.loads(p.read_text())
        codes = [c for c in S["stocks"] if c in C.columns and pd.notna(Op.iloc[i + 1].get(c))]
        fr = C.iloc[-1][codes] / Op.iloc[i + 1][codes] - 1
        row = {"date": day, "days": len(C.index) - 1 - i, "all": float(fr.mean())}
        for k in VARIANTS:
            top, _ = top20(S, codes, k)
            if top:
                row[k] = float(fr[top].mean())
                row[k + "_best"] = [[c, float(fr[c])] for c in fr[top].sort_values(ascending=False).index[:3]]
        out.append(row)
    return out


def summarize(live):
    rep = {"variants": {}}
    for h in GRADE_H:
        R = [r for r in live if r["h"] == h]
        for k, nm in VARIANTS.items():
            ex = [r["var"][k]["top"] - r["all"] for r in R if k in r["var"]]
            if ex:
                a = np.array(ex); n_eff = max(1.0, len(a) / h)
                rep["variants"].setdefault(k, {"name": nm})[str(h)] = {"n": len(a), "ex": float(a.mean()), "beat": float((a > 0).mean()),
                                                                     "t": float(a.mean() / a.std() * np.sqrt(n_eff)) if len(a) > 2 and a.std() > 0 else None}
    # 승격 규칙: 지금 기본(td=추천 바구니)보다 20일 성적이 같은 날끼리 비교해 꾸준히 좋으면(20일 채점 40번 이상, t≥2) 기본을 바꿈
    R20 = [r for r in live if r["h"] == 20 and "td" in r["var"]]
    leader, why = "td", f"20일 채점 {len(R20)}번 — 40번 쌓이기 전엔 기본(추천 바구니) 유지"
    if len(R20) >= 40:
        best = None
        for k in VARIANTS:
            if k == "td":
                continue
            d = np.array([r["var"][k]["top"] - r["var"]["td"]["top"] for r in R20 if k in r["var"]])
            if len(d) >= 40 and d.std() > 0:
                t = d.mean() / d.std() * np.sqrt(len(d) / 20)
                if t >= 2 and (best is None or t > best[1]):
                    best = (k, t, d.mean())
        if best:
            leader, why = best[0], f"{VARIANTS[best[0]]}가 추천 바구니보다 20일 평균 {best[2]*100:+.2f}%p (t {best[1]:.1f}, {len(R20)}번) → 기본으로 승격"
        else:
            why = f"20일 채점 {len(R20)}번 — 추천 바구니를 확실히 이긴 방식 없음 (t≥2 기준)"
    rep["leader"], rep["leader_why"] = leader, why
    vb = OUT / "variants_backfill.json"
    rep["variants_backfill"] = json.loads(vb.read_text()) if vb.exists() else None
    return rep


# ---------------- 테마 ----------------
def gnews(q, days=3):
    import news_build as NBD
    x = NBD.get("https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f"{q} when:{days}d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"}), raw=True)
    return NBD.rss_items(x)


def yahoo_many(tickers):
    cache_p = OUT / "yahoo_cache.json"
    cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
    today = NOW.strftime("%Y-%m-%d")
    need = [t for t in tickers if cache.get(t, {}).get("_d") != today]
    def one(t):
        y = SE.yahoo(t); time.sleep(0.3)
        return t, y
    with ThreadPoolExecutor(3) as ex:
        for t, y in ex.map(one, need):
            if y is not None:
                y["_d"] = today; cache[t] = y
    dump(cache_p, cache)
    return cache


def themes(P, C, ks, names, ko, mkt_up, day):
    tick_all = sorted({t for n in NARR for t in n["tickers"] if t in C.columns})
    yh = yahoo_many(tick_all)
    m50 = C.rolling(50).mean().iloc[-1]
    rows, picks_all = [], {}
    import news_build as NBD
    for n in NARR:
        mem = [t for t in n["tickers"] if t in C.columns and C[t].notna().sum() > 130]
        r = C[mem].pct_change(fill_method=None).clip(-0.3, 0.3).mean(axis=1).fillna(0)
        idx = (1 + r).cumprod()
        rel = lambda w: float(np.log(idx.iloc[-1] / idx.iloc[-1 - w]) - np.log(ks.iloc[-1] / ks.iloc[-1 - w])) if len(idx) > w else np.nan
        r1, r3, r6, r12 = rel(21), rel(63), rel(126), rel(250)
        heads = gnews(" OR ".join(n["ko"][:5]))
        seen, hs = set(), []
        for h in heads:
            if h["t"] not in seen:
                seen.add(h["t"]); hs.append({"t": h["t"], "u": h["u"], "at": h["at"], "pol": any(w in h["t"] for w in POLICY_WORDS)})
        ups = [yh[t]["target"] / C[t].iloc[-1] - 1 for t in mem if (yh.get(t) or {}).get("target") and C[t].iloc[-1] > 0]
        ups = [u for u in ups if -0.6 < u < 2]
        recs = [{"strong_buy": 1, "buy": 0.75, "hold": 0.5, "underperform": 0.25, "sell": 0}.get((yh.get(t) or {}).get("rec")) for t in mem]
        recs = [x for x in recs if x is not None]
        above = [bool(C[t].iloc[-1] > m50[t]) for t in mem if pd.notna(m50.get(t))]
        rows.append({"key": n["key"], "name": n["name"], "story": n["story"], "n": len(mem), "r1": r1, "r3": r3, "r6": r6, "r12": r12,
                     "sig": {"trend": np.nanmean([r3, r6]), "breadth": np.mean(above) if above else np.nan, "buzz": len(hs),
                             "policy": sum(h["pol"] for h in hs), "target": np.median(ups) if len(ups) >= 2 else np.nan, "opinion": np.mean(recs) if recs else np.nan},
                     "ev_raw": {"above": (sum(above), len(above)), "ups": (float(np.median(ups)) if ups else None, len(ups)), "news": len(hs)},
                     "heads": sorted(hs, key=lambda x: x["at"], reverse=True)[:8], "mem": mem, "idx": idx})
    PARTS = {"trend": ("주가 추세", 30), "breadth": ("확산", 20), "buzz": ("관심(기사)", 15), "policy": ("정책 뉴스", 15), "target": ("목표가 여력", 10), "opinion": ("애널리스트 의견", 10)}
    for p in PARTS:
        s = pd.Series({r["key"]: r["sig"][p] for r in rows}, dtype=float).rank(pct=True)
        for r in rows:
            r.setdefault("parts", {})[p] = (float(s[r["key"]]) if pd.notna(s[r["key"]]) else 0.5) * PARTS[p][1]
    for r in rows:
        r["score"] = sum(r["parts"].values())
        r["status"] = ("강해지는 중" if r["r1"] > 0 and r["r3"] > 0 else "숨 고르기" if r["r3"] > 0 else "바닥에서 반등" if r["r1"] > 0 else "약함")
        e = r["ev_raw"]
        r["evidence"] = [f"테마 종목 평균이 S&P500보다 3개월 {r['r3']*100:+.1f}%p, 6개월 {r['r6']*100:+.1f}%p",
                         f"{e['above'][1]}종목 중 {e['above'][0]}개가 50일선 위"]
        if e["ups"][0] is not None:
            r["evidence"].append(f"애널리스트 목표가가 현재가보다 평균 {e['ups'][0]*100:+.0f}% ({e['ups'][1]}종목, Yahoo 집계)")
        r["evidence"].append(f"최근 3일 국내 관련 기사 {e['news']}건, 그중 정책 관련 {sum(h['pol'] for h in r['heads'])}건")
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["stocks"] = [{"code": t, "name": names.get(t) or (yh.get(t) or {}).get("name") or t, "ko": ko.get(t), "close": float(C[t].iloc[-1]),
                        "r3": float(C[t].iloc[-1] / C[t].iloc[-64] - 1) if C[t].iloc[-64] > 0 else None,
                        "up": ((yh.get(t) or {}).get("target") / C[t].iloc[-1] - 1) if (yh.get(t) or {}).get("target") else None,
                        "rec": (yh.get(t) or {}).get("rec"), "n": (yh.get(t) or {}).get("n")} for t in r["mem"]]
    # ---- 추천 기업 ----
    pm_cache = {}
    def pm(q, must, minv=20000):
        if q not in pm_cache:
            pm_cache[q] = SE.polymarket(q, minv, 6)
        return [e for e in pm_cache[q] if any(m in (e["title"] or "") for m in must)]
    sel = {}
    for r in rows:
        n = next(x for x in NARR if x["key"] == r["key"])
        sc = []
        for t in r["mem"]:
            b = (P.get(t) or [])[-130:]
            if len(b) < 130:
                continue
            val = np.mean([x[4] * x[5] for x in b[-20:]])
            if val < 2e7:                      # 하루 거래대금 2천만 달러 미만 제외
                continue
            pl = PLN.analyze(b, mkt_up)
            if not pl:
                continue
            px = b[-1][4]; d0 = pd.Timestamp(b[-64][0]); k0 = ks.asof(d0)
            rs3 = (px / b[-64][4]) / (ks.iloc[-1] / k0) - 1
            y = yh.get(t) or {}
            up = y["target"] / px - 1 if y.get("target") else None
            v5, v60 = np.mean([x[5] for x in b[-5:]]), np.mean([x[5] for x in b[-60:]])
            sc.append({"t": t, "px": px, "pl": pl, "rs3": rs3, "up": up, "y": y, "val": val, "volr": v5 / v60 if v60 else 1, "r5": px / b[-6][4] - 1})
        if not sc:
            r["picks"] = []; continue
        rk = lambda key: pd.Series({x["t"]: x[key] if x[key] is not None else np.nan for x in sc}, dtype=float).rank(pct=True)
        rr, ur, nr = rk("rs3"), rk("up"), pd.Series({x["t"]: (x["y"].get("n") or 0) for x in sc}, dtype=float).rank(pct=True)
        for x in sc:
            pl = x["pl"]
            s = ((30 if pl["kind"] == "pullback" else 12) if pl["ok"] else 0) + (8 if pl["ok"] and pl["in_zone"] else 0)
            s += 20 * (rr.get(x["t"]) if pd.notna(rr.get(x["t"])) else 0.5) + 15 * (ur.get(x["t"]) if pd.notna(ur.get(x["t"])) else 0.4)
            s += 3 if x["y"].get("rec") in ("strong_buy", "buy") else 0
            s += 10 * (nr.get(x["t"]) if pd.notna(nr.get(x["t"])) else 0.3)
            s += 7 if x["volr"] >= 1.2 and x["r5"] > 0 else 3 if x["volr"] >= 1.0 else 0
            x["score"] = s
        top = sorted(sc, key=lambda x: -x["score"])[:5]
        picks_all[r["key"]] = [{"code": x["t"], "entry": x["pl"]["entry"], "stop": x["pl"]["stop"], "target": x["pl"]["target"], "kind": x["pl"]["kind"], "ok": x["pl"]["ok"]} for x in top]
        r["picks"] = []
        for x in top:
            pl, y = x["pl"], x["y"]; t = x["t"]
            why = [f"테마: {n['name']} 대표 종목", f"주가: 최근 3개월 S&P500 대비 {x['rs3']*100:+.1f}%p, " + ("상승 추세(종가>60일선, 20일선>60일선)" if pl["trend_ok"] else "아직 추세 전환 전")]
            if y.get("n"):
                why.append(f"애널리스트 {y['n']}명 · 목표가 평균 ${y['target']:,.2f} (현재가 대비 {x['up']*100:+.0f}%) · {y.get('rec') or '—'}")
            why.append(f"거래: 하루 평균 ${x['val']/1e6:,.0f}M · 최근 5일 거래량 평소의 {x['volr']:.1f}배")
            sel[t] = True
            r["picks"].append({"code": t, "sym": t, "name": names.get(t) or y.get("name") or t, "ko": ko.get(t), "px": x["px"], "score": x["score"], "plan": pl,
                               "why": why, "yahoo": y, "consensus": {"target": y.get("target"), "up": x["up"], "rec": y.get("rec"), "n": y.get("n")}})
        ev, seen = [], set()
        for q, must in n["pm"]:
            for e in pm(q, must):
                if e["title"] not in seen:
                    seen.add(e["title"]); ev.append(e)
        r["markets"] = sorted(ev, key=lambda e: -e["vol"])[:3]
    with ThreadPoolExecutor(4) as ex:
        st = dict(zip(sel, ex.map(SE.stocktwits, list(sel))))
    for r in rows:
        for p in r.get("picks", []):
            p["community"] = st.get(p["code"])
            en = COMPANY_PM.get(p["code"])
            p["markets"] = pm(en, [en], 10000)[:2] if en else []
    macro = SE.kalshi_macro()
    for q, must in [("Fed rate cuts 2026", ["Fed"]), ("US recession 2026", ["recession", "Recession"])]:
        macro += pm(q, must, 100000)[:1]
    return rows, picks_all, macro


def theme_history(rows, C):
    hp = OUT / "theme_history.json"
    Hh = json.loads(hp.read_text()) if hp.exists() else {"dates": [], "ks": [], "idx": {}}
    return Hh


def pick_record(Hh_sp):
    pr = OUT / "pick_prices.json"
    if not pr.exists():
        return None
    PX = json.loads(pr.read_text())
    up = (Hh_sp > Hh_sp.rolling(200).mean()).to_dict()
    def run(filt):
        sig = []
        for p in sorted(TSNAP.glob("*.json")):
            S = json.loads(p.read_text())
            if filt and not up.get(S["date"], True):
                continue
            for k, v in (S.get("picks") or {}).items():
                for x in v:
                    if x.get("ok"):
                        sig.append((S["date"], k, x))
        busy, res, seen = {}, [], set()
        for date, k, x in sorted(sig, key=lambda z: z[0]):
            c = x["code"]
            if (date, c) in seen or (busy.get(c) and busy[c] >= date):
                continue
            seen.add((date, c))
            b = [r for r in PX.get(c, []) if r[0] > date]
            fill = None
            for j, r in enumerate(b[:5]):
                o, h, l = r[1], r[2], r[3]
                if x["kind"] == "pullback" and l <= x["entry"]:
                    if o <= x["stop"]: break
                    fill = (j, min(o, x["entry"])); break
                if x["kind"] == "breakout" and h >= x["entry"]:
                    if o >= x["target"]: break
                    fill = (j, max(o, x["entry"])); break
            if not fill:
                continue
            j0, e = fill; out, exd = None, None
            for r in b[j0:j0 + 60]:
                if r[3] <= x["stop"]: out = ("손절", min(r[1], x["stop"]) / e - 1 if r[0] != b[j0][0] else x["stop"] / e - 1); exd = r[0]; break
                if r[2] >= x["target"]: out = ("목표", x["target"] / e - 1); exd = r[0]; break
            last = b[min(len(b), j0 + 60) - 1]
            res.append({"date": date, "theme": k, "code": c, "res": out[0] if out else "보유 중", "ret": out[1] if out else last[4] / e - 1})
            busy[c] = exd or "9999"
        done = [r for r in res if r["res"] != "보유 중"]; op = [r["ret"] for r in res if r["res"] == "보유 중"]
        return {"n": len(res), "done": len(done), "win": sum(r["res"] == "목표" for r in done), "avg": float(np.mean([r["ret"] for r in done])) if done else None,
                "open": len(op), "open_avg": float(np.mean(op)) if op else None, "recent": res[-20:]}
    a = run(True); b = run(False)
    a["nofilter"] = {k: b[k] for k in ("n", "done", "win", "avg", "open", "open_avg")}
    return a


# ---------------- 메인 ----------------
def main(force=False):
    t0 = time.time()
    try:
        import us_universe
        if not (OUT / "universe.json").exists() or (pd.Timestamp.today() - pd.Timestamp(json.loads((OUT / "universe.json").read_text())["made"])).days >= 7:
            us_universe.main()
    except Exception as e:
        print("종목 목록 갱신 실패:", e)
    U = json.loads((OUT / "universe.json").read_text())
    uni_all = [s["t"] for s in U["stocks"]]
    names = {s["t"]: s["name"] for s in U["stocks"]}
    sector = {s["t"]: s["sector"] for s in U["stocks"]}
    ko = {**U.get("ko", {}), **EXTRA_KO}
    extras = sorted({t for n in NARR for t in n["tickers"]} - set(uni_all))
    old = set()
    for p in sorted(SNAP.glob("*.json"))[-30:]:
        old |= set(json.loads(p.read_text())["stocks"])
    for p in sorted(TSNAP.glob("*.json"))[-130:]:
        for v in (json.loads(p.read_text()).get("picks") or {}).values():
            old |= {x["code"] for x in v}
    tick = sorted(set(uni_all) | set(extras) | old) + [a for a, _ in ASSETS] + [s for s, _ in SECTORS]
    P = UP.download(tick, period="2y")
    print(f"시세 {len(P)}종목 {time.time() - t0:.0f}s", flush=True)
    sp = P["^GSPC"]; cal = [r[0] for r in sp]
    # 장 마감 직후엔 종목 시세가 아직 안 들어온 경우가 있음 → 90% 이상 들어온 날까지만 씀 (안 그러면 전날 가격으로 순위·채점이 됨)
    while cal:
        have = sum(1 for t in uni_all if P.get(t) and P[t][-1][0] >= cal[-1])
        if have >= 0.9 * len(uni_all):
            break
        print(f"{cal[-1]} 시세가 {have}/{len(uni_all)}종목만 들어옴 → 그 전날까지만 사용", flush=True)
        drop = cal.pop()
        P = {t: [r for r in v if r[0] < drop] for t, v in P.items()}
    sp = P["^GSPC"]
    last = cal[-1]
    if (SNAP / f"{last}.json").exists() and not force:
        print("이미 계산한 거래일:", last); return
    stocks = {t: P[t] for t in P if not t.startswith("^") and "=" not in t and t not in dict(SECTORS) and t not in ("DX-Y.NYB", "BTC-USD")}
    C, H, V = L.wide(stocks, cal); Op = L.opens(stocks, cal)
    ks = pd.Series({r[0]: r[4] for r in sp}); ks.index = pd.to_datetime(ks.index); ks = ks.reindex(C.index).ffill()
    d = C.index[-1]; day = d.strftime("%Y-%m-%d")
    uni = [t for t in uni_all if t in C.columns and pd.notna(C.loc[d, t])]
    mk = market(P, C, uni, names, ko)
    dump(OUT / "market.json", mk)
    mkt_up = mk["regime"]["up"]

    # 테마 추세 → 테마 눌림 점수
    prim = {}
    for n in NARR:
        for t in n["tickers"]:
            prim.setdefault(t, n["key"])
    tr = {}
    for n in NARR:
        mem = [t for t in n["tickers"] if t in C.columns]
        r = C[mem].pct_change(fill_method=None).clip(-0.3, 0.3).mean(axis=1).fillna(0); idx = (1 + r).cumprod()
        tr[n["key"]] = float(np.nanmean([np.log(idx.iloc[-1] / idx.iloc[-1 - w]) - np.log(ks.iloc[-1] / ks.iloc[-1 - w]) for w in (63, 126)]))
    tpct = pd.Series(tr).rank(pct=True).to_dict()
    TP, TH = L.theme_pullback(C, d, uni, tpct, prim)
    OI = L.ours_inputs(C, H, V)
    O = L.our_score(**{k: v.loc[d, uni] for k, v in OI.items()}); O["grade"] = O["total"].map(L.grade_of)
    i = C.index.get_loc(d)
    MOM = C.loc[d, uni] / C.iloc[i - 252][uni] if i >= 252 else C.loc[d, uni] * np.nan
    MOM = C.iloc[i - 21][uni] / C.iloc[i - 252][uni] - 1 if i >= 252 else MOM
    order = TP.sort_values(ascending=False, kind="stable").index
    basket, cnt = [], {}
    for c in order:
        k = prim.get(c) or "-"
        if k != "-" and cnt.get(k, 0) >= CAP:
            continue
        basket.append(c); cnt[k] = cnt.get(k, 0) + 1
        if len(basket) == 20:
            break
    bset = set(basket); tp_pct = TP.rank(pct=True) * 100; mom_pct = MOM.rank(pct=True) * 100
    tnames = {n["key"]: n["name"] for n in NARR}
    try:                                              # 터틀 신호 (같은 시세로)
        import us_turtle
        us_turtle.build(P, uni, names, ko, mk["regime"], prim, tnames)
    except Exception as e:
        print("터틀 신호 실패:", e)
    rows = []
    for c in order:
        rows.append({"code": c, "name": names.get(c), "ko": ko.get(c), "sector": sector.get(c), "close": float(C.loc[d, c]),
                     "chg": float(C.loc[d, c] / C.iloc[-2][c] - 1) if pd.notna(C.iloc[-2][c]) else None,
                     "tp": float(tp_pct[c]), "mom": float(mom_pct[c]) if pd.notna(mom_pct.get(c)) else None, "theme": prim.get(c), "theme_pct": tpct.get(prim.get(c)),
                     "basket": c in bset, "rev5": float(C.loc[d, c] / C.iloc[-6][c] - 1), "ours": float(O.loc[c, "total"]), "grade": O.loc[c, "grade"],
                     "parts": {k: float(O.loc[c, k]) for k in ("trend", "flow", "safe")}, "spark": [float(x) for x in C[c].iloc[-60:].ffill().tolist()]})
    dump(SNAP / f"{day}.json", {"date": day, "made": NOW.strftime("%Y-%m-%d %H:%M"),
                                "stocks": {c: {"c": float(C.loc[d, c]), "t": float(TP[c]), "th": float(TH[c]), "m": (float(MOM[c]) if pd.notna(MOM.get(c)) else None),
                                               "o": float(O.loc[c, "total"]), "k": prim.get(c), "n": names.get(c)} for c in uni}})
    live = json.loads((OUT / "rank_live.json").read_text()) if (OUT / "rank_live.json").exists() else []
    grade(C, Op, live); dump(OUT / "rank_live.json", live)
    rep = summarize(live); rep["track"] = track(C, Op)
    dump(OUT / "rank_report.json", rep)
    dump(OUT / "rank.json", {"date": day, "made": NOW.strftime("%Y-%m-%d %H:%M"), "regime": mk["regime"], "themes": tnames, "rows": rows,
                              "leader": rep.get("leader", "td"), "leader_why": rep.get("leader_why", ""),
                              "ours_def": {k: {"name": nm, "max": mx, "desc": ds} for k, (nm, mx, ds) in L.OURS.items() if k in ("trend", "flow", "safe")}})
    days = cal[-130:]
    allb = {t: P[t] for t in set(uni) | set(extras) if t in P}
    dump(OUT / "bars.json", {"days": days, "bars": {t: [([round(x, 4) for x in m[t2][1:5]] + [m[t2][5]] if t2 in m else 0) for t2 in days]
                                                    for t, m in ((t, {r[0]: r for r in v}) for t, v in allb.items())}})
    print(f"순위 {len(rows)} · {time.time() - t0:.0f}s", flush=True)

    # 테마 + 추천
    trows, picks_all, macro = themes(P, C, ks, names, ko, mkt_up, day)
    hp = OUT / "theme_history.json"
    Hh = json.loads(hp.read_text()) if hp.exists() else {"dates": [], "ks": [], "idx": {}}
    dates = [x.strftime("%Y-%m-%d") for x in C.index]
    lastd = Hh["dates"][-1] if Hh["dates"] else None
    new = [j for j, x in enumerate(dates) if lastd is None or x > lastd]
    for r in trows:
        s = r["idx"]; arr = Hh["idx"].setdefault(r["key"], [None] * len(Hh["dates"]))
        for j in new:
            if lastd is None:
                arr.append(float(s.iloc[j]) * 100)
            else:
                prev = arr[-1] if arr and arr[-1] else 100.0
                arr.append(prev * float(s.iloc[j] / s.iloc[j - 1]))
    Hh["ks"] += [float(ks.iloc[j]) for j in new]; Hh["dates"] += [dates[j] for j in new]
    dump(hp, Hh)
    dump(TSNAP / f"{day}.json", {"date": day, "score": {r["key"]: r["score"] for r in trows}, "picks": picks_all})
    dump(OUT / "pick_prices.json", {c: P[c][-160:] for c in {x["code"] for p in TSNAP.glob("*.json") for v in (json.loads(p.read_text()).get("picks") or {}).values() for x in v} if c in P})
    sp_hist = pd.Series(Hh["ks"], index=Hh["dates"], dtype=float)
    for r in trows:
        r.pop("idx", None); r.pop("mem", None); r.pop("sig", None); r.pop("ev_raw", None)
    bf = OUT / "theme_backfill.json"
    dump(OUT / "theme.json", {"date": day, "made": NOW.strftime("%Y-%m-%d %H:%M"), "rows": trows, "macro": macro, "market_up": mkt_up,
                              "parts": {"trend": {"name": "주가 추세", "max": 30}, "breadth": {"name": "확산", "max": 20}, "buzz": {"name": "관심(기사)", "max": 15},
                                        "policy": {"name": "정책 뉴스", "max": 15}, "target": {"name": "목표가 여력", "max": 10}, "opinion": {"name": "애널리스트 의견", "max": 10}},
                              "primary": prim, "pick_record": pick_record(sp_hist), "backfill": (json.loads(bf.read_text()) if bf.exists() else {}).get("summary")})
    try:                                              # 모의 투자 (전략을 실제처럼 굴려 기록)
        import us_paper
        us_paper.run(P, day)
    except Exception as e:
        print("모의 투자 실패:", e)
    print(f"완료 {day} · {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
