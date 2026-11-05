"""
뉴스 탭 자료 — 시장 주요 뉴스 + 유명 인물이 자주 쓰는 단어
  시장 뉴스: 네이버 증권 주요 뉴스 (관련 종목·장기 테마·정책·호재/악재 표시)
  인물:
    트럼프 — 본인 Truth Social 글(trumpstruth.org 공개 보관 피드, 영어) + 백악관 발표 + 국내 기사 제목
    그 밖 — 구글 뉴스 국내 기사 제목에서 함께 나온 단어
  단어는 최근 7일 vs 그 전 7일 횟수로 '늘어남/줄어듦'을 보여줌. 글·제목은 data/news/archive.json 에 쌓아 몇 주치 비교
실행: python scripts/news_build.py (시세 갱신과 함께 30분마다)
"""
import html, json, re, sys, time, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "data/news"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
UA = {"User-Agent": "Mozilla/5.0"}

PEOPLE = [
    {"key": "trump", "name": "도널드 트럼프", "role": "미국 대통령", "truth": True, "gnews": "트럼프"},
    {"key": "jensen", "name": "젠슨 황", "role": "엔비디아 CEO", "gnews": "젠슨 황"},
    {"key": "musk", "name": "일론 머스크", "role": "테슬라·스페이스X CEO", "gnews": "머스크"},
    {"key": "fed", "name": "연준 의장", "role": "미국 중앙은행(금리)", "gnews": "연준 의장"},
    {"key": "altman", "name": "샘 올트먼", "role": "OpenAI CEO", "gnews": "올트먼"},
]

# 시장과 관련된 단어 → (한국어, 장기 테마 key 들)
EN_MARKET = {
    "tariff": ("관세", ["auto", "materials"]), "tariffs": ("관세", ["auto", "materials"]), "trade": ("무역", []), "china": ("중국", []),
    "chinese": ("중국", []), "chip": ("반도체", ["ai_chip"]), "chips": ("반도체", ["ai_chip"]), "semiconductor": ("반도체", ["ai_chip"]),
    "semiconductors": ("반도체", ["ai_chip"]), "korea": ("한국", []), "korean": ("한국", []), "japan": ("일본", []), "fed": ("연준", []),
    "rate": ("금리", []), "rates": ("금리", []), "interest": ("금리", []), "inflation": ("물가", []), "oil": ("유가", []),
    "drill": ("석유 시추", []), "energy": ("에너지", ["power", "green"]), "nuclear": ("원전·핵", ["nuclear"]), "ship": ("배", ["ship"]),
    "ships": ("배", ["ship"]), "shipbuilding": ("조선", ["ship"]), "navy": ("해군", ["ship", "defense"]), "crypto": ("암호화폐", ["digital"]),
    "bitcoin": ("비트코인", ["digital"]), "stablecoin": ("스테이블코인", ["digital"]), "ukraine": ("우크라이나", ["defense", "infra"]),
    "russia": ("러시아", ["defense", "infra"]), "ceasefire": ("휴전", ["defense", "infra"]), "war": ("전쟁", ["defense"]),
    "military": ("군", ["defense"]), "defense": ("국방", ["defense"]), "nato": ("나토", ["defense"]), "iran": ("이란", ["defense"]),
    "steel": ("철강", ["materials"]), "aluminum": ("알루미늄", ["materials"]), "copper": ("구리", ["materials"]), "cars": ("자동차", ["auto"]),
    "auto": ("자동차", ["auto"]), "drug": ("약", ["bio"]), "drugs": ("약", ["bio"]), "pharmaceutical": ("제약", ["bio"]),
    "robot": ("로봇", ["robot"]), "robots": ("로봇", ["robot"]), "electricity": ("전기", ["power"]), "grid": ("전력망", ["power"]),
    "investment": ("투자", []), "jobs": ("일자리", []), "economy": ("경제", []), "market": ("시장", []), "stock": ("주식", []),
    "dollar": ("달러", []), "taxes": ("세금", []), "tax": ("세금", []), "deal": ("협상·거래", []), "space": ("우주", ["defense"]),
}
KO_MARKET = {
    "관세": ["auto", "materials"], "반도체": ["ai_chip"], "엔비디아": ["ai_chip"], "HBM": ["ai_chip"], "AI": ["software", "ai_chip"],
    "원전": ["nuclear"], "SMR": ["nuclear"], "조선": ["ship"], "방산": ["defense"], "전쟁": ["defense"], "휴전": ["defense", "infra"],
    "금리": [], "인하": [], "인상": [], "물가": [], "비트코인": ["digital"], "가상자산": ["digital"], "스테이블코인": ["digital"],
    "로봇": ["robot"], "휴머노이드": ["robot"], "테슬라": ["auto", "battery"], "전기차": ["battery", "auto"], "자율주행": ["auto"],
    "데이터센터": ["power", "ai_chip"], "전력": ["power"], "중국": [], "수출": [], "철강": ["materials"], "배터리": ["battery"],
    "우주": ["defense"], "스페이스X": ["defense"], "오픈AI": ["software"], "칩": ["ai_chip"], "투자": [], "환율": [],
}
EN_STOP = set("""the a an and or but if of to in on at by for with from as is are was were be been being this that these those it its
they them their we our us you your he him his she her i me my mine our ours not no yes so very just also than then there here what which who whom
whose when where why how all any both each few more most other some such only own same too can will would should could may might must do does did
done have has had having get got make made go going went come came say said says one two three about into over after before again further once
up down out off under above below between through during because while until against among per via amp https http www com truthsocial status
statuses rt new now many much great big good bad people country time year years day days today tonight thank thanks everyone president trump donald
america american americans united states usa u.s s don t ll re ve m like know want even back never ever always way well really view image video
""".split())
KO_JOSA = ("으로", "에서", "에게", "까지", "부터", "보다", "처럼", "라고", "이라", "하고", "이며", "이나", "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "도", "로", "만", "께")
KO_STOP = set("""기자 뉴스 연합뉴스 종합 속보 단독 사진 영상 오늘 내일 이번 지난 관련 위해 대해 통해 따라 이후 이어 가운데 정도 상황 우리 대한 한국 미국 발언 말했다 밝혔다
강조 언급 전망 예상 가능성 결국 다시 최근 현재 지금 또한 그리고 하지만 것으로 했다 한다 된다 있다 없다 있는 없는 하는 되는 위한 대한민국 서울 경제 신문 일보 방송 뉴시스 머니투데이 이데일리 매일경제 한국경제
""".split())


def get(url, raw=False, timeout=20):
    for k in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
            return b.decode("utf-8", "replace") if raw else json.loads(b)
        except Exception:
            time.sleep(1 + k)
    return None


def rss_items(xml):
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml or "", re.S):
        g = lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", it, re.S) or [None, ""])[1]
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", s)))).strip()
        try:
            dt = parsedate_to_datetime(g("pubDate")).astimezone(KST)
        except Exception:
            dt = NOW
        out.append({"t": clean(g("title")), "d": clean(g("description")), "u": clean(g("link")), "at": dt.strftime("%Y-%m-%d %H:%M"),
                    "src": clean(g("source")) if "<source" in it else ""})
    return out


