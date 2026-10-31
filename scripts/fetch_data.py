"""
watchlist.json에 있는 종목의 시세를 받아 data/ 폴더에 JSON으로 저장합니다.

  data/meta.json               전체 종목 요약 (현재가, 등락률, 갱신 시각)
  data/daily/<심볼>.json        일봉 (최근 10년)
  data/intraday/<심볼>.json     5분봉 (최근 60일, intraday: true 인 종목만)

로컬 실행:  pip install -r requirements.txt && python scripts/fetch_data.py
"""
import json
import math
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path

import FinanceDataReader as fdr
import yfinance as yf

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))


def safe_name(symbol: str) -> str:
    return symbol.replace("^", "_").replace("/", "_")


def to_bars(df, intraday: bool):
    bars = []
    for ts, r in df.iterrows():
        vals = [r["Open"], r["High"], r["Low"], r["Close"], r["Volume"]]
        if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals[:4]):
            continue
        if intraday:
            t = int(ts.timestamp())                      # UNIX 초 (UTC)
        else:
            t = ts.strftime("%Y-%m-%d")
        o, h, l, c, v = vals
        v = 0 if (v is None or (isinstance(v, float) and math.isnan(v))) else int(v)
        bars.append([t, round(float(o), 4), round(float(h), 4), round(float(l), 4), round(float(c), 4), v])
    return bars


def is_korean(symbol: str) -> bool:
    return symbol.endswith((".KS", ".KQ"))


def download(symbol: str, period: str, interval: str):
    # 한국 종목 일봉은 야후 종가가 실제와 어긋나는 경우가 있어 FinanceDataReader(네이버) 사용
    if interval == "1d" and is_korean(symbol):
        start = (datetime.now(KST) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
        df = fdr.DataReader(symbol.split(".")[0], start)
        if df is None or df.empty:
            return None
        df = df[df["Volume"] > 0]  # 거래정지일 제외
        return df[["Open", "High", "Low", "Close", "Volume"]]
    df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False, actions=False)
    if df is None or df.empty:
        return None
    return df


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    watch = json.loads((ROOT / "watchlist.json").read_text(encoding="utf-8"))["symbols"]
    meta = {"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "symbols": []}

    for item in watch:
        sym, name = item["symbol"], item.get("name", item["symbol"])
        fname = safe_name(sym) + ".json"
        entry = {"symbol": sym, "name": name, "file": fname, "intraday": False}
        try:
            d = download(sym, "10y", "1d")
            if d is None:
                print(f"[건너뜀] {sym}: 일봉 데이터 없음")
                continue
            bars = to_bars(d, intraday=False)
            write_json(DATA / "daily" / fname, {"symbol": sym, "name": name, "interval": "1d", "bars": bars})
            last, prev = bars[-1], bars[-2] if len(bars) > 1 else bars[-1]
            entry.update({
                "date": last[0], "close": last[4], "prevClose": prev[4],
                "change": round(last[4] - prev[4], 4),
                "changePct": round((last[4] / prev[4] - 1) * 100, 2) if prev[4] else 0,
                "volume": last[5],
                "high52": max(b[2] for b in bars[-252:]),
                "low52": min(b[3] for b in bars[-252:]),
                "currency": "KRW" if is_korean(sym) else "USD",
            })

            if item.get("intraday"):
                di = download(sym, "60d", "5m")
                if di is not None:
                    ib = to_bars(di, intraday=True)
                    write_json(DATA / "intraday" / fname, {"symbol": sym, "name": name, "interval": "5m", "bars": ib})
                    entry["intraday"] = True
                    # 장중이면 5분봉 마지막 값이 더 최신 → 현재가로 사용
                    next_day = datetime.strptime(last[0], "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)
                    if ib and ib[-1][0] >= next_day.timestamp():
                        entry["prevClose"] = last[4]
                        entry["close"] = ib[-1][4]
                        entry["date"] = datetime.fromtimestamp(ib[-1][0], KST).strftime("%Y-%m-%d")
                        entry["change"] = round(entry["close"] - entry["prevClose"], 4)
                        entry["changePct"] = round((entry["close"] / entry["prevClose"] - 1) * 100, 2)
            print(f"[완료] {sym} {name}: 일봉 {len(bars)}개{' + 5분봉' if entry['intraday'] else ''}")
        except Exception as e:  # 한 종목 실패가 전체를 멈추지 않도록
            print(f"[오류] {sym}: {e}")
            continue
        meta["symbols"].append(entry)

    write_json(DATA / "meta.json", meta)
    print(f"meta.json 저장: {len(meta['symbols'])}개 종목, {meta['updated']}")


US_LIST = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/{0}/{0}_full_tickers.json"


def build_symbols(force: bool = False):
    """검색용 종목 목록 data/symbols.json (하루 한 번만 갱신)."""
    path = DATA / "symbols.json"
    today = datetime.now(KST).strftime("%Y-%m-%d")
    if path.exists() and not force:
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("updated") == today:
                return
        except Exception:
            pass
    rows = []
    try:
        l = fdr.StockListing("KRX")
        l = l[l["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"])].sort_values("Marcap", ascending=False)
        for _, r in l.iterrows():
            mk = "KOSPI" if r["Market"] == "KOSPI" else "KOSDAQ"
            rows.append([r["Code"] + (".KS" if mk == "KOSPI" else ".KQ"), r["Name"], mk])
    except Exception as e:
        print("[오류] 한국 종목 목록:", e)
    try:
        etf = fdr.StockListing("ETF/KR")
        for _, r in etf.iterrows():
            rows.append([str(r["Symbol"]) + ".KS", r["Name"], "ETF"])
    except Exception as e:
        print("[오류] ETF 목록:", e)
    try:
        import urllib.request
        us = []
        for ex in ("nasdaq", "nyse", "amex"):
            with urllib.request.urlopen(US_LIST.format(ex), timeout=30) as f:
                for r in json.loads(f.read().decode()):
                    try:
                        cap = float(r.get("marketCap") or 0)
                    except ValueError:
                        cap = 0
                    if cap >= 3e8 and "^" not in r["symbol"]:  # 시가총액 3억 달러 이상
                        us.append((cap, r["symbol"].replace("/", "-").replace(".", "-"), r["name"], ex.upper()))
        us.sort(reverse=True)
        rows += [[s, n.replace(" Common Stock", "").replace(" Class A", ""), ex] for _, s, n, ex in us]
    except Exception as e:
        print("[오류] 미국 종목 목록:", e)
    if rows:
        write_json(path, {"updated": today, "list": rows})
        print(f"symbols.json 저장: {len(rows)}개")


if __name__ == "__main__":
    main()
    build_symbols()
