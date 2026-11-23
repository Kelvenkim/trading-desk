"""한국 시장 연구용 자료 받기 (11/23 형 요청) — 네이버 증권 공개 API
  ① 코스피·코스닥 전 종목 + 시가총액 → 300억~10조 보통주만 (ETF·스팩·우선주 제외)  ※ 지금 시총 기준(생존 편향)
  ② 일봉 2015~ (외국인 보유율 포함)  ③ 투자자별 순매수(개인·외국인·기관) 최근 약 1.5년  ④ 테마 목록·구성 종목
research/kr2/data/ 에 저장 (gitignore)"""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

H = Path(__file__).parent / "data"; H.mkdir(exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0"
def num(x):
    try:
        return float(str(x).replace(",", "").replace("+", ""))
    except (TypeError, ValueError):
        return None

def get(u, tries=3):
    for k in range(tries):
        try:
            r = S.get(u, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(1 + k)
    return None

def universe():
    out = []
    for mk in ("KOSPI", "KOSDAQ"):
        p = 1
        while True:
            d = get(f"https://m.stock.naver.com/api/stocks/marketValue/{mk}?page={p}&pageSize=100")
            if not d or not d.get("stocks"):
                break
            for s in d["stocks"]:
                out.append(dict(code=s["itemCode"], name=s["stockName"], mk=mk, end=s.get("stockEndType"), cap=num(s.get("marketValue")), val=num(s.get("accumulatedTradingValue"))))
            p += 1
            if len(d["stocks"]) < 100:
                break
    U = [s for s in out if s["end"] == "stock" and s["cap"] and 300 <= s["cap"] <= 100000 and "스팩" not in s["name"] and not re.search(r"(우|우B|우C|\(전환\))$", s["name"])]
    (H / "universe_all.json").write_text(json.dumps(out, ensure_ascii=False)); (H / "universe.json").write_text(json.dumps(U, ensure_ascii=False))
    print("전 종목", len(out), "· 시총 300억~10조 보통주", len(U))
    return U

def day(code):
    f = H / f"day_{code}.json"
    if f.exists():
        return
    d = get(f"https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime=201501010000&endDateTime=202612310000")
    if d:
        f.write_text(json.dumps([[x["localDate"], x["openPrice"], x["highPrice"], x["lowPrice"], x["closePrice"], x["accumulatedTradingVolume"], x.get("foreignRetentionRate")] for x in d]))

def trend(code, pages=6):
    f = H / f"trend_{code}.json"
    if f.exists():
        return
    rows, bd = [], None
    for _ in range(pages):
        d = get(f"https://m.stock.naver.com/api/stock/{code}/trend?pageSize=60" + (f"&bizdate={bd}" if bd else ""))
        if not d:
            break
        rows += [[x["bizdate"], num(x.get("individualPureBuyQuant")), num(x.get("foreignerPureBuyQuant")), num(x.get("organPureBuyQuant")), num(x.get("closePrice")), num(x.get("accumulatedTradingVolume"))] for x in d]
        last = d[-1]["bizdate"]
        if len(d) < 60:
            break
        from datetime import date, timedelta
        bd = (date(int(last[:4]), int(last[4:6]), int(last[6:])) - timedelta(days=1)).strftime("%Y%m%d")
    f.write_text(json.dumps(rows))

def themes():
    T, p = [], 1
    while True:
        d = get(f"https://m.stock.naver.com/api/stocks/theme?page={p}&pageSize=100")
        if not d or not d.get("groups"):
            break
        T += d["groups"]; p += 1
        if len(d["groups"]) < 100:
            break
    def mem(t):
        d = get(f"https://m.stock.naver.com/api/stocks/theme/{t['no']}?page=1&pageSize=100")
        return dict(no=t["no"], name=t["name"], codes=[s["itemCode"] for s in (d or {}).get("stocks", [])])
    with ThreadPoolExecutor(6) as ex:
        M = list(ex.map(mem, T))
    (H / "themes.json").write_text(json.dumps(M, ensure_ascii=False)); print("테마", len(M))

if __name__ == "__main__":
    U = universe(); themes()
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda s: day(s["code"]), U))
    print("일봉 끝", len(list(H.glob("day_*.json"))))
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda s: trend(s["code"]), U))
    print("수급 끝", len(list(H.glob("trend_*.json"))))