def en_words(text):
    text = re.sub(r"https?://\S+", " ", text.lower())
    return [w for w in re.findall(r"[a-z][a-z']{2,}", text) if w not in EN_STOP and not w.endswith("'s")]


def raw_ko(title):
    t = re.sub(r"\s-\s[^-]+$", "", title)          # 끝의 '- 언론사' 제거
    return re.findall(r"[가-힣A-Za-z0-9]{2,}", t)


def ko_normalizer(titles):
    """조사 떼기: '관세를'→'관세'. 단, 뗀 말이 다른 제목에 따로 나온 적이 있을 때만 (스파이→스파 같은 실수 방지)"""
    vocab = Counter(w for t in titles for w in raw_ko(t))
    def norm(w):
        for j in KO_JOSA:
            if w.endswith(j) and len(w) - len(j) >= 2 and vocab.get(w[: -len(j)], 0) >= 1:
                return w[: -len(j)]
        return w
    return norm


def ko_words(title, drop, norm=lambda w: w):
    out = []
    for w in raw_ko(title):
        w = norm(w)
        if w in KO_STOP or any(d in w for d in drop) or w.isdigit():
            continue
        out.append(w)
    return out


def count_window(items, fn, days):
    a = Counter(); b = Counter()
    t1 = (NOW - timedelta(days=days)).strftime("%Y-%m-%d %H:%M"); t2 = (NOW - timedelta(days=2 * days)).strftime("%Y-%m-%d %H:%M")
    for it in items:
        ws = set(fn(it))                       # 한 글에서 같은 단어는 한 번만
        if it["at"] >= t1:
            a.update(ws)
        elif it["at"] >= t2:
            b.update(ws)
    return a, b


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    arch_p = OUT / "archive.json"
    arch = json.loads(arch_p.read_text()) if arch_p.exists() else {}
    cut = (NOW - timedelta(days=45)).strftime("%Y-%m-%d")

    def merge(key, items):
        old = {x["u"]: x for x in arch.get(key, [])}
        for x in items:
            if x.get("u"):
                old.setdefault(x["u"], x)
        arch[key] = sorted([x for x in old.values() if x["at"][:10] >= cut], key=lambda x: x["at"], reverse=True)[:1500]
        return arch[key]

    # ---- 인물 ----
    people = []
    for p in PEOPLE:
        info = {"key": p["key"], "name": p["name"], "role": p["role"]}
        heads = merge(p["key"] + "_news", rss_items(get("https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": p["gnews"] + " when:7d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"}), raw=True)))
        drop = [p["gnews"].replace(" ", ""), p["gnews"].split()[0], p["name"].split()[-1]]
        norm = ko_normalizer([h["t"] for h in heads])
        a, b = count_window(heads, lambda it: ko_words(it["t"], drop, norm), 7)
        info["ko_words"] = [{"w": w, "n": n, "prev": b.get(w, 0), "themes": KO_MARKET.get(w, [])} for w, n in a.most_common(18)]
        info["ko_market"] = [{"w": w, "n": a.get(w, 0), "prev": b.get(w, 0), "themes": th} for w, th in KO_MARKET.items() if a.get(w, 0) >= 2]
        info["ko_market"].sort(key=lambda x: -x["n"])
        info["heads"] = [{"t": h["t"], "u": h["u"], "at": h["at"]} for h in heads[:8]]
        info["since"] = heads[-1]["at"][:10] if heads else None
        info["n_heads"] = sum(1 for h in heads if h["at"] >= (NOW - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))
        if p.get("truth"):
            posts = [x for x in rss_items(get("https://www.trumpstruth.org/feed", raw=True))
                     if len(re.sub(r"View (image|video)", "", x["d"]).strip()) > 25 and not x["d"].startswith("http")]
            posts = merge("trump_truth", [{"t": re.sub(r"\s*View (image|video)\s*", " ", x["d"]).strip()[:600], "u": x["u"], "at": x["at"]} for x in posts])
            posts = [x for x in posts if len(re.sub(r"View (image|video)", "", x["t"]).strip()) > 25]
            wh = merge("whitehouse", rss_items(get("https://www.whitehouse.gov/news/feed/", raw=True)))
            a, b = count_window(posts, lambda it: en_words(it["t"]), 7)
            info["own_words"] = [{"w": w, "ko": EN_MARKET.get(w, (None,))[0], "n": n, "prev": b.get(w, 0), "themes": EN_MARKET.get(w, (None, []))[1]}
                                 for w, n in a.most_common(20)]
            mk = Counter()
            for w, (ko, th) in EN_MARKET.items():
                if a.get(w):
                    mk[ko] += a[w]
            prevk = Counter()
            for w, (ko, th) in EN_MARKET.items():
                if b.get(w):
                    prevk[ko] += b[w]
            themes_of = {}
            for w, (ko, th) in EN_MARKET.items():
                themes_of.setdefault(ko, set()).update(th)
            info["own_market"] = [{"w": k, "n": n, "prev": prevk.get(k, 0), "themes": sorted(themes_of.get(k, []))} for k, n in mk.most_common(15)]
            info["n_posts"] = sum(1 for x in posts if x["at"] >= (NOW - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))
            info["posts"] = posts[:6]
            info["since_own"] = posts[-1]["at"][:10] if posts else None
            info["whitehouse"] = [{"t": x["t"], "u": x["u"], "at": x["at"]} for x in wh[:6]]
        people.append(info)

    # ---- 시장 뉴스 ----
    try:
        from narrative_def import NARRATIVES, POLICY_WORDS
        import rank_lib as L
    except Exception:
        NARRATIVES, POLICY_WORDS, L = [], [], None
    try:
        rows = json.loads((ROOT / "data/rank/latest.json").read_text())["rows"]
        names = sorted({(r["name"], r["code"]) for r in rows}, key=lambda x: -len(x[0]))
    except Exception:
        names = []
    news = []
    for page in (1, 2, 3):
        j = get(f"https://m.stock.naver.com/front-api/news/category?category=mainnews&pageSize=40&page={page}") or {}
        for it in j.get("result") or []:
            t = html.unescape(it.get("titleFull") or it.get("title") or "")
            dt = it.get("datetime", "")
            at = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]} {dt[8:10]}:{dt[10:12]}" if len(dt) >= 12 else ""
            text = t + " " + (it.get("body") or "")[:120]
            stocks = []
            for nm, cd in names:
                if len(nm) >= 2 and nm in t and all(nm not in s[0] for s in stocks):
                    stocks.append([nm, cd])
            themes = sorted({k for w, ks in KO_MARKET.items() if w in text for k in ks})
            who = [p["key"] for p in PEOPLE if p["gnews"].split()[0] in text or p["name"].split()[-1] in text]
            news.append({"t": t, "b": (it.get("body") or "")[:140], "o": it.get("officeName"), "at": at,
                         "u": f"https://n.news.naver.com/mnews/article/{it.get('officeId')}/{it.get('articleId')}",
                         "s": L.headline_score(t) if L else 0, "pol": any(w in text for w in POLICY_WORDS), "stocks": stocks[:4],
                         "themes": themes[:3], "who": who})
    seen, uniq = set(), []
    for n in sorted(news, key=lambda x: x["at"], reverse=True):
        if n["t"] in seen:
            continue
        seen.add(n["t"]); uniq.append(n)
    arch_p.write_text(json.dumps(arch, ensure_ascii=False, separators=(",", ":")))
    tnames = {n["key"]: n["name"] for n in NARRATIVES}
    (OUT / "latest.json").write_text(json.dumps({"made": NOW.strftime("%Y-%m-%d %H:%M"), "news": uniq, "people": people, "themes": tnames},
                                                ensure_ascii=False, separators=(",", ":")))
    print(f"뉴스 {len(uniq)}건 · 인물 {len(people)}명 · 트럼프 글 {people[0].get('n_posts')}개(7일)")


if __name__ == "__main__":
    main()
