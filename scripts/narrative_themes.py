"""네이버 증권 테마 전체(약 260개)와 소속 종목 → data/narrative/naver_themes.json (주 1회 정도 갱신)"""
import json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent / "data/narrative/naver_themes.json"
H = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}

def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=20) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(1 + 2 * k)
    return None

def main():
    groups, page = [], 1
    while True:
        j = get(f"https://m.stock.naver.com/api/stocks/theme?page={page}&pageSize=100")
        if not j or not j.get("groups"):
            break
        groups += j["groups"]
        if len(groups) >= j.get("totalCount", 0):
            break
        page += 1
    def members(g):
        j = get(f"https://m.stock.naver.com/api/stocks/theme/{g['no']}?page=1&pageSize=100") or {}
        return g["no"], [[s["itemCode"], s["stockName"]] for s in j.get("stocks", [])]
    with ThreadPoolExecutor(6) as ex:
        mem = dict(ex.map(members, groups))
    out = {"made": time.strftime("%Y-%m-%d"), "themes": [{"no": g["no"], "name": g["name"], "stocks": mem.get(g["no"], [])} for g in groups]}
    if len(out["themes"]) < 100:
        raise SystemExit("테마를 충분히 받지 못했어요")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("themes", len(out["themes"]), "links", sum(len(t["stocks"]) for t in out["themes"]))

if __name__ == "__main__":
    main()
