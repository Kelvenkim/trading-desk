"""
미국 기업 정보 카드 → data/us/profile/티커.json  (차트 화면에서 종목을 열면 보여줌)
  회사 소개(한국어 번역), 가치평가, 실적·성장, 월가 목표가·의견 분포·최근 의견 변경, 실적 발표 일정·예상치·지난 서프라이즈,
  업종 대비 비교, 관련 뉴스(국내·해외), 투자자 분위기(StockTwits, 우선 종목만)
갱신: 관심종목·추천 바구니·테마 추천은 매일, 나머지는 오래된 순으로 하루 최대 N개 (며칠이면 한 바퀴)
실행: python scripts/us_profiles.py [--all] [--max 90] [--force]
"""
import json, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "data/us/profile"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TR_CACHE = ROOT / "data/us/translate_cache.json"


def num(x):
    try:
        x = float(x)
        return x if np.isfinite(x) else None
    except Exception:
        return None


def translate(text, cache):
    if not text:
        return None
    key = text[:200]
    if key in cache:
        return cache[key]
    parts, out = re.split(r"(?<=[.!?])\s+", text), []
    chunk = ""
    for s in parts:                                 # 긴 글은 나눠서
        if len(chunk) + len(s) > 1500:
            out.append(chunk); chunk = ""
        chunk += s + " "
    if chunk.strip():
        out.append(chunk)
    ko = []
    for c in out:
        if not c.strip():
            continue
        for k in range(3):                          # 가끔 막히면 잠깐 쉬고 다시
            try:
                u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ko&dt=t&q=" + urllib.parse.quote(c)
                r = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
                ko.append("".join(x[0] for x in r[0] if x and x[0]))
                time.sleep(0.3)
                break
            except Exception:
                time.sleep(2 + 3 * k)
        else:
            return None
    cache[key] = " ".join(ko).strip()
    return cache[key]


def gnews(q, lang="ko", n=6):
    import news_build as NB
    p = {"q": q + " when:14d", "hl": lang, "gl": "KR" if lang == "ko" else "US", "ceid": "KR:ko" if lang == "ko" else "US:en"}
    items = NB.rss_items(NB.get("https://news.google.com/rss/search?" + urllib.parse.urlencode(p), raw=True))
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x["at"], reverse=True):
        t = re.sub(r"\s+[-–|]\s+[^-–|]{1,40}$", "", it["t"]).strip()
        if t in seen:
            continue
        seen.add(t); out.append({"t": t, "u": it["u"], "at": it["at"], "o": it.get("src") or (it["t"].rsplit(" - ", 1)[-1][:30] if " - " in it["t"] else "")})
        if len(out) >= n:
            break
    return out


def df_records(df, cols=None, n=None):
    try:
        if df is None or len(df) == 0:
            return []
        d = df.reset_index()
        if n:
            d = d.head(n)
        out = []
        for _, r in d.iterrows():
            row = {}
            for k, v in r.items():
                if cols and k not in cols:
                    continue
                if hasattr(v, "isoformat"):
                    v = v.isoformat()[:10]
                elif isinstance(v, (float, np.floating)):
                    v = num(v)
                elif isinstance(v, (np.integer,)):
                    v = int(v)
                row[str(k)] = v
            out.append(row)
        return out
    except Exception:
        return []


def build(t, ko, cache, with_social=False):
    import yfinance as yf
    import sentiment as SE
    T = yf.Ticker(t)
    try:
        i = T.info or {}
    except Exception:
        i = {}
    if not i.get("longName") and not i.get("shortName"):
        return None
    g = lambda k: num(i.get(k))
    p = {"t": t, "made": NOW.strftime("%Y-%m-%d %H:%M"), "name": i.get("longName") or i.get("shortName"), "ko": ko.get(t),
         "sector": i.get("sector"), "industry": i.get("industry"), "employees": i.get("fullTimeEmployees"),
         "hq": ", ".join(x for x in [i.get("city"), i.get("state"), i.get("country")] if x), "website": i.get("website"),
         "summary_en": i.get("longBusinessSummary"), "quote_type": i.get("quoteType")}
    p["summary_ko"] = translate(i.get("longBusinessSummary") or "", cache)
    p["val"] = {"price": g("currentPrice") or g("regularMarketPrice"), "mcap": g("marketCap"), "pe": g("trailingPE"), "fpe": g("forwardPE"),
                "peg": g("trailingPegRatio"), "ps": g("priceToSalesTrailing12Months"), "pb": g("priceToBook"), "ev_ebitda": g("enterpriseToEbitda"),
                "div": g("dividendYield"), "beta": g("beta"), "hi52": g("fiftyTwoWeekHigh"), "lo52": g("fiftyTwoWeekLow")}
    p["fin"] = {"rev": g("totalRevenue"), "rev_g": g("revenueGrowth"), "eps_g": g("earningsGrowth"), "gross": g("grossMargins"),
                "op": g("operatingMargins"), "net": g("profitMargins"), "roe": g("returnOnEquity"), "fcf": g("freeCashflow"),
                "cash": g("totalCash"), "debt": g("totalDebt"), "de": g("debtToEquity"), "eps": g("trailingEps"), "feps": g("forwardEps")}
    p["own"] = {"short": g("shortPercentOfFloat"), "inst": g("heldPercentInstitutions"), "insider": g("heldPercentInsiders")}
    p["analyst"] = {"n": i.get("numberOfAnalystOpinions"), "mean": g("targetMeanPrice"), "median": g("targetMedianPrice"), "high": g("targetHighPrice"),
                    "low": g("targetLowPrice"), "rec": i.get("recommendationKey"), "recMean": g("recommendationMean")}
    try:
        p["analyst"]["trend"] = df_records(T.recommendations)
    except Exception:
        p["analyst"]["trend"] = []
    try:
        ud = T.upgrades_downgrades
        p["changes"] = df_records(ud.sort_index(ascending=False) if ud is not None and len(ud) else ud, n=10)
    except Exception:
        p["changes"] = []
    e = {}
    try:
        cal = T.calendar or {}
        ed = cal.get("Earnings Date")
        e["next"] = (ed[0].isoformat() if isinstance(ed, list) and ed else None)
        e["eps_avg"], e["eps_low"], e["eps_high"] = num(cal.get("Earnings Average")), num(cal.get("Earnings Low")), num(cal.get("Earnings High"))
        e["rev_avg"] = num(cal.get("Revenue Average"))
    except Exception:
        pass
    try:
        e["eps_est"] = df_records(T.earnings_estimate)
        e["rev_est"] = df_records(T.revenue_estimate)
        e["hist"] = df_records(T.earnings_history)
    except Exception:
        pass
    p["earn"] = e
    p["news_ko"] = gnews(f'"{ko.get(t)}"' if ko.get(t) else f'"{(p["name"] or t).split(",")[0]}" 주가')
    p["news_en"] = gnews(f'{t} stock', "en-US")
    if with_social:
        try:
            p["social"] = SE.stocktwits(t)
        except Exception:
            p["social"] = None
    return p


