"""AI 에이전트 계좌용 자료 (11/23 형: Massive 데이터로 진짜 AI 에이전트 매매)
Massive(옛 Polygon.io) 무료 플랜으로 되는 것만: 장 상태 · 최신 뉴스(종목 태그·종목별 호재/악재 판단 포함) · 보유 종목 뉴스
무료 플랜은 1분에 5번까지라 한 번 실행에 최대 4번만 부름. 키는 GitHub secrets MASSIVE_API_KEY (코드·파일에 절대 안 씀)
→ data/us/agent_brief.json  (에이전트가 판단할 때 rank.json·theme.json·market.json과 같이 읽음)"""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/us/agent_brief.json"
KEY = os.environ.get("MASSIVE_API_KEY", "").strip()
API = "https://api.massive.com"


def get(path, **params):
    params["apiKey"] = KEY
    r = requests.get(f"{API}/{path}", params=params, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"{path} {r.status_code} {r.text[:120]}")
    return r.json()


def slim(n):
    ins = {i.get("ticker"): {"s": i.get("sentiment"), "why": i.get("sentiment_reasoning")} for i in (n.get("insights") or [])}
    return {"t": n.get("title"), "at": n.get("published_utc"), "src": (n.get("publisher") or {}).get("name"), "u": n.get("article_url"),
            "tk": n.get("tickers") or [], "desc": (n.get("description") or "")[:400], "ins": ins}


def main():
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    if not KEY:
        print("MASSIVE_API_KEY 없음 → 건너뜀 (GitHub secrets에 넣으면 시작)")
        return
    out = {"made": datetime.now(timezone.utc).isoformat(timespec="minutes"), "source": "Massive (무료 플랜)"}
    try:
        out["market"] = get("v1/marketstatus/now")
    except Exception as e:
        out["market_err"] = str(e)
    try:
        out["news"] = [slim(n) for n in get("v2/reference/news", limit=100, order="desc", sort="published_utc").get("results", [])]
    except Exception as e:
        out["news_err"] = str(e); out["news"] = old.get("news", [])
    held = []
    try:
        S = json.loads((ROOT / "data/us/agent_paper_state.json").read_text())
        held = sorted(S.get("pos", {}))
    except Exception:
        pass
    out["held_news"] = {}
    for s in held[:2]:
        try:
            time.sleep(1)
            out["held_news"][s] = [slim(n) for n in get("v2/reference/news", ticker=s, limit=10, order="desc", sort="published_utc").get("results", [])]
        except Exception as e:
            out["held_news"][s] = old.get("held_news", {}).get(s, [])
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"에이전트 자료: 뉴스 {len(out['news'])}건 · 장 {out.get('market', {}).get('market')}")


if __name__ == "__main__":
    main()
