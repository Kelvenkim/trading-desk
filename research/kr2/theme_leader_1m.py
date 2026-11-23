"""테마 대장주 1분봉 시험 (11/23 형: "10시에 바뀌면 바로 갈아타") — 네이버 1분봉(최근 약 2주만 제공)
매 1분봉 마감 때 전날 종가 대비 상승률로 가장 강한 테마 → 그 안 대장주(상한가 +29%↑ 제외) → 바뀌면 바로 다음 1분봉 가격에 갈아탐 → 15:15 정리
비용 왕복 0.25%(거래세 포함). 변형: 갈아타기 기준(새 대장이 X%p 앞설 때만), 시작 시각"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
import numpy as np, pandas as pd, requests

H = Path(__file__).parent / "data"; M1 = H / "m1"
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0"
U = {s["code"]: s for s in json.loads((H / "universe.json").read_text())}
TH = {t["name"]: [c for c in t["codes"] if c in U] for t in json.loads((H / "themes.json").read_text())}
TH = {n: cs for n, cs in TH.items() if len(cs) >= 3}
codes = sorted({c for cs in TH.values() for c in cs})


def days():
    d = json.loads((H / "day_005930.json").read_text()) if (H / "day_005930.json").exists() else None
    out, k = [], date.today()
    while len(out) < 7:
        if k.weekday() < 5:
            out.append(k.strftime("%Y%m%d"))
        k -= timedelta(days=1)
    return out


def get(code, dd):
    f = M1 / f"{code}_{dd}.json"
    if f.exists():
        return
    for _ in range(3):
        try:
            r = S.get(f"https://api.stock.naver.com/chart/domestic/item/{code}/minute?startDateTime={dd}0900&endDateTime={dd}1530", timeout=15)
            if r.status_code == 200:
                f.write_text(json.dumps([[x["localDateTime"][8:12], x["currentPrice"]] for x in r.json()])); return
        except Exception:
            time.sleep(1)


def prevclose():
    pc = {}
    for c in codes:
        f = H / f"day_{c}.json"
        if f.exists():
            d = pd.DataFrame(json.loads(f.read_text()), columns=["d", "o", "h", "l", "c", "v", "fr"]).set_index("d"); pc[c] = d.c.where(d.c > 0)
    return pd.DataFrame(pc)


def sim(px, pc, edge=0.0, start="0901", cost=0.0025):
    ret = px / pc - 1
    hold = ent = None; pnl = 0.0; sw = 0
    mins = [m for m in px.index if start <= m <= "1514"]
    for i, m in enumerate(mins[:-1]):
        row = ret.loc[m]
        th = {n: row.reindex(cs).mean() for n, cs in TH.items()}
        th = {n: v for n, v in th.items() if np.isfinite(v)}
        if not th:
            continue
        top = max(th, key=th.get)
        cand = row.reindex(TH[top]).dropna(); cand = cand[cand < 0.29]
        if not len(cand):
            continue
        lead = cand.idxmax()
        if lead != hold and (hold is None or cand[lead] - row.get(hold, -9) >= edge):
            nxt = px.loc[mins[i + 1]]
            if not np.isfinite(nxt.get(lead, np.nan)):
                continue
            if hold is not None and np.isfinite(nxt.get(hold, np.nan)):
                pnl += nxt[hold] / ent - 1 - cost; sw += 1
            hold, ent = lead, nxt[lead]
    if hold is not None:
        last = px.loc[mins[-1]].get(hold, np.nan)
        if np.isfinite(last):
            pnl += last / ent - 1 - cost
    return pnl, sw


if __name__ == "__main__":
    DD = days()
    with ThreadPoolExecutor(24) as ex:
        list(ex.map(lambda a: get(*a), [(c, d) for d in DD for c in codes]))
    PC = prevclose(); res = {}
    for dd in sorted(DD):
        cols = {}
        for c in codes:
            f = M1 / f"{c}_{dd}.json"
            if f.exists():
                x = json.loads(f.read_text())
                if x:
                    cols[c] = pd.Series({m: p for m, p in x})
        if len(cols) < 500:
            continue
        px = pd.DataFrame(cols).sort_index().ffill()
        prev = PC[PC.index < dd]
        if not len(prev):
            continue
        pc = prev.iloc[-1].reindex(px.columns)
        for lab, kw in (("바로 갈아탐", {}), ("1%p 앞설 때만", dict(edge=0.01)), ("3%p 앞설 때만", dict(edge=0.03)), ("10시부터", dict(start="1000", edge=0.01))):
            res.setdefault(lab, []).append((dd, *sim(px, pc, **kw)))
    out = {}
    for lab, rows in res.items():
        R = pd.DataFrame(rows, columns=["day", "pnl", "sw"])
        out[lab] = R
        print(f"{lab:<14} {len(R)}일 · 하루 평균 {R.pnl.mean() * 100:+.2f}% · 이긴 날 {(R.pnl > 0).mean():.0%} · 하루 갈아탄 횟수 {R.sw.mean():.1f}번 · 누적 {np.prod(1 + R.pnl) - 1:+.1%} · 비용 빼기 전 {(R.pnl.mean() + 0.0025 * (1 + R.sw.mean())) * 100:+.2f}%")
    pd.to_pickle(out, H / "theme1m.pkl")
