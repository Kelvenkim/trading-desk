"""
매일 보고서 → data/us/daily_report.md (+ reports/날짜.md 보관)
  어제 올린 순위가 어땠는지 / 방식별 누적 채점 / 모의 투자 결과와 오늘 매매 / 기본 방식이 바뀌었는지(승격) / 오늘 바구니 변화 / 터틀 신호
us_daily.py 끝에서 불러요. 따로: python scripts/daily_report.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us"
VN = {"td": "추천 바구니", "t": "테마 눌림", "m": "12-1 모멘텀", "o": "우리 점수"}


def j(p, d=None):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return d


def pct(v, d=1):
    return "—" if v is None else f"{v * 100:+.{d}f}%"


def main():
    rank, rep, live, paper, tt, mk = j("rank.json"), j("rank_report.json", {}), j("rank_live.json", []), j("paper.json"), j("turtle.json"), j("market.json")
    if not rank:
        return
    day = rank["date"]
    hist = j("report_state.json", {"leader": None, "basket": [], "date": None})
    L = []
    sp = next((a for a in (mk or {}).get("assets", []) if a["t"] == "^GSPC"), None)
    nq = next((a for a in (mk or {}).get("assets", []) if a["t"] == "^IXIC"), None)
    g = rank.get("regime", {})
    L.append(f"## 📊 {day} 미국장 마감 보고")
    if sp:
        L.append(f"S&P500 {pct(sp['d1'])} · 나스닥 {pct(nq['d1']) if nq else '—'} · 시장 필터 {'통과 (200일선 위)' if g.get('up') else '멈춤 (200일선 아래)'}")

    # 1) 어제(직전) 올린 순위 결과
    L.append("\n### 1. 지난 순위, 실제로 어땠나")
    one = sorted([r for r in live if r["h"] == 1], key=lambda r: r["date"])
    if one:
        r = one[-1]
        parts = [f"{VN[k]} {pct(v['top'] - r['all'], 2)}" for k, v in r["var"].items()]
        L.append(f"- {r['date']} 순위 → 다음 날 (시가 매수, 전체 평균 {pct(r['all'], 2)} 대비): " + " · ".join(parts))
        b = r["var"].get("td", {}).get("best") or []
        if b:
            L.append("- 바구니 상위 5: " + ", ".join(f"{c} {pct(x)}" for c, x in b))
    else:
        L.append("- 아직 채점된 날이 없어요.")
    V = rep.get("variants", {})
    rows = []
    for k, nm in VN.items():
        cells = []
        for h in ("1", "5", "20"):
            x = (V.get(k) or {}).get(h)
            cells.append(f"{h}일 {pct(x['ex'], 2)} ({x['n']}번, 이김 {x['beat'] * 100:.0f}%)" if x else f"{h}일 —")
        rows.append(f"- {nm}: " + " · ".join(cells))
    L.append("**누적 채점** (상위 20 − 전체 평균)")
    L += rows

    # 2) 바뀐 것
    L.append("\n### 2. 그래서 바꾼 것")
    lead, why = rank.get("leader", "td"), rank.get("leader_why", "")
    if hist.get("leader") and hist["leader"] != lead:
        L.append(f"- **기본 방식 변경: {VN.get(hist['leader'])} → {VN.get(lead)}** — {why}")
    else:
        L.append(f"- 기본 방식 그대로: {VN.get(lead)} — {why}")
    L.append("- 공식 자체는 바꾸지 않았어요. 하루·며칠 결과로 바꾸면 우연에 맞추는 과적합이 돼서, 20일 채점 40번 + 확실성(t≥2) 조건을 넘을 때만 바꿔요.")

    # 3) 오늘 바구니 변화
    bk = [r["code"] for r in rank["rows"] if r.get("basket")]
    nm = {r["code"]: (r.get("ko") or r["code"]) for r in rank["rows"]}
    if hist.get("basket"):
        inn, out = [c for c in bk if c not in hist["basket"]], [c for c in hist["basket"] if c not in bk]
        L.append(f"- 오늘 바구니 20: 새로 들어옴 {', '.join(nm.get(c, c) for c in inn) or '없음'} / 빠짐 {', '.join(nm.get(c, c) for c in out) or '없음'}")
    else:
        L.append(f"- 오늘 바구니 20: {', '.join(nm.get(c, c) for c in bk)}")

    # 4) 모의 투자
    if paper:
        L.append("\n### 3. 모의 투자 ($10,000씩)")
        for k, lbl in (("basket", "추천 바구니"), ("turtle", "터틀"), ("spy", "S&P500 보유")):
            a = paper["acct"][k]; e = a["eq"]
            d1 = e[-1][1] / e[-2][1] - 1 if len(e) > 1 else None
            L.append(f"- {lbl}: ${e[-1][1]:,.0f} (시작 대비 {pct(e[-1][1] / paper['cash0'] - 1, 2)}, 하루 {pct(d1, 2)}) · 보유 {len(a['pos'])}종목")
        for k, lbl in (("basket", "바구니"), ("turtle", "터틀")):
            lg = [x for x in paper["acct"][k]["log"] if x["d"] == paper["date"]]
            buys = [x["t"] for x in lg if x["k"] == "buy"]
            sells = [f"{x['t']} {pct(x.get('pl'))}" for x in lg if x["k"] == "sell"]
            kills = [f"{x['t']}({x['why']})" if x["t"] else x["why"] for x in lg if x["k"] == "kill"]
            bits = []
            if buys: bits.append(f"매수 {len(buys)}건 ({', '.join(buys[:8])}{'…' if len(buys) > 8 else ''})")
            if sells: bits.append(f"매도 {', '.join(sells[:8])}")
            if kills: bits.append(f"걸러냄 {', '.join(kills[:5])}")
            if bits: L.append(f"- {lbl} 오늘: " + " · ".join(bits))
            o = paper["acct"][k]["orders"]
            if o: L.append(f"- {lbl} 내일 주문 {len(o)}건")
        st = paper["acct"]["turtle"]["stats"]
        if st["n"]:
            L.append(f"- 터틀 끝난 거래 {st['n']}건 · 이긴 비율 {st['win'] * 100:.0f}%")

    # 5) 터틀
    if tt:
        new = [r for r in tt["rows"] if r["st"]["kind"] == "new"]
        near = [r for r in tt["rows"] if r["st"]["kind"] == "near"]
        L.append(f"\n### 4. 터틀 신호\n- 오늘 진입 {len(new)} ({', '.join((r.get('ko') or r['code']) for r in new[:6]) or '없음'}) · 돌파 대기 {len(near)} · 청산 {tt['count'].get('exit', 0)}")

    L.append("\n_숫자는 참고용이고 투자 권유가 아니에요._")
    md = "\n".join(L)
    (D / "daily_report.md").write_text(md)
    (ROOT / "data/us/reports").mkdir(exist_ok=True)
    (ROOT / f"data/us/reports/{day}.md").write_text(md)
    (D / "report_state.json").write_text(json.dumps({"leader": lead, "basket": bk, "date": day}))
    print(md)


if __name__ == "__main__":
    main()