def peers(profiles):
    """업종(industry·sector)별 중앙값 — '비싼지 싼지' 비교용"""
    by = {}
    for p in profiles:
        for key in ("industry", "sector"):
            k = p.get(key)
            if k:
                by.setdefault((key, k), []).append(p)
    med = {}
    for (key, k), ps in by.items():
        if len(ps) < 4:
            continue
        m = {}
        for f, sec in (("fpe", "val"), ("ps", "val"), ("ev_ebitda", "val"), ("rev_g", "fin"), ("op", "fin"), ("net", "fin")):
            v = [x[sec].get(f) for x in ps if x.get(sec) and x[sec].get(f) is not None and -5 < x[sec][f] < 500]
            if len(v) >= 4:
                m[f] = float(np.median(v))
        med[f"{key}:{k}"] = {"n": len(ps), **m}
    return med


def main(all_=False, max_n=220, force=False):
    OUT.mkdir(parents=True, exist_ok=True)
    mark = OUT / "_last.txt"
    if not force and mark.exists() and mark.read_text().strip() == NOW.strftime("%Y-%m-%d"):
        print("오늘 이미 갱신함"); return
    U = json.loads((ROOT / "data/us/universe.json").read_text())
    from us_narr_def import NARR, EXTRA_KO
    ko = {**U.get("ko", {}), **EXTRA_KO}
    tick = sorted({s["t"] for s in U["stocks"]} | {t for n in NARR for t in n["tickers"]})
    pri = set()
    try:
        pri |= {s["symbol"] for s in json.loads((ROOT / "watchlist.json").read_text())["symbols"]}
        pri |= {r["code"] for r in json.loads((ROOT / "data/us/rank.json").read_text())["rows"] if r.get("basket")}
        pri |= {p["code"] for r in json.loads((ROOT / "data/us/theme.json").read_text())["rows"] for p in r.get("picks", [])}
    except Exception:
        pass
    age = {}
    for t in tick:
        f = OUT / f"{t}.json"
        age[t] = json.loads(f.read_text()).get("made", "") if f.exists() else ""
    rest = sorted([t for t in tick if t not in pri], key=lambda t: age[t])
    todo = sorted(pri) + (rest if all_ else rest[:max_n])
    cache = json.loads(TR_CACHE.read_text()) if TR_CACHE.exists() else {}
    t0 = time.time(); ok = 0
    budget = 25 * 60 if not all_ else 10 ** 9            # 예약 실행은 25분 안에 끝내기 (남은 건 다음 날)
    def one(t):
        if time.time() - t0 > budget:
            return t, None
        try:
            return t, build(t, ko, cache, with_social=t in pri)
        except Exception as e:
            return t, None
    with ThreadPoolExecutor(3) as ex:
        for t, p in ex.map(one, todo):
            if p:
                (OUT / f"{t}.json").write_text(json.dumps(p, ensure_ascii=False, separators=(",", ":"), default=str))
                ok += 1
    TR_CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    mark.write_text(NOW.strftime("%Y-%m-%d"))
    # 업종 비교표
    allp = []
    for f in OUT.glob("[A-Z]*.json"):
        try:
            allp.append(json.loads(f.read_text()))
        except Exception:
            pass
    (ROOT / "data/us/peers.json").write_text(json.dumps(peers(allp), ensure_ascii=False))
    print(f"기업 정보 {ok}/{len(todo)} 갱신 · 전체 {len(allp)}개 · {time.time() - t0:.0f}s")


if __name__ == "__main__":
    a = sys.argv
    main(all_="--all" in a, max_n=int(a[a.index("--max") + 1]) if "--max" in a else 90, force="--force" in a)
