"""미국 종목 목록: S&P500(업종 포함) + 나스닥100 → data/us/universe.json (주 1회 갱신, 실패하면 이전 목록 유지)"""
import csv, io, json, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us/universe.json"
UA = {"User-Agent": "Mozilla/5.0"}

# 한국어 이름 (검색·뉴스 태그용, 자주 보는 종목)
KO = {"AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존", "GOOGL": "알파벳", "GOOG": "알파벳C", "META": "메타",
      "TSLA": "테슬라", "AVGO": "브로드컴", "BRK-B": "버크셔해서웨이", "JPM": "JP모건", "LLY": "일라이릴리", "V": "비자", "MA": "마스터카드",
      "UNH": "유나이티드헬스", "XOM": "엑슨모빌", "COST": "코스트코", "WMT": "월마트", "NFLX": "넷플릭스", "ORCL": "오라클", "AMD": "AMD",
      "INTC": "인텔", "QCOM": "퀄컴", "MU": "마이크론", "TSM": "TSMC", "ASML": "ASML", "ARM": "ARM", "PLTR": "팔란티어", "CRM": "세일즈포스",
      "ADBE": "어도비", "NOW": "서비스나우", "PANW": "팔로알토", "CRWD": "크라우드스트라이크", "SNOW": "스노우플레이크", "UBER": "우버",
      "SHOP": "쇼피파이", "PYPL": "페이팔", "COIN": "코인베이스", "MSTR": "마이크로스트래티지", "HOOD": "로빈후드", "BA": "보잉",
      "LMT": "록히드마틴", "RTX": "RTX", "NOC": "노스롭그루먼", "GD": "제너럴다이내믹스", "GE": "GE에어로스페이스", "CAT": "캐터필러",
      "DE": "디어", "HON": "허니웰", "VST": "비스트라", "CEG": "컨스텔레이션에너지", "NEE": "넥스트에라", "GEV": "GE버노바",
      "ETN": "이튼", "VRT": "버티브", "SMCI": "슈퍼마이크로", "DELL": "델", "ANET": "아리스타", "LRCX": "램리서치", "AMAT": "어플라이드머티어리얼즈",
      "KLAC": "KLA", "MRVL": "마벨", "TXN": "텍사스인스트루먼트", "ADI": "아날로그디바이스", "NXPI": "NXP", "ON": "온세미",
      "PFE": "화이자", "MRK": "머크", "ABBV": "애브비", "JNJ": "존슨앤드존슨", "NVO": "노보노디스크", "AMGN": "암젠", "GILD": "길리어드",
      "KO": "코카콜라", "PEP": "펩시코", "MCD": "맥도날드", "SBUX": "스타벅스", "NKE": "나이키", "DIS": "디즈니", "HD": "홈디포",
      "BAC": "뱅크오브아메리카", "GS": "골드만삭스", "MS": "모건스탠리", "WFC": "웰스파고", "C": "씨티", "BLK": "블랙록", "SCHW": "찰스슈왑",
      "CVX": "셰브론", "COP": "코노코필립스", "OXY": "옥시덴탈", "FCX": "프리포트맥모란", "NEM": "뉴몬트", "F": "포드", "GM": "GM",
      "RIVN": "리비안", "LCID": "루시드", "IBM": "IBM", "CSCO": "시스코", "APP": "앱러빈", "AXON": "액손", "ABNB": "에어비앤비",
      "SPY": "S&P500 ETF", "QQQ": "나스닥100 ETF", "DIA": "다우 ETF", "IWM": "러셀2000 ETF", "SOXX": "반도체 ETF", "TQQQ": "나스닥 3배 ETF"}


def get(url, raw=True):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                b = r.read()
            return b.decode() if raw else json.loads(b)
        except Exception:
            time.sleep(2 + 3 * k)
    return None


def main():
    old = json.loads(OUT.read_text()) if OUT.exists() else {"stocks": []}
    rows = {}
    txt = get("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv")
    if txt:
        for r in csv.DictReader(io.StringIO(txt)):
            t = r["Symbol"].replace(".", "-")
            rows[t] = {"t": t, "name": r["Security"], "sector": r["GICS Sector"], "sub": r["GICS Sub-Industry"], "idx": ["SP500"]}
    j = get("https://api.nasdaq.com/api/quote/list-type/nasdaq100", raw=False)
    for r in (((j or {}).get("data") or {}).get("data") or {}).get("rows") or []:
        t = r["symbol"].replace(".", "-")
        if t in rows:
            rows[t]["idx"].append("NDX")
        else:
            rows[t] = {"t": t, "name": r.get("companyName"), "sector": r.get("sector") or "", "sub": "", "idx": ["NDX"]}
    if len(rows) < 400:
        print("목록을 충분히 받지 못해 이전 목록 유지", len(rows)); return
    for t, r in rows.items():
        r["ko"] = KO.get(t)
    out = {"made": time.strftime("%Y-%m-%d"), "stocks": sorted(rows.values(), key=lambda r: r["t"]), "ko": KO}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("미국 종목", len(rows), "· 나스닥100만", sum(1 for r in rows.values() if r["idx"] == ["NDX"]))


if __name__ == "__main__":
    main()
