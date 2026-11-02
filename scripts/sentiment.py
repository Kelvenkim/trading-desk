"""
시장 여론 모으기
  - 국내 증권사: 목표가·투자의견, 최근 리포트 (네이버 증권)
  - 수급: 외국인·기관 최근 순매수 (네이버 증권)
  - 해외 포함 애널리스트 집계: Yahoo Finance (목표가 평균·의견 수·추천)
  - 투자 커뮤니티: 네이버 종목토론방 최근 글의 낙관·비관 단어 비율
  - 예측시장: Polymarket(검색), Kalshi(거시 지표 시리즈)
"""
import json, time, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}


def _get(url, timeout=20, tries=2):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(1 + k * 2)
    return None


def num(x):
    try:
        return float(str(x).replace(",", "").replace("+", "").replace("%", ""))
    except Exception:
        return None


def naver_detail(code):
    j = _get(f"https://m.stock.naver.com/api/stock/{code}/integration")
    if not j:
        return None
    c = j.get("consensusInfo") or {}
    rs = [{"broker": r.get("bnm"), "title": r.get("tit"), "date": r.get("wdt"), "id": r.get("id")} for r in (j.get("researches") or [])[:4]]
    fl = j.get("dealTrendInfos") or []
    f5 = sum((num(x.get("foreignerPureBuyQuant")) or 0) * (num(x.get("closePrice")) or 0) for x in fl[:5])
    o5 = sum((num(x.get("organPureBuyQuant")) or 0) * (num(x.get("closePrice")) or 0) for x in fl[:5])
    return {"target": num(c.get("priceTargetMean")) or None, "opinion": num(c.get("recommMean")), "cdate": c.get("createDate"),
            "reports": rs, "foreign5": f5, "organ5": o5, "fhold": (fl[0].get("foreignerHoldRatio") if fl else None), "flow_days": len(fl[:5])}


BULL = ["매수", "간다", "가즈아", "상승", "오른다", "떡상", "저점", "싸다", "줍줍", "호재", "목표가", "돌파", "반등", "기대", "홀딩", "존버", "대박"]
BEAR = ["매도", "손절", "떨어", "폭락", "하락", "탈출", "악재", "물렸", "고점", "망했", "도망", "팔아", "버려", "개잡주", "거품", "하한"]


def community(code, n=60):
    j = _get(f"https://m.stock.naver.com/front-api/discussion/list?discussionType=domesticStock&itemCode={code}"
             f"&isHolderOnly=false&excludesItemNews=true&isItemNewsOnly=false&isCleanbotPassedOnly=true&pageSize={n}")
    posts = ((j or {}).get("result") or {}).get("posts") if isinstance((j or {}).get("result"), dict) else (j or {}).get("posts")
    if not posts:
        return None
    bull = bear = 0
    for p in posts:
        t = (p.get("title") or "") + " " + (p.get("contents") or "")[:200]
        b1, b2 = any(w in t for w in BULL), any(w in t for w in BEAR)
        bull += b1 and not b2; bear += b2 and not b1
    span = None
    try:
        ts = sorted(p.get("writtenAt") for p in posts if p.get("writtenAt"))
        span = ts[0][:16].replace("T", " ") + " ~ " + ts[-1][:16].replace("T", " ")
    except Exception:
        pass
    return {"n": len(posts), "bull": bull, "bear": bear, "ratio": bull / (bull + bear) if bull + bear else None, "span": span}


def yahoo(sym):
    try:
        import yfinance as yf
        i = yf.Ticker(sym).info or {}
        if not i.get("numberOfAnalystOpinions"):
            return {"name": i.get("longName") or i.get("shortName")}
        return {"name": i.get("longName") or i.get("shortName"), "target": i.get("targetMeanPrice"), "high": i.get("targetHighPrice"),
                "low": i.get("targetLowPrice"), "n": i.get("numberOfAnalystOpinions"), "rec": i.get("recommendationKey")}
    except Exception:
        return None


def _poly_event(e):
    ms = e.get("markets") or []
    outs = []
    for m in ms:
        try:
            pr = json.loads(m.get("outcomePrices") or "[]")
            yes = float(pr[0]) if pr else None
        except Exception:
            yes = None
        if yes is None or m.get("closed"):
            continue
        outs.append({"label": m.get("groupItemTitle") or ("Yes" if len(ms) == 1 else m.get("question")), "p": yes})
    outs.sort(key=lambda x: -x["p"])
    return {"src": "Polymarket", "title": e.get("title"), "url": f"https://polymarket.com/event/{e.get('slug')}",
            "vol": float(e.get("volume") or 0), "end": (e.get("endDate") or "")[:10], "outs": outs[:3], "single": len(ms) == 1}


def polymarket(q, min_vol=20000, k=3):
    j = _get("https://gamma-api.polymarket.com/public-search?" + urllib.parse.urlencode({"q": q, "limit_per_type": 8, "events_status": "active"}))
    out = []
    for e in (j or {}).get("events", []) or []:
        if e.get("closed") or float(e.get("volume") or 0) < min_vol:
            continue
        ev = _poly_event(e)
        if ev["outs"]:
            out.append(ev)
    out.sort(key=lambda x: -x["vol"])
    return out[:k]


KALSHI_SERIES = [("KXFEDDECISION", "미국 12월 금리 결정"), ("KXRECSSNBER", "올해 미국 경기침체"), ("KXINXY", "S&P500 연말 지수")]


def kalshi_macro():
    out = []
    for s, ko in KALSHI_SERIES:
        j = _get(f"https://api.elections.kalshi.com/trade-api/v2/events?series_ticker={s}&status=open&with_nested_markets=true&limit=1")
        ev = ((j or {}).get("events") or [None])[0]
        if not ev:
            continue
        outs = []
        for m in ev.get("markets", []):
            p = num(m.get("last_price_dollars")) or num(m.get("yes_bid_dollars"))
            if p is not None:
                outs.append({"label": m.get("yes_sub_title") or m.get("title"), "p": p})
        outs.sort(key=lambda x: -x["p"])
        out.append({"src": "Kalshi", "title": ev.get("title"), "ko": ko, "url": f"https://kalshi.com/markets/{s.lower()}",
                    "outs": outs[:3], "single": len(ev.get("markets", [])) == 1})
        time.sleep(0.5)
    return out
